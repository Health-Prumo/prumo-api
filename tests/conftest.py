from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from prumo_api import handler as api
from prumo_api.ia import Coach
from prumo_api.repositorio import RepositorioMemoria

USUARIO = "2f1c9a7e-0000-4000-8000-000000000001"


def registro(**alteracoes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sono_horas": 7.5,
        "sono_qualidade": 4,
        "atividade_minutos": 30,
        "atividade_intensidade": "moderada",
        "agua_litros": 2.0,
        "alimentacao": {"frutas_verduras": True, "refeicao_caseira": True, "ultraprocessados": False},
        "humor": 4,
        "tela_horas": 1.5,
    }
    base.update(alteracoes)
    return base


@pytest.fixture(autouse=True)
def ambiente(monkeypatch: pytest.MonkeyPatch) -> Iterator[RepositorioMemoria]:
    for var in ("PRUMO_AUTH", "PRUMO_PESOS", "PRUMO_TABELA", "AWS_LAMBDA_FUNCTION_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PRUMO_IA", "mock")
    monkeypatch.setenv("PRUMO_ORIGENS", "http://localhost:5173,https://app.healthprumo.online")
    repo = RepositorioMemoria()
    api.configurar(repo=repo, coach=Coach("mock"))
    yield repo
    api.configurar()


Chamar = Callable[..., tuple[int, Any, dict[str, str]]]


@pytest.fixture
def chamar() -> Chamar:
    def _chamar(
        metodo: str,
        caminho: str,
        corpo: Any = None,
        usuario: str | None = USUARIO,
        origem: str | None = None,
        query: dict[str, str] | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        evento: dict[str, Any] = {
            "version": "2.0",
            "rawPath": caminho,
            "headers": {"origin": origem} if origem else {},
            "queryStringParameters": query,
            "body": None if corpo is None else json.dumps(corpo),
            "isBase64Encoded": False,
            "requestContext": {"http": {"method": metodo}},
        }
        if usuario:
            evento["requestContext"]["authorizer"] = {
                "jwt": {"claims": {"sub": usuario, "email": "pessoa@exemplo.com"}}
            }
        resposta = api.handler(evento)
        corpo_resposta = json.loads(resposta["body"]) if resposta["body"] else None
        return resposta["statusCode"], corpo_resposta, resposta["headers"]

    return _chamar


@pytest.fixture
def com_perfil(chamar: Chamar) -> None:
    status, _, _ = chamar("PUT", "/perfil", {"sexo": "feminino", "consentimento_aceito": True})
    assert status == 200
