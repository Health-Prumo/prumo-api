"""Casos de uso do protótipo local."""

from datetime import UTC, datetime
from typing import Any

from function_module.errors import ErroAPI
from function_module.io.llm import gerar_card_mock
from function_module.io.repositorio import Repositorio
from function_module.logic.functions import analisar_dia


class ServicoPrumo:
    def __init__(self, repositorio: Repositorio) -> None:
        self.repositorio = repositorio

    def salvar_perfil(self, usuario: str, perfil: dict[str, Any]) -> dict[str, Any]:
        perfil = {**perfil, "consentimento_em": datetime.now(UTC).isoformat()}
        self.repositorio.salvar(usuario, "PERFIL", perfil)
        return perfil

    def _exigir_consentimento(self, usuario: str) -> None:
        perfil = self.repositorio.obter(usuario, "PERFIL")
        if not perfil or perfil.get("consentimento") is not True:
            raise ErroAPI(
                403, "consentimento_necessario", "Registre o consentimento em PUT /perfil."
            )

    def _dias(self, usuario: str) -> list[dict[str, Any]]:
        return [
            dados for chave, dados in self.repositorio.listar(usuario) if chave.startswith("DIA#")
        ]

    def _apresentar(self, dia: dict[str, Any], dias: list[dict[str, Any]]) -> dict[str, Any]:
        return {**dia, **analisar_dia(dia, dias), "card": gerar_card_mock()}

    def salvar_dia(self, usuario: str, data_dia: str, registro: dict[str, Any]) -> dict[str, Any]:
        self._exigir_consentimento(usuario)
        dia = {
            "data": data_dia,
            "registro": registro,
            "nota": None,
            "status_avaliacao": "regras_pendentes",
        }
        self.repositorio.salvar(usuario, f"DIA#{data_dia}", dia)
        return self._apresentar(dia, self._dias(usuario))

    def obter_dia(self, usuario: str, data_dia: str) -> dict[str, Any]:
        dia = self.repositorio.obter(usuario, f"DIA#{data_dia}")
        if dia is None:
            raise ErroAPI(404, "dia_nao_encontrado", "Nenhum registro encontrado para esta data.")
        return self._apresentar(dia, self._dias(usuario))

    def historico(self, usuario: str, inicio: str, fim: str) -> dict[str, Any]:
        dias = self._dias(usuario)
        return {
            "dias": [self._apresentar(dia, dias) for dia in dias if inicio <= dia["data"] <= fim]
        }

    def exportar(self, usuario: str) -> dict[str, Any]:
        return {
            "itens": [
                {"chave": chave, "dados": dados}
                for chave, dados in self.repositorio.listar(usuario)
            ]
        }

    def apagar(self, usuario: str) -> None:
        self.repositorio.apagar(usuario)
