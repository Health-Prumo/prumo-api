"""Leitura e escrita do contrato API Gateway HTTP API 2.0."""

import base64
import binascii
import json
from typing import Any

from function_module.errors import ErroAPI

LIMITE_CORPO = 65_536


def resposta(status: int, dados: Any = None) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
        },
        "body": "" if status == 204 else json.dumps(dados, ensure_ascii=False, allow_nan=False),
        "isBase64Encoded": False,
    }


def rejeitar_constante(valor: str) -> None:
    raise ValueError("Constante JSON inválida.")


def ler_corpo(evento: dict[str, Any]) -> dict[str, Any]:
    cabecalhos = {chave.lower(): valor for chave, valor in (evento.get("headers") or {}).items()}
    if cabecalhos.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise ErroAPI(415, "tipo_nao_suportado", "Use Content-Type: application/json.")
    corpo = evento.get("body") or ""
    if not isinstance(corpo, str):
        raise ErroAPI(400, "json_invalido", "O corpo deve ser um objeto JSON.")
    if len(corpo.encode("utf-8")) > LIMITE_CORPO * 2:
        raise ErroAPI(413, "corpo_muito_grande", "O corpo excede 64 KiB.")
    try:
        conteudo = (
            base64.b64decode(corpo, validate=True)
            if evento.get("isBase64Encoded")
            else corpo.encode("utf-8")
        )
        if len(conteudo) > LIMITE_CORPO:
            raise ErroAPI(413, "corpo_muito_grande", "O corpo excede 64 KiB.")
        dados = json.loads(conteudo.decode("utf-8"), parse_constant=rejeitar_constante)
    except (ValueError, UnicodeError, binascii.Error, RecursionError) as erro:
        raise ErroAPI(400, "json_invalido", "Envie um objeto JSON válido em UTF-8.") from erro
    if not isinstance(dados, dict):
        raise ErroAPI(400, "json_invalido", "O corpo deve ser um objeto JSON.")
    return dados


def identificar_usuario(evento: dict[str, Any]) -> str:
    contexto = evento.get("requestContext") or {}
    usuario = (contexto.get("authorizer") or {}).get("jwt", {}).get("claims", {}).get("sub")
    if not isinstance(usuario, str) or not usuario.strip() or len(usuario) > 128:
        raise ErroAPI(401, "nao_autenticado", "Identidade do usuário não encontrada.")
    return usuario
