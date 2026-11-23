"""Fixtures isoladas: banco temporário, configuração local e nenhuma rede."""

import socket
from pathlib import Path
from typing import Any

import pytest
from flask.testing import FlaskClient

from local_server import criar_app


@pytest.fixture(autouse=True)
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    valores = {
        "PRUMO_AMBIENTE": "teste",
        "PRUMO_BANCO_LOCAL": str(tmp_path / "prumo.sqlite3"),
        "PRUMO_USUARIO_LOCAL": "usuario-teste",
        "PRUMO_ORIGEM_FRONT": "http://localhost:5173",
        "PRUMO_PORTA": "8000",
        "PRUMO_HOST_LOCAL": "127.0.0.1",
        "PRUMO_LLM_MODO": "mock",
    }
    for nome, valor in valores.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    def bloquear_rede(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Testes do protótipo não podem acessar a rede.")

    monkeypatch.setattr(socket.socket, "connect", bloquear_rede)
    monkeypatch.setattr(socket, "create_connection", bloquear_rede)


@pytest.fixture
def cliente() -> FlaskClient:
    app = criar_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def registro() -> dict[str, Any]:
    return {
        "sono_horas": 7.5,
        "sono_qualidade": 4,
        "atividade_minutos": 30,
        "atividade_intensidade": "moderada",
        "agua_litros": 1.8,
        "alimentacao": {
            "frutas_verduras": True,
            "refeicao_caseira": True,
            "ultraprocessados": False,
        },
        "humor": 4,
        "energia": 3,
        "tela_lazer_horas": 2,
    }
