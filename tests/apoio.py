"""Eventos equivalentes ao contrato HTTP API 2.0."""

import json
from typing import Any

CONSENTIMENTO = {"consentimento": True, "versao_termo": "prototipo-local-v1"}


def evento(
    metodo: str, caminho: str, corpo: Any = None, usuario: str = "usuario-teste"
) -> dict[str, Any]:
    return {
        "version": "2.0",
        "rawPath": caminho,
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {"method": metodo},
            "authorizer": {"jwt": {"claims": {"sub": usuario}}},
        },
        "body": json.dumps(corpo) if corpo is not None else "",
        "isBase64Encoded": False,
    }
