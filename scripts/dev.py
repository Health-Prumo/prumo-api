"""Uma definição de comandos para PowerShell, Bash e GitHub Actions."""

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ALVOS = ["main.py", "local_server.py", "servidor_local.py", "function_module"]


def comandos(acao: str, argumentos: list[str]) -> list[list[str]]:
    verificar = [
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "mypy"],
        ["-m", "bandit", "-c", "pyproject.toml", "-r", *ALVOS],
    ]
    opcoes = {
        "run": [["local_server.py"]],
        "test": [["-m", "pytest", "--cov", "--cov-report=term-missing", *argumentos]],
        "check": verificar,
        "format": [
            ["-m", "ruff", "format", "."],
            ["-m", "ruff", "check", "--fix", "."],
            *verificar,
        ],
        "audit": [["-m", "pip_audit", "-r", "requirements/development.txt"]],
        "event": [["-m", "scripts.invoke", *argumentos]],
    }
    return opcoes[acao]


def executar(acao: str, argumentos: list[str]) -> int:
    for comando in comandos(acao, argumentos):
        resultado = subprocess.run([sys.executable, *comando], cwd=RAIZ, check=False)
        if resultado.returncode:
            return resultado.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acao", choices=["run", "test", "check", "format", "audit", "event"])
    parametros, argumentos = parser.parse_known_args()
    if argumentos and parametros.acao not in {"test", "event"}:
        parser.error("Argumentos adicionais são aceitos somente em test e event.")
    if sys.version_info[:2] != (3, 12):
        parser.error("Use o Python 3.12 definido pelo projeto.")
    return executar(parametros.acao, argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
