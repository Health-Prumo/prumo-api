"""Os comandos de qualidade devem interromper na primeira falha."""

import subprocess
from pathlib import Path

import pytest

from scripts import dev


def test_verificacao_interrompe_na_primeira_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas = []

    def simular(comando: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        chamadas.append(comando)
        assert cwd == dev.RAIZ
        return subprocess.CompletedProcess(comando, 2)

    monkeypatch.setattr(dev.subprocess, "run", simular)
    assert dev.executar("check", []) == 2
    assert len(chamadas) == 1


def test_entrada_antiga_preserva_factory() -> None:
    from local_server import criar_app
    from servidor_local import criar_app as criar_app_compativel

    assert criar_app is criar_app_compativel
