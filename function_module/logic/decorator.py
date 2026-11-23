"""Fronteira do handler: respostas de erro e telemetria operacional mínima."""

import sqlite3
from collections.abc import Callable
from functools import wraps
from time import monotonic
from typing import Any

from marshmallow import ValidationError

from function_module.errors import ErroAPI
from function_module.io.http import resposta
from function_module.logger import registrar_execucao

FuncaoLambda = Callable[..., dict[str, Any]]


def aws_lambda(funcao: FuncaoLambda) -> FuncaoLambda:
    """Mantém o envelope HTTP e nunca registra dados de entrada ou de saída."""

    @wraps(funcao)
    def executar(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        inicio = monotonic()
        tipo_erro = None
        try:
            retorno = funcao(event, context)
        except ErroAPI as erro:
            tipo_erro = type(erro).__name__
            retorno = resposta(
                erro.status, {"erro": {"codigo": erro.codigo, "mensagem": str(erro)}}
            )
        except ValidationError as erro:
            tipo_erro = type(erro).__name__
            retorno = resposta(422, {"erro": {"codigo": "validacao", "campos": erro.messages}})
        except (ValueError, sqlite3.Error, OSError) as erro:
            tipo_erro = type(erro).__name__
            retorno = resposta(
                503, {"erro": {"codigo": "indisponivel", "mensagem": "Serviço indisponível."}}
            )
        except Exception as erro:
            # A fronteira HTTP responde 500 sem vazar mensagens ou traceback ao cliente/log.
            tipo_erro = type(erro).__name__
            retorno = resposta(
                500, {"erro": {"codigo": "erro_interno", "mensagem": "Erro interno do servidor."}}
            )
        registrar_execucao(retorno["statusCode"], (monotonic() - inicio) * 1000, tipo_erro)
        return retorno

    return executar
