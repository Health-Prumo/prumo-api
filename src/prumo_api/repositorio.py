"""Persistência: DynamoDB (tabela única) na AWS; memória ou arquivo JSON no local e nos testes.

Chaves: PK = USUARIO#<sub>; SK = PERFIL | DIA#<aaaa-mm-dd> | CHAT#<timestamp>.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

# Conversas do Coach se apagam sozinhas depois de 7 dias: o DynamoDB remove o item pelo TTL
# (atributo expira_em) e, como essa remoção pode atrasar até uns 2 dias, a leitura já ignora
# mensagens vencidas.
TTL_CHAT_DIAS = 7


def chat_vigente(item: dict[str, Any], agora: datetime | None = None) -> bool:
    """True se a mensagem tem menos de TTL_CHAT_DIAS dias."""
    try:
        em = datetime.fromisoformat(str(item["em"]))
    except (KeyError, ValueError):
        return False
    if em.tzinfo is None:
        em = em.replace(tzinfo=UTC)
    return em > (agora or datetime.now(UTC)) - timedelta(days=TTL_CHAT_DIAS)


def _pk(usuario: str) -> str:
    return f"USUARIO#{usuario}"


class Repositorio(Protocol):
    def obter_perfil(self, usuario: str) -> dict[str, Any] | None: ...
    def salvar_perfil(self, usuario: str, perfil: dict[str, Any]) -> None: ...
    def obter_dia(self, usuario: str, data: str) -> dict[str, Any] | None: ...
    def salvar_dia(self, usuario: str, data: str, dia: dict[str, Any]) -> None: ...
    def listar_dias(self, usuario: str, inicio: str, fim: str) -> list[dict[str, Any]]: ...
    def adicionar_chat(self, usuario: str, papel: str, texto: str, em: str) -> None: ...
    def listar_chat(self, usuario: str, limite: int) -> list[dict[str, Any]]: ...
    def exportar(self, usuario: str) -> dict[str, Any]: ...
    def apagar_tudo(self, usuario: str) -> None: ...


def _chave_chat(em: str) -> str:
    # Sufixo de alta resolução evita colisão de duas mensagens no mesmo segundo.
    return f"CHAT#{em}#{time.time_ns() % 10**9:09d}"


# ---------------------------------------------------------------- memória / arquivo


class RepositorioMemoria:
    """Guarda tudo num dicionário; com `arquivo`, persiste em JSON (uso local)."""

    def __init__(self, arquivo: str | Path | None = None) -> None:
        self._itens: dict[str, dict[str, dict[str, Any]]] = {}
        self._arquivo = Path(arquivo) if arquivo else None
        self._trava = threading.Lock()
        if self._arquivo and self._arquivo.exists():
            self._itens = json.loads(self._arquivo.read_text("utf-8"))

    def _gravar(self) -> None:
        if self._arquivo:
            self._arquivo.write_text(json.dumps(self._itens, ensure_ascii=False, indent=1), "utf-8")

    def _put(self, usuario: str, sk: str, item: dict[str, Any]) -> None:
        with self._trava:
            self._itens.setdefault(_pk(usuario), {})[sk] = json.loads(json.dumps(item))
            self._gravar()

    def _get(self, usuario: str, sk: str) -> dict[str, Any] | None:
        item = self._itens.get(_pk(usuario), {}).get(sk)
        return json.loads(json.dumps(item)) if item is not None else None

    def obter_perfil(self, usuario: str) -> dict[str, Any] | None:
        return self._get(usuario, "PERFIL")

    def salvar_perfil(self, usuario: str, perfil: dict[str, Any]) -> None:
        self._put(usuario, "PERFIL", perfil)

    def obter_dia(self, usuario: str, data: str) -> dict[str, Any] | None:
        return self._get(usuario, f"DIA#{data}")

    def salvar_dia(self, usuario: str, data: str, dia: dict[str, Any]) -> None:
        self._put(usuario, f"DIA#{data}", dia)

    def listar_dias(self, usuario: str, inicio: str, fim: str) -> list[dict[str, Any]]:
        itens = self._itens.get(_pk(usuario), {})
        chaves = sorted(k for k in itens if f"DIA#{inicio}" <= k <= f"DIA#{fim}")
        return [json.loads(json.dumps(itens[k])) for k in chaves]

    def adicionar_chat(self, usuario: str, papel: str, texto: str, em: str) -> None:
        self._put(usuario, _chave_chat(em), {"papel": papel, "texto": texto, "em": em})

    def listar_chat(self, usuario: str, limite: int) -> list[dict[str, Any]]:
        itens = self._itens.get(_pk(usuario), {})
        chaves = sorted(k for k in itens if k.startswith("CHAT#") and chat_vigente(itens[k]))[-limite:]
        return [json.loads(json.dumps(itens[k])) for k in chaves]

    def exportar(self, usuario: str) -> dict[str, Any]:
        itens = self._itens.get(_pk(usuario), {})
        return {
            "perfil": self.obter_perfil(usuario),
            "dias": [itens[k] for k in sorted(itens) if k.startswith("DIA#")],
            "chat": [itens[k] for k in sorted(itens) if k.startswith("CHAT#") and chat_vigente(itens[k])],
        }

    def apagar_tudo(self, usuario: str) -> None:
        with self._trava:
            self._itens.pop(_pk(usuario), None)
            self._gravar()


# ---------------------------------------------------------------- DynamoDB


def _para_dynamo(valor: Any) -> Any:
    """DynamoDB não aceita float: converte para Decimal (recursivo)."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, float):
        return Decimal(str(valor))
    if isinstance(valor, dict):
        return {k: _para_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_para_dynamo(v) for v in valor]
    return valor


