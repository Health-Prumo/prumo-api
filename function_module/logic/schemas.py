"""Contrato JSON do protótipo; limites de entrada não são metas de saúde."""

import re
from datetime import date
from typing import Any

from marshmallow import RAISE, Schema, ValidationError, fields, pre_load, validate


class BaseSchema(Schema):
    class Meta:
        unknown = RAISE

    error_messages = {"unknown": "Campo desconhecido.", "type": "Envie um objeto JSON."}

    @pre_load
    def verificar_tipos(self, dados: Any, **kwargs: Any) -> Any:
        """Evita coerção silenciosa de strings e booleanos em números."""
        if not isinstance(dados, dict):
            raise ValidationError("Envie um objeto JSON.")
        for nome, campo in self.fields.items():
            if nome not in dados:
                continue
            valor = dados[nome]
            if isinstance(campo, fields.Integer) and type(valor) is not int:
                raise ValidationError({nome: ["Informe um número inteiro."]})
            if isinstance(campo, fields.Float) and type(valor) not in {int, float}:
                raise ValidationError({nome: ["Informe um número."]})
            if isinstance(campo, fields.Boolean) and type(valor) is not bool:
                raise ValidationError({nome: ["Informe true ou false."]})
        return dados


ERROS: dict[str, str | list[Any] | dict[Any, Any]] = {
    "required": "Campo obrigatório.",
    "null": "O campo não pode ser nulo.",
}


def faixa(minimo: float, maximo: float) -> validate.Range:
    return validate.Range(min=minimo, max=maximo, error=f"Use um valor entre {minimo} e {maximo}.")


class AlimentacaoSchema(BaseSchema):
    frutas_verduras = fields.Boolean(required=True, error_messages=ERROS)
    refeicao_caseira = fields.Boolean(required=True, error_messages=ERROS)
    ultraprocessados = fields.Boolean(required=True, error_messages=ERROS)


class RegistroDiaSchema(BaseSchema):
    sono_horas = fields.Float(required=True, validate=faixa(0, 24), error_messages=ERROS)
    sono_qualidade = fields.Integer(required=True, validate=faixa(1, 5), error_messages=ERROS)
    atividade_minutos = fields.Integer(required=True, validate=faixa(0, 1440), error_messages=ERROS)
    atividade_intensidade = fields.String(
        required=True,
        validate=validate.OneOf(
            ["leve", "moderada", "vigorosa"], error="Use leve, moderada ou vigorosa."
        ),
        error_messages=ERROS,
    )
    agua_litros = fields.Float(required=True, validate=faixa(0, 20), error_messages=ERROS)
    alimentacao = fields.Nested(AlimentacaoSchema, required=True, error_messages=ERROS)
    humor = fields.Integer(required=True, validate=faixa(1, 5), error_messages=ERROS)
    energia = fields.Integer(required=True, validate=faixa(1, 5), error_messages=ERROS)
    tela_lazer_horas = fields.Float(required=True, validate=faixa(0, 24), error_messages=ERROS)


class PerfilSchema(BaseSchema):
    consentimento = fields.Boolean(
        required=True,
        validate=validate.Equal(True, error="É necessário consentimento para registrar hábitos."),
        error_messages=ERROS,
    )
    versao_termo = fields.String(
        required=True,
        validate=validate.Equal("prototipo-local-v1", error="Versão do termo não reconhecida."),
        error_messages=ERROS,
    )


def validar_data(valor: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ValidationError({"data": ["Use uma data válida no formato AAAA-MM-DD."]})
    try:
        return date.fromisoformat(valor)
    except ValueError as erro:
        raise ValidationError({"data": ["Data inexistente."]}) from erro
