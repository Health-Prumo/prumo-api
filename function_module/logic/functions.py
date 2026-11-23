"""Cálculos puros sobre registros; nenhuma chamada externa ou nota inventada."""

from datetime import date
from statistics import mean
from typing import Any

CAMPOS_NUMERICOS = (
    "sono_horas",
    "sono_qualidade",
    "atividade_minutos",
    "agua_litros",
    "humor",
    "energia",
    "tela_lazer_horas",
)


def resumir_historico(data_dia: str, dias: list[dict[str, Any]]) -> dict[str, Any]:
    """Usa sete dias de calendário anteriores, sem preencher lacunas com zero."""
    referencia = date.fromisoformat(data_dia)
    inicio = max(date.min.toordinal(), referencia.toordinal() - 7)
    anteriores = [
        dia for dia in dias if date.fromordinal(inicio).isoformat() <= dia["data"] < data_dia
    ]
    return {
        "dias_registrados": len(anteriores),
        "medias": {
            campo: round(mean(dia["registro"][campo] for dia in anteriores), 2)
            for campo in CAMPOS_NUMERICOS
        }
        if anteriores
        else {},
    }


def analisar_dia(dia: dict[str, Any], historico: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "nota": None,
        "status_avaliacao": "regras_pendentes",
        "motivo": "As fórmulas e os pesos da nota aguardam definição do grupo.",
        "resumo_historico": resumir_historico(dia["data"], historico),
    }
