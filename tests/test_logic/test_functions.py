"""Determinismo do resumo; nota permanece pendente até aprovação das regras."""

from copy import deepcopy
from typing import Any

from function_module.logic.functions import analisar_dia, resumir_historico


def test_media_usa_janela_calendario_e_nao_imputa_zeros(registro: dict[str, Any]) -> None:
    dias = [
        {"data": data, "registro": {**registro, "sono_horas": horas}}
        for data, horas in [
            ("2026-11-15", 1),
            ("2026-11-16", 6),
            ("2026-11-22", 8),
            ("2026-11-23", 20),
            ("2026-11-24", 22),
        ]
    ]
    original = deepcopy(dias)
    resumo = resumir_historico("2026-11-23", dias)
    assert resumo["dias_registrados"] == 2
    assert resumo["medias"]["sono_horas"] == 7
    dia = dias[3]
    assert analisar_dia(dia, dias) == analisar_dia(dia, list(reversed(dias)))
    assert analisar_dia(dia, dias)["nota"] is None
    assert dias == original


def test_sem_historico_e_data_minima() -> None:
    assert resumir_historico("0001-01-01", []) == {"dias_registrados": 0, "medias": {}}