def _de_dynamo(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, dict):
        return {k: _de_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_de_dynamo(v) for v in valor]
    return valor


def _limpar(item: dict[str, Any]) -> dict[str, Any]:
    dados: dict[str, Any] = _de_dynamo(item)
    for chave in ("PK", "SK", "expira_em"):
        dados.pop(chave, None)
    return dados


class RepositorioDynamo:
    def __init__(self, tabela: str, recurso: Any = None) -> None:
        if recurso is None:
            import boto3

            recurso = boto3.resource("dynamodb")
        self._tabela = recurso.Table(tabela)

    def _put(self, usuario: str, sk: str, item: dict[str, Any], **extra: Any) -> None:
        self._tabela.put_item(Item=_para_dynamo({**item, **extra, "PK": _pk(usuario), "SK": sk}))

    def _get(self, usuario: str, sk: str) -> dict[str, Any] | None:
        item = self._tabela.get_item(Key={"PK": _pk(usuario), "SK": sk}).get("Item")
        return _limpar(item) if item else None

    def _query(self, **kwargs: Any) -> list[dict[str, Any]]:
        itens: list[dict[str, Any]] = []
        while True:
            resposta = self._tabela.query(**kwargs)
            itens.extend(resposta.get("Items", []))
            ultimo = resposta.get("LastEvaluatedKey")
            if not ultimo or ("Limit" in kwargs and len(itens) >= kwargs["Limit"]):
                return itens
            kwargs["ExclusiveStartKey"] = ultimo

    def obter_perfil(self, usuario: str) -> dict[str, Any] | None:
        return self._get(usuario, "PERFIL")

    def salvar_perfil(self, usuario: str, perfil: dict[str, Any]) -> None:
        self._put(usuario, "PERFIL", perfil)

    def obter_dia(self, usuario: str, data: str) -> dict[str, Any] | None:
        return self._get(usuario, f"DIA#{data}")

    def salvar_dia(self, usuario: str, data: str, dia: dict[str, Any]) -> None:
        self._put(usuario, f"DIA#{data}", dia)

    def listar_dias(self, usuario: str, inicio: str, fim: str) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        itens = self._query(
            KeyConditionExpression=Key("PK").eq(_pk(usuario)) & Key("SK").between(f"DIA#{inicio}", f"DIA#{fim}")
        )
        return [_limpar(i) for i in itens]

    def adicionar_chat(self, usuario: str, papel: str, texto: str, em: str) -> None:
        expira = int(time.time()) + TTL_CHAT_DIAS * 86400
        self._put(usuario, _chave_chat(em), {"papel": papel, "texto": texto, "em": em}, expira_em=expira)

    def listar_chat(self, usuario: str, limite: int) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        itens = self._query(
            KeyConditionExpression=Key("PK").eq(_pk(usuario)) & Key("SK").begins_with("CHAT#"),
            ScanIndexForward=False,
            Limit=limite,
        )
        return [_limpar(i) for i in reversed(itens[:limite]) if chat_vigente(i)]

    def _todos(self, usuario: str) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        return self._query(KeyConditionExpression=Key("PK").eq(_pk(usuario)))

    def exportar(self, usuario: str) -> dict[str, Any]:
        itens = self._todos(usuario)
        perfil = next((_limpar(i) for i in itens if i["SK"] == "PERFIL"), None)
        return {
            "perfil": perfil,
            "dias": [_limpar(i) for i in itens if str(i["SK"]).startswith("DIA#")],
            "chat": [_limpar(i) for i in itens if str(i["SK"]).startswith("CHAT#") and chat_vigente(i)],
        }

    def apagar_tudo(self, usuario: str) -> None:
        with self._tabela.batch_writer() as lote:
            for item in self._todos(usuario):
                lote.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})


def criar_repositorio() -> Repositorio:
    """Escolhe o repositório pelas variáveis de ambiente."""
    tabela = os.environ.get("PRUMO_TABELA")
    if tabela:
        return RepositorioDynamo(tabela)
    return RepositorioMemoria(os.environ.get("PRUMO_ARQUIVO_LOCAL") or None)
