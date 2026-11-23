"""Compatibilidade com o comando original; implementação em local_server.py."""

from local_server import criar_app, executar

__all__ = ["criar_app", "executar"]


if __name__ == "__main__":
    executar()
