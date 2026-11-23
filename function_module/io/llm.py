"""Card fixo do protótipo, sem rede, identificadores ou cálculo de nota."""

from typing import Any


def gerar_card_mock() -> dict[str, Any]:
    return {
        "modo": "mock",
        "titulo": "Seu dia",
        "texto": "Seu registro foi salvo. Acompanhe seu histórico para observar sua rotina.",
        "sugestoes": ["Reserve um momento amanhã para registrar como foi seu dia."],
        "aviso": "O Prumo não substitui orientação médica.",
    }
