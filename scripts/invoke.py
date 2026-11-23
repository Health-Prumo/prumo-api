"""Invoca um evento JSON local usando o mesmo handler da API."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from function_module.settings import RAIZ
from main import handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", nargs="?", default="examples/evento-health.json", type=Path)
    argumentos = parser.parse_args()
    caminho = argumentos.arquivo
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    load_dotenv(RAIZ / ".env", override=False)
    try:
        evento = json.loads(caminho.read_text(encoding="utf-8-sig"))
        if not isinstance(evento, dict):
            raise ValueError("O evento precisa ser um objeto JSON.")
    except (OSError, ValueError) as erro:
        parser.error(f"Não foi possível ler um evento JSON: {type(erro).__name__}.")
    retorno = handler(evento)
    print(json.dumps(retorno, ensure_ascii=False, indent=2))
    return 0 if retorno["statusCode"] < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
