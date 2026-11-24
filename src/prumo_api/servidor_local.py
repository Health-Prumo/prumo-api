"""Servidor local: monta o evento do API Gateway (payload 2.0) e chama o mesmo handler da Lambda.

Uso: python -m prumo_api.servidor_local  (porta 8000; PRUMO_PORTA muda)
"""

from __future__ import annotations

import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from prumo_api import handler as api


def montar_evento(metodo: str, alvo: str, cabecalhos: dict[str, str], corpo: bytes) -> dict[str, Any]:
    partes = urlsplit(alvo)
    return {
        "version": "2.0",
        "rawPath": partes.path,
        "rawQueryString": partes.query,
        "queryStringParameters": dict(parse_qsl(partes.query)) or None,
        "headers": {k.lower(): v for k, v in cabecalhos.items()},
        "body": corpo.decode("utf-8") if corpo else None,
        "isBase64Encoded": False,
        "requestContext": {"http": {"method": metodo, "path": partes.path}},
    }


class Manipulador(BaseHTTPRequestHandler):
    server_version = "prumo-local"

    def _atender(self) -> None:
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tamanho) if tamanho else b""
        evento = montar_evento(self.command, self.path, dict(self.headers.items()), corpo)
        resposta = api.handler(evento)
        dados = resposta.get("body", "").encode("utf-8")
        self.send_response(resposta["statusCode"])
        for chave, valor in resposta.get("headers", {}).items():
            self.send_header(chave, valor)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        if dados:
            self.wfile.write(dados)

    do_GET = do_PUT = do_POST = do_DELETE = do_OPTIONS = _atender

    def log_message(self, formato: str, *args: Any) -> None:  # o handler já registra cada chamada
        return


def main() -> None:
    os.environ.setdefault("PRUMO_AUTH", "local")
    os.environ.setdefault("PRUMO_IA", "mock")
    os.environ.setdefault("PRUMO_ORIGENS", "http://localhost:5173")
    os.environ.setdefault("PRUMO_ARQUIVO_LOCAL", ".dados-locais.json")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    porta = int(os.environ.get("PRUMO_PORTA", "8000"))
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    print(f"Prumo API local em http://localhost:{porta} (IA: {os.environ['PRUMO_IA']})")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
