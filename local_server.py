"""Adaptador Flask de desenvolvimento: todas as rotas passam por main.handler."""

import base64
import logging
from typing import Any
from urllib.parse import parse_qs

from dotenv import load_dotenv
from flask import Flask, Response, request
from werkzeug.exceptions import RequestEntityTooLarge

from function_module.io.http import LIMITE_CORPO, resposta
from function_module.logger import configurar_logging
from function_module.settings import RAIZ, carregar_configuracao
from main import handler


def criar_app() -> Flask:
    load_dotenv(RAIZ / ".env", override=False)
    config = carregar_configuracao()
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=LIMITE_CORPO, TRUSTED_HOSTS=["localhost", "127.0.0.1"])

    def converter(retorno: dict[str, Any]) -> Response:
        return Response(retorno["body"], status=retorno["statusCode"], headers=retorno["headers"])

    @app.errorhandler(RequestEntityTooLarge)
    def corpo_grande(erro: RequestEntityTooLarge) -> Response:
        return converter(resposta(413, {"erro": {"codigo": "corpo_muito_grande"}}))

    @app.after_request
    def cors(retorno: Response) -> Response:
        if request.headers.get("Origin") == config.origem_front:
            retorno.headers["Access-Control-Allow-Origin"] = config.origem_front
            retorno.headers["Access-Control-Allow-Methods"] = "GET, PUT, DELETE, OPTIONS"
            retorno.headers["Access-Control-Allow-Headers"] = "Content-Type"
            retorno.vary.add("Origin")
        return retorno

    @app.route(
        "/", defaults={"caminho": ""}, methods=["GET", "PUT", "POST", "DELETE", "PATCH", "OPTIONS"]
    )
    @app.route("/<path:caminho>", methods=["GET", "PUT", "POST", "DELETE", "PATCH", "OPTIONS"])
    def encaminhar_http(caminho: str) -> Response:
        origem = request.headers.get("Origin")
        if origem and origem != config.origem_front:
            return converter(resposta(403, {"erro": {"codigo": "origem_nao_permitida"}}))
        consulta = request.query_string.decode("utf-8", errors="replace")
        parametros = parse_qs(consulta, keep_blank_values=True)
        evento = {
            "version": "2.0",
            "rawPath": f"/{caminho}",
            "rawQueryString": consulta,
            "queryStringParameters": {
                chave: ",".join(valores) for chave, valores in parametros.items()
            },
            "headers": {chave.lower(): valor for chave, valor in request.headers.items()},
            "requestContext": {
                "http": {"method": request.method, "path": f"/{caminho}"},
                "authorizer": {"jwt": {"claims": {"sub": config.usuario_local}}},
            },
            "body": base64.b64encode(request.get_data()).decode("ascii"),
            "isBase64Encoded": True,
        }
        return converter(handler(evento, None))

    return app


def executar() -> None:
    """Inicia apenas o servidor de desenvolvimento."""
    configurar_logging()
    aplicacao = criar_app()
    # Evita logs de URLs com datas e parâmetros de saúde no servidor local.
    logging.getLogger("werkzeug").disabled = True
    print("Prumo local em http://localhost:" + str(carregar_configuracao().porta))
    aplicacao.run(
        host=carregar_configuracao().host_local,
        port=carregar_configuracao().porta,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    executar()
