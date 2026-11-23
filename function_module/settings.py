"""Configuração por ambiente; nunca armazena valores reais de segredos."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parent.parent
# Escuta interna do container; o Compose publica a porta apenas no loopback da máquina.
HOST_CONTAINER = "0.0.0.0"  # nosec B104


@dataclass(frozen=True)
class Configuracao:
    ambiente: str
    banco_local: Path
    usuario_local: str
    origem_front: str
    porta: int
    host_local: str


def carregar_configuracao() -> Configuracao:
    """Falha explicitamente em modos que o protótipo ainda não implementa."""
    ambiente = os.getenv("PRUMO_AMBIENTE", "local")
    if ambiente not in {"local", "teste"} or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        raise ValueError("O adaptador DynamoDB precisa ser implementado antes do deploy na AWS.")
    if os.getenv("PRUMO_LLM_MODO", "mock") != "mock":
        raise ValueError("Este protótipo suporta somente PRUMO_LLM_MODO=mock.")
    usuario = os.getenv("PRUMO_USUARIO_LOCAL", "usuario-demo").strip()
    if not usuario or len(usuario) > 128:
        raise ValueError("PRUMO_USUARIO_LOCAL deve ter entre 1 e 128 caracteres.")
    origem = os.getenv("PRUMO_ORIGEM_FRONT", "http://localhost:5173").rstrip("/")
    url = urlsplit(origem)
    if (
        url.scheme != "http"
        or url.hostname not in {"localhost", "127.0.0.1"}
        or not url.port
        or url.path
        or url.query
        or url.fragment
        or url.username
        or url.password
    ):
        raise ValueError("PRUMO_ORIGEM_FRONT deve ser uma origem HTTP de loopback com porta.")
    porta = int(os.getenv("PRUMO_PORTA", "8000"))
    if not 1 <= porta <= 65535:
        raise ValueError("PRUMO_PORTA deve estar entre 1 e 65535.")
    host_local = os.getenv("PRUMO_HOST_LOCAL", "127.0.0.1")
    if host_local not in {"127.0.0.1", HOST_CONTAINER}:
        raise ValueError("PRUMO_HOST_LOCAL deve ser 127.0.0.1 ou 0.0.0.0 (Docker local).")
    caminho = Path(os.getenv("PRUMO_BANCO_LOCAL", ".local/prumo.sqlite3"))
    return Configuracao(
        ambiente=ambiente,
        banco_local=caminho if caminho.is_absolute() else RAIZ / caminho,
        usuario_local=usuario,
        origem_front=origem,
        porta=porta,
        host_local=host_local,
    )
