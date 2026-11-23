"""O tratamento central preserva o contrato e não registra dados sensíveis."""

import json
import logging
import sqlite3
from typing import Any

import pytest

import main
from function_module.logger import configurar_logging
from tests.apoio import CONSENTIMENTO, evento


def test_logs_nao_contem_dados_do_evento(
    caplog: pytest.LogCaptureFixture, registro: dict[str, Any]
) -> None:
    caplog.set_level(logging.INFO, logger="prumo.api")
    main.handler(evento("PUT", "/perfil", CONSENTIMENTO, "identidade-privada"))
    requisicao = evento("PUT", "/dias/2026-11-23", registro, "identidade-privada")
    requisicao["headers"]["authorization"] = "Bearer token-privado"
    assert main.handler(requisicao)["statusCode"] == 200
    assert "identidade-privada" not in caplog.text
    assert "token-privado" not in caplog.text
    assert "sono_horas" not in caplog.text
    assert "2026-11-23" not in caplog.text
    for linha in caplog.records:
        campos = json.loads(linha.message)
        assert set(campos) == {"evento", "status", "duracao_ms", "tipo_erro"}
        assert campos["duracao_ms"] >= 0


@pytest.mark.parametrize("falha,status", [(RuntimeError, 500), (sqlite3.OperationalError, 503)])
def test_falha_nao_expoe_mensagem_ou_traceback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    falha: type[Exception],
    status: int,
) -> None:
    def falhar(event: dict[str, Any]) -> dict[str, Any]:
        raise falha("dado-sensivel-que-nao-pode-vazar")

    monkeypatch.setattr(main, "encaminhar", falhar)
    retorno = main.handler(evento("GET", "/health"))
    assert retorno["statusCode"] == status
    assert "dado-sensivel" not in retorno["body"]
    assert "dado-sensivel" not in caplog.text
    assert all(linha.exc_info is None for linha in caplog.records)


def test_logging_nao_duplica_handlers_nem_altera_logger_raiz() -> None:
    logger = logging.getLogger("prumo")
    estado = logger.handlers[:], logger.level, logger.propagate
    raiz = logging.getLogger()
    estado_raiz = raiz.handlers[:], raiz.level
    try:
        configurar_logging()
        configurar_logging()
        assert len(logger.handlers) == 1
        assert (raiz.handlers, raiz.level) == estado_raiz
    finally:
        for saida in logger.handlers:
            if saida not in estado[0]:
                saida.close()
        logger.handlers, logger.level, logger.propagate = estado
