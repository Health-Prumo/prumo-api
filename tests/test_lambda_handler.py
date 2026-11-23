"""Testes de contrato, persistência, autorização e exclusão."""

import base64
import json
from typing import Any

import pytest

from main import handler, lambda_handler
from tests.apoio import CONSENTIMENTO, evento


def test_fluxo_completo_e_idempotencia(registro: dict[str, Any]) -> None:
    assert handler(evento("GET", "/health"))["statusCode"] == 200
    assert lambda_handler(evento("GET", "/health")) == handler(evento("GET", "/health"))
    assert handler(evento("PUT", "/dias/2026-11-23", registro))["statusCode"] == 403
    assert handler(evento("PUT", "/perfil", CONSENTIMENTO))["statusCode"] == 200
    for _ in range(2):
        resultado = handler(evento("PUT", "/dias/2026-11-23", registro))
        assert resultado["statusCode"] == 200
        dados = json.loads(resultado["body"])
        assert dados["nota"] is None
        assert dados["status_avaliacao"] == "regras_pendentes"
        assert len(dados["card"]["sugestoes"]) <= 2
        assert dados["card"]["modo"] == "mock"
    consulta = handler(evento("GET", "/dias/2026-11-23"))
    assert json.loads(consulta["body"])["registro"] == registro
    historico = json.loads(handler(evento("GET", "/historico"))["body"])
    assert len(historico["dias"]) == 1
    exportacao = json.loads(handler(evento("GET", "/dados/exportacao"))["body"])
    assert {item["chave"] for item in exportacao["itens"]} == {"PERFIL", "DIA#2026-11-23"}
    assert handler(evento("DELETE", "/dados"))["statusCode"] == 204
    assert json.loads(handler(evento("GET", "/dados/exportacao"))["body"]) == {"itens": []}
    assert handler(evento("GET", "/dias/2026-11-23"))["statusCode"] == 404
    assert handler(evento("PUT", "/dias/2026-11-23", registro))["statusCode"] == 403


def test_isolamento_e_exclusao_por_usuario(registro: dict[str, Any]) -> None:
    for usuario in ["alice", "bruno"]:
        handler(evento("PUT", "/perfil", CONSENTIMENTO, usuario))
        handler(evento("PUT", "/dias/2026-11-23", registro, usuario))
    handler(evento("DELETE", "/dados", usuario="alice"))
    assert handler(evento("GET", "/dias/2026-11-23", usuario="alice"))["statusCode"] == 404
    assert handler(evento("GET", "/dias/2026-11-23", usuario="bruno"))["statusCode"] == 200
    assert json.loads(handler(evento("GET", "/historico", usuario="carla"))["body"]) == {"dias": []}


def test_nao_aceita_identidade_do_cliente(registro: dict[str, Any]) -> None:
    requisicao = evento("PUT", "/dias/2026-11-23", registro)
    del requisicao["requestContext"]["authorizer"]
    requisicao["headers"]["x-user-id"] = "alice"
    assert handler(requisicao)["statusCode"] == 401
    requisicao["version"] = "1.0"
    assert handler(requisicao)["statusCode"] == 400


@pytest.mark.parametrize("corpo", ["{", "[]", "null", '{"agua_litros": NaN}', '{"a": Infinity}'])
def test_json_invalido(corpo: str) -> None:
    requisicao = evento("PUT", "/perfil")
    requisicao["body"] = corpo
    assert handler(requisicao)["statusCode"] == 400


def test_base64_e_limites() -> None:
    requisicao = evento("PUT", "/perfil", CONSENTIMENTO)
    requisicao["body"] = base64.b64encode(requisicao["body"].encode()).decode()
    requisicao["isBase64Encoded"] = True
    assert handler(requisicao)["statusCode"] == 200
    for invalido in ["%%%", "/w=="]:
        requisicao["body"] = invalido
        assert handler(requisicao)["statusCode"] == 400
    requisicao["isBase64Encoded"] = False
    for tamanho in [70_000, 140_000]:
        requisicao["body"] = "x" * tamanho
        assert handler(requisicao)["statusCode"] == 413
    requisicao["headers"] = {}
    assert handler(requisicao)["statusCode"] == 415


@pytest.mark.parametrize(
    ("metodo", "caminho", "status"),
    [
        ("GET", "/inexistente", 404),
        ("POST", "/perfil", 405),
        ("GET", "/dias/2026-02-30", 422),
        ("GET", "/dias/20261123", 422),
        ("OPTIONS", "/perfil", 204),
    ],
)
def test_rotas_e_datas(metodo: str, caminho: str, status: int) -> None:
    assert handler(evento(metodo, caminho))["statusCode"] == status


def test_filtro_e_atualizacao_do_historico(registro: dict[str, Any]) -> None:
    handler(evento("PUT", "/perfil", CONSENTIMENTO))
    for data in ["2026-11-15", "2026-11-16", "2026-11-22", "2026-11-23"]:
        handler(evento("PUT", f"/dias/{data}", registro))
    requisicao = evento("GET", "/historico")
    requisicao["queryStringParameters"] = {"inicio": "2026-11-23", "fim": "2026-11-23"}
    dias = json.loads(handler(requisicao)["body"])["dias"]
    assert len(dias) == 1
    assert dias[0]["resumo_historico"]["dias_registrados"] == 2
    registro["sono_horas"] = 8.5
    handler(evento("PUT", "/dias/2026-11-22", registro))
    atualizado = json.loads(handler(evento("GET", "/dias/2026-11-23"))["body"])
    assert atualizado["resumo_historico"]["medias"]["sono_horas"] == 8
    requisicao["queryStringParameters"] = {"inicio": "2026-11-24", "fim": "2026-11-23"}
    assert handler(requisicao)["statusCode"] == 400
    requisicao["queryStringParameters"] = {"usuario": "outro"}
    assert handler(requisicao)["statusCode"] == 400


def test_falha_de_configuracao_nao_expoe_detalhes(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PRUMO_LLM_MODO", "bedrock")
    retorno = handler(evento("GET", "/health"))
    assert retorno["statusCode"] == 503
    assert "bedrock" not in retorno["body"]
    assert "bedrock" not in caplog.text
