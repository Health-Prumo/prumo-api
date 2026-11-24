"""Leitura das metas oficiais e dos parâmetros provisórios (data/referencias.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def carregar() -> dict[str, Any]:
    """Devolve o conteúdo de referencias.json (lido uma vez por processo)."""
    texto = resources.files("prumo_api").joinpath("data/referencias.json").read_text("utf-8")
    dados: dict[str, Any] = json.loads(texto)
    return dados


def metas() -> dict[str, Any]:
    resultado: dict[str, Any] = carregar()["metas"]
    return resultado


def parametros() -> dict[str, Any]:
    resultado: dict[str, Any] = carregar()["parametros_provisorios"]
    return resultado
