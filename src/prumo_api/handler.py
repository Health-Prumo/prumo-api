"""Entrada da Lambda (API Gateway HTTP API, payload 2.0) e do servidor local."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from prumo_api import regras
from prumo_api.ia import AVISO, Coach
from prumo_api.repositorio import Repositorio, criar_repositorio

log = logging.getLogger()
log.setLevel(logging.INFO)

VERSAO_CONSENTIMENTO = "2026-11"
ORIGENS_PADRAO = "http://localhost:5173,https://app.healthprumo.online"

_repo: Repositorio | None = None
_coach: Coach | None = None


def configurar(repo: Repositorio | None = None, coach: Coach | None = None) -> None:
    """Troca o repositório e o coach (testes e servidor local)."""
    global _repo, _coach
    _repo, _coach = repo, coach


def repo() -> Repositorio:
    global _repo
    if _repo is None:
        _repo = criar_repositorio()
    return _repo


def coach() -> Coach:
    global _coach
    if _coach is None:
        _coach = Coach()
    return _coach


class ErroHttp(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status, self.codigo, self.mensagem = status, codigo, mensagem


# ---------------------------------------------------------------- utilidades


def agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def hoje_local() -> date:
    """Data de hoje no fuso do usuário (Brasília por padrão, sem horário de verão)."""
    fuso = timezone(timedelta(hours=float(os.environ.get("PRUMO_FUSO_HORAS", "-3"))))
    return datetime.now(fuso).date()


def _origens() -> list[str]:
    return [o.strip() for o in os.environ.get("PRUMO_ORIGENS", ORIGENS_PADRAO).split(",") if o.strip()]


def _cabecalhos_cors(origem: str | None) -> dict[str, str]:
    if not origem or origem not in _origens():
        return {}
    return {
        "Access-Control-Allow-Origin": origem,
        "Access-Control-Allow-Methods": "GET,PUT,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "authorization,content-type",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


def _resposta(status: int, corpo: Any, origem: str | None) -> dict[str, Any]:
    cabecalhos = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
    cabecalhos.update(_cabecalhos_cors(origem))
    return {
        "statusCode": status,
        "headers": cabecalhos,
        "body": "" if corpo is None else json.dumps(corpo, ensure_ascii=False),
    }


def _corpo(evento: dict[str, Any]) -> Any:
    bruto = evento.get("body") or ""
    if evento.get("isBase64Encoded"):
        bruto = base64.b64decode(bruto).decode("utf-8")
    if not bruto:
        raise ErroHttp(400, "dados_invalidos", "O corpo da requisição está vazio.")
    try:
        return json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise ErroHttp(400, "dados_invalidos", "O corpo precisa ser um JSON válido.") from erro


def _usuario(evento: dict[str, Any]) -> str:
    if os.environ.get("PRUMO_AUTH") == "local":
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            raise RuntimeError("PRUMO_AUTH=local não pode ser usado na Lambda.")
        cabecalhos = {k.lower(): v for k, v in (evento.get("headers") or {}).items()}
        if str(cabecalhos.get("authorization", "")).startswith("Bearer local-"):
            return "local-dev"
        raise ErroHttp(401, "nao_autenticado", "Faça login para continuar.")
    claims = evento.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    sub = claims.get("sub")
    if not isinstance(sub, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", sub):
        raise ErroHttp(401, "nao_autenticado", "Faça login para continuar.")
    return sub


def _data(texto: str) -> date:
    try:
        valor = date.fromisoformat(texto)
    except ValueError as erro:
        raise ErroHttp(400, "dados_invalidos", "Use a data no formato aaaa-mm-dd.") from erro
    if valor > hoje_local():
        raise ErroHttp(400, "dados_invalidos", "Não é possível registrar um dia que ainda não chegou.")
    return valor


def _exigir_consentimento(usuario: str) -> dict[str, Any]:
    perfil = repo().obter_perfil(usuario)
    if not perfil or not perfil.get("consentimento", {}).get("aceito"):
        raise ErroHttp(403, "consentimento_necessario", "Aceite o termo de consentimento para registrar seus dados.")
    return perfil


# ---------------------------------------------------------------- rotas


def rota_saude(_evento: dict[str, Any], _usuario_id: str | None, _p: dict[str, str]) -> tuple[int, Any]:
    return 200, {"status": "ok"}


def rota_obter_perfil(_evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    perfil = repo().obter_perfil(usuario)
    if not perfil:
        raise ErroHttp(404, "perfil_inexistente", "Perfil ainda não criado.")
    return 200, perfil


def rota_salvar_perfil(evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    dados = _corpo(evento)
    if not isinstance(dados, dict) or dados.get("sexo") not in regras.SEXOS:
        raise ErroHttp(400, "dados_invalidos", "Informe o sexo como feminino, masculino ou nao_informar.")
    if dados.get("consentimento_aceito") is not True:
        raise ErroHttp(403, "consentimento_necessario", "Aceite o termo de consentimento para continuar.")
    atual = repo().obter_perfil(usuario) or {}
    momento = agora()
    perfil = {
        "sexo": dados["sexo"],
        "consentimento": atual.get("consentimento") or {"aceito": True, "versao": VERSAO_CONSENTIMENTO, "em": momento},
        "criado_em": atual.get("criado_em", momento),
    }
    repo().salvar_perfil(usuario, perfil)
    return 200, perfil


def rota_salvar_dia(evento: dict[str, Any], usuario: str, p: dict[str, str]) -> tuple[int, Any]:
    data = _data(p["data"])
    perfil = _exigir_consentimento(usuario)
    try:
        registro = regras.validar_registro(_corpo(evento))
    except regras.ErroValidacao as erro:
        raise ErroHttp(400, "dados_invalidos", str(erro)) from erro
    inicio = (data - timedelta(days=7)).isoformat()
    fim = (data - timedelta(days=1)).isoformat()
    anteriores = {d["data"]: d["registro"] for d in repo().listar_dias(usuario, inicio, fim)}
    notas = regras.calcular(registro, perfil.get("sexo", "nao_informar"), anteriores, data)
    analise = coach().analisar_dia(registro, notas)
    dia = {"data": data.isoformat(), "registro": registro, "notas": notas, "analise": analise, "calculado_em": agora()}
    repo().salvar_dia(usuario, data.isoformat(), dia)
    return 200, dia


def rota_obter_dia(_evento: dict[str, Any], usuario: str, p: dict[str, str]) -> tuple[int, Any]:
    dia = repo().obter_dia(usuario, _data(p["data"]).isoformat())
    if not dia:
        raise ErroHttp(404, "dia_inexistente", "Nenhum registro para esse dia.")
    return 200, dia


def _ponto(dia: dict[str, Any]) -> dict[str, Any]:
    r, n = dia["registro"], dia["notas"]
    return {
        "data": dia["data"],
        "energia": n["energia"],
        "sono_horas": r["sono_horas"],
        "atividade_minutos": r["atividade_minutos"],
        # Minutos que contam para a meta da OMS (vigorosa vale 2, leve não conta).
        "atividade_meta_min": regras.arredondar(
            regras.minutos_equivalentes(r["atividade_minutos"], r["atividade_intensidade"])
        ),
        "agua_litros": r["agua_litros"],
        "alimentacao_nota": n["habitos"]["alimentacao"]["nota"],
        "humor": r["humor"],
        "tela_horas": r["tela_horas"],
    }


def _dias_recentes(usuario: str, quantidade: int) -> list[dict[str, Any]]:
    fim = hoje_local()
    inicio = fim - timedelta(days=quantidade - 1)
    return repo().listar_dias(usuario, inicio.isoformat(), fim.isoformat())


def rota_historico(evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    bruto = (evento.get("queryStringParameters") or {}).get("dias", "30")
    if not str(bruto).isdigit() or not 1 <= int(bruto) <= 90:
        raise ErroHttp(400, "dados_invalidos", "O parâmetro 'dias' precisa ficar entre 1 e 90.")
    return 200, {"dias": [_ponto(d) for d in _dias_recentes(usuario, int(bruto))]}


def resumo_historico(dias: list[dict[str, Any]], meta_agua_l: float = 2.0) -> dict[str, Any]:
    """Resumo numérico do histórico para o Coach. Sem nenhum identificador."""
    if not dias:
        return {"dias_registrados": 0, "meta_agua_l": meta_agua_l}
    pontos = [_ponto(d) for d in dias]

    def media(chave: str) -> float:
        return regras.arredondar(sum(float(p[chave]) for p in pontos) / len(pontos), 2)

    medias_notas = {
        h: regras.arredondar(sum(d["notas"]["habitos"][h]["nota"] for d in dias) / len(dias), 1) for h in regras.HABITOS
    }
    return {
        "dias_registrados": len(pontos),
        "energia_media": media("energia"),
        "sono_medio_h": media("sono_horas"),
        "atividade_media_min_dia": media("atividade_minutos"),
        "agua_media_l": media("agua_litros"),
        "humor_medio_1a5": media("humor"),
        "tela_media_h": media("tela_horas"),
        "notas_medias_0a10": medias_notas,
        "habito_mais_baixo": min(regras.HABITOS, key=lambda h: (medias_notas[h], regras.HABITOS.index(h))),
        "sono_qualidade_media": regras.arredondar(sum(d["registro"]["sono_qualidade"] for d in dias) / len(dias), 1),
        "dias_frutas_verduras": sum(1 for d in dias if d["registro"]["alimentacao"]["frutas_verduras"]),
        "dias_refeicao_caseira": sum(1 for d in dias if d["registro"]["alimentacao"]["refeicao_caseira"]),
        "dias_ultraprocessados": sum(1 for d in dias if d["registro"]["alimentacao"]["ultraprocessados"]),
        "atividade_semana_min": dias[-1]["notas"]["habitos"]["atividade"]["semana_min"],
        "meta_semana_min": dias[-1]["notas"]["habitos"]["atividade"]["meta_semana_min"],
        "meta_agua_l": meta_agua_l,
        "pesos": dias[-1]["notas"].get("pesos", {}),
        "ultimos_7_dias": [
            {"dia": i - len(pontos[-7:]), "energia": p["energia"], "sono_h": p["sono_horas"], "tela_h": p["tela_horas"]}
            for i, p in enumerate(pontos[-7:])
        ],
    }


def rota_listar_chat(_evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    return 200, {"mensagens": repo().listar_chat(usuario, 50)}


def rota_chat(evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    _exigir_consentimento(usuario)
    dados = _corpo(evento)
    mensagem = dados.get("mensagem") if isinstance(dados, dict) else None
    if not isinstance(mensagem, str) or not 1 <= len(mensagem.strip()) <= 500:
        raise ErroHttp(400, "dados_invalidos", "A mensagem precisa ter de 1 a 500 caracteres.")
    mensagem = mensagem.strip()
    conversa = repo().listar_chat(usuario, 6)
    perfil = repo().obter_perfil(usuario) or {}
    meta_agua_l = regras.meta_agua(str(perfil.get("sexo", "nao_informar")))
    resumo = resumo_historico(_dias_recentes(usuario, 30), meta_agua_l)
    resposta, fonte = coach().responder(mensagem, resumo, conversa)
    repo().adicionar_chat(usuario, "usuario", mensagem, agora())
    repo().adicionar_chat(usuario, "coach", resposta, agora())
    return 200, {"resposta": resposta, "fonte": fonte}


def rota_exportar(_evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    return 200, repo().exportar(usuario)


def rota_apagar_conta(_evento: dict[str, Any], usuario: str, _p: dict[str, str]) -> tuple[int, Any]:
    repo().apagar_tudo(usuario)
    return 204, None


Rota = Callable[[dict[str, Any], Any, dict[str, str]], tuple[int, Any]]

ROTAS: list[tuple[str, re.Pattern[str], Rota, bool]] = [
    ("GET", re.compile(r"^/saude$"), rota_saude, False),
    ("GET", re.compile(r"^/perfil$"), rota_obter_perfil, True),
    ("PUT", re.compile(r"^/perfil$"), rota_salvar_perfil, True),
    ("PUT", re.compile(r"^/dias/(?P<data>[^/]+)$"), rota_salvar_dia, True),
    ("GET", re.compile(r"^/dias/(?P<data>[^/]+)$"), rota_obter_dia, True),
    ("GET", re.compile(r"^/historico$"), rota_historico, True),
    ("GET", re.compile(r"^/chat$"), rota_listar_chat, True),
    ("POST", re.compile(r"^/chat$"), rota_chat, True),
    ("GET", re.compile(r"^/exportar$"), rota_exportar, True),
    ("DELETE", re.compile(r"^/conta$"), rota_apagar_conta, True),
]


def tarefa_diaria(evento: dict[str, Any]) -> dict[str, Any]:
    """Disparada pelo EventBridge Scheduler. Por enquanto só registra a execução."""
    log.info("Tarefa diária executada (origem: %s).", evento.get("source", "scheduler"))
    return {"ok": True}


def handler(evento: dict[str, Any], _contexto: Any = None) -> dict[str, Any]:
    if "requestContext" not in evento:
        return tarefa_diaria(evento)

    metodo = evento["requestContext"].get("http", {}).get("method", "GET").upper()
    caminho = evento.get("rawPath") or "/"
    cabecalhos = {k.lower(): v for k, v in (evento.get("headers") or {}).items()}
    origem = cabecalhos.get("origin")

    if metodo == "OPTIONS":
        return _resposta(204, None, origem)

    status = 500
    try:
        caminho_existe = False
        for rota_metodo, padrao, funcao, protegida in ROTAS:
            encontrado = padrao.match(caminho)
            if not encontrado:
                continue
            caminho_existe = True
            if rota_metodo != metodo:
                continue
            usuario = _usuario(evento) if protegida else None
            status, corpo = funcao(evento, usuario, encontrado.groupdict())
            return _resposta(status, corpo, origem)
        if caminho_existe:
            status = 405
            raise ErroHttp(405, "metodo_nao_permitido", "Método não permitido nesta rota.")
        status = 404
        raise ErroHttp(404, "rota_inexistente", "Rota não encontrada.")
    except ErroHttp as erro:
        status = erro.status
        return _resposta(erro.status, {"erro": erro.codigo, "mensagem": erro.mensagem}, origem)
    except Exception:
        log.exception("Erro inesperado em %s %s", metodo, caminho)
        return _resposta(
            500, {"erro": "erro_interno", "mensagem": "Algo deu errado. Tente de novo em instantes."}, origem
        )
    finally:
        # Só método, caminho e status: nunca o corpo, que tem dados de saúde.
        log.info("%s %s -> %s", metodo, caminho, status)


__all__ = ["AVISO", "configurar", "handler"]
