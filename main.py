"""Entrada fina da Lambda; o adaptador local chama exatamente o mesmo handler."""

from typing import Any

from function_module.api import encaminhar
from function_module.logic.decorator import aws_lambda


@aws_lambda
def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Encaminha o evento para as rotas do Prumo."""
    return encaminhar(event)


# Preserva o contrato usado pelo front local e pelos eventos HTTP API 2.0.
handler = lambda_handler
