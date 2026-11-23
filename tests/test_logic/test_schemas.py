"""Valida limites, campos desconhecidos e tipos sem coerção silenciosa."""

from typing import Any

import pytest
from marshmallow import ValidationError

from function_module.logic.schemas import PerfilSchema, RegistroDiaSchema


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("sono_horas", -1),
        ("sono_horas", 25),
        ("sono_horas", True),
        ("agua_litros", "2.0"),
        ("agua_litros", float("nan")),
        ("agua_litros", float("inf")),
        ("humor", 0),
        ("energia", 6),
        ("energia", 2.5),
        ("sono_qualidade", None),
        ("atividade_minutos", 1441),
        ("atividade_intensidade", "intensa"),
        ("tela_lazer_horas", 25),
        ("usuario", "outro"),
        ("nota", 10),
    ],
)
def test_rejeita_entrada_invalida(registro: dict[str, Any], campo: str, valor: Any) -> None:
    registro[campo] = valor
    with pytest.raises(ValidationError):
        RegistroDiaSchema().load(registro)


def test_alimentacao_exige_booleanos(registro: dict[str, Any]) -> None:
    registro["alimentacao"]["frutas_verduras"] = "sim"
    with pytest.raises(ValidationError):
        RegistroDiaSchema().load(registro)


@pytest.mark.parametrize("valor", [False, "true", 1, None])
def test_consentimento_explicito(valor: Any) -> None:
    with pytest.raises(ValidationError):
        PerfilSchema().load({"consentimento": valor, "versao_termo": "prototipo-local-v1"})


def test_registro_completo_obrigatorio() -> None:
    with pytest.raises(ValidationError):
        RegistroDiaSchema().load({})
    with pytest.raises(ValidationError):
        RegistroDiaSchema().load([])
