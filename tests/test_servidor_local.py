"""O adaptador HTTP preserva as respostas e a identidade fixada pelo servidor."""

import json
from typing import Any

from flask.testing import FlaskClient

from local_server import criar_app
from main import handler
from tests.apoio import CONSENTIMENTO, evento


def test_http_equivale_ao_handler(cliente: FlaskClient, registro: dict[str, Any]) -> None:
    assert cliente.get("/health").json == json.loads(handler(evento("GET", "/health"))["body"])
    assert cliente.put("/perfil", json=CONSENTIMENTO).status_code == 200
    retorno = cliente.put("/dias/2026-11-23", json=registro)
    assert retorno.status_code == 200
    assert retorno.json == json.loads(handler(evento("GET", "/dias/2026-11-23"))["body"])
    # Uma nova aplicação lê o mesmo banco em disco.
    novo_cliente = criar_app().test_client()
    assert novo_cliente.get("/dias/2026-11-23").json == retorno.json
    assert novo_cliente.get("/historico?inicio=2026-11-23&fim=2026-11-23").json["dias"] == [
        retorno.json
    ]
    assert novo_cliente.delete("/dados").status_code == 204


def test_cors_e_origem(cliente: FlaskClient) -> None:
    origem = {"Origin": "http://localhost:5173"}
    retorno = cliente.options("/perfil", headers={**origem, "Access-Control-Request-Method": "PUT"})
    assert retorno.status_code == 204
    assert retorno.headers["Access-Control-Allow-Origin"] == origem["Origin"]
    assert "Content-Type" in retorno.headers["Access-Control-Allow-Headers"]
    rejeitado = cliente.put("/perfil", json=CONSENTIMENTO, headers={"Origin": "https://outro.test"})
    assert rejeitado.status_code == 403
    assert "Access-Control-Allow-Origin" not in rejeitado.headers
    assert cliente.get("/health", headers={"Host": "outro.test"}).status_code == 400


def test_usuario_nao_vem_de_header(cliente: FlaskClient, registro: dict[str, Any]) -> None:
    cliente.put("/perfil", json=CONSENTIMENTO)
    cliente.put("/dias/2026-11-23", json=registro, headers={"X-User-Id": "invasor"})
    assert handler(evento("GET", "/dias/2026-11-23", usuario="invasor"))["statusCode"] == 404


def test_erros_http(cliente: FlaskClient) -> None:
    assert cliente.put("/perfil", data="{}").status_code == 415
    assert cliente.put("/perfil", data="{", content_type="application/json").status_code == 400
    assert (
        cliente.put("/perfil", data="x" * 70_000, content_type="application/json").status_code
        == 413
    )
    assert cliente.get("/historico?inicio=2026-11-23&inicio=2026-11-24").status_code == 422
