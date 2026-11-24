from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest

from prumo_api import regras
from tests.conftest import registro

HOJE = date(2026, 11, 24)


def anteriores(dias: int, **alteracoes: Any) -> dict[str, dict[str, Any]]:
    return {(HOJE - timedelta(days=i)).isoformat(): registro(**alteracoes) for i in range(1, dias + 1)}


def test_mesmos_dados_dao_sempre_a_mesma_nota() -> None:
    historico = anteriores(5, sono_horas=6.0)
    primeira = regras.calcular(registro(sono_horas=5.5), "feminino", historico, HOJE)
    for _ in range(20):
        assert (
            regras.calcular(registro(sono_horas=5.5), "feminino", json.loads(json.dumps(historico)), HOJE) == primeira
        )


def test_dia_ideal_da_nota_maxima() -> None:
    notas = regras.calcular(
        registro(atividade_minutos=150, agua_litros=2.5, humor=5, tela_horas=0.5), "masculino", {}, HOJE
    )
    assert notas["energia"] == 10.0
    assert all(h["situacao"] == "boa" for h in notas["habitos"].values())


@pytest.mark.parametrize(
    ("horas", "nota", "situacao"),
    [
        (8, 10.0, "boa"),
        (7, 10.0, "boa"),
        (9, 10.0, "boa"),
        (6.3, 9.0, "atencao"),
        (3.5, 5.0, "alerta"),
        (13.5, 5.0, "alerta"),
        (0, 0.0, "alerta"),
    ],
)
def test_sono_faixa_nsf(horas: float, nota: float, situacao: str) -> None:
    habito = regras.calcular(registro(sono_horas=horas), "feminino", {}, HOJE)["habitos"]["sono"]
    assert habito["nota"] == nota
    assert habito["situacao"] == situacao


def test_sono_compara_com_o_padrao_do_usuario() -> None:
    habito = regras.calcular(registro(sono_horas=5 + 40 / 60), "feminino", anteriores(7, sono_horas=6 + 40 / 60), HOJE)[
        "habitos"
    ]["sono"]
    assert habito["resumo"] == "Abaixo do seu padrão de 6h40"
    assert habito["media_7d"] == pytest.approx(6.67, abs=0.01)


def test_atividade_soma_7_dias_com_vigorosa_valendo_dobro() -> None:
    historico = anteriores(6, atividade_minutos=10, atividade_intensidade="vigorosa")  # 6 x 20 = 120
    habito = regras.calcular(registro(atividade_minutos=30), "feminino", historico, HOJE)["habitos"]["atividade"]
    assert habito["semana_min"] == 150
    assert habito["nota"] == 10.0
    assert habito["resumo"] == "Meta semanal da OMS atingida"


def test_atividade_ignora_dia_fora_da_janela() -> None:
    historico = {(HOJE - timedelta(days=7)).isoformat(): registro(atividade_minutos=300)}
    habito = regras.calcular(registro(atividade_minutos=0), "feminino", historico, HOJE)["habitos"]["atividade"]
    assert habito["semana_min"] == 0
    assert habito["resumo"] == "Faltam 150 min para a meta semanal da OMS"
    # mas o dia 7 entra na média de 7 dias
    assert habito["media_7d"] == 300


def test_atividade_leve_nao_soma_na_meta() -> None:
    habito = regras.calcular(registro(atividade_minutos=60, atividade_intensidade="leve"), "feminino", {}, HOJE)[
        "habitos"
    ]["atividade"]
    assert habito["semana_min"] == 0
    assert "não soma na meta" in habito["resumo"]


@pytest.mark.parametrize(
    ("sexo", "litros", "nota", "resumo"),
    [
        ("feminino", 1.6, 8.0, "Faltam 0,4 L para 2 L"),
        ("masculino", 2.5, 10.0, "Meta de 2,5 L atingida"),
        ("nao_informar", 1.0, 5.0, "Faltam 1 L para 2 L"),
        ("masculino", 5.0, 10.0, "Meta de 2,5 L atingida"),
    ],
)
def test_agua_efsa(sexo: str, litros: float, nota: float, resumo: str) -> None:
    habito = regras.calcular(registro(agua_litros=litros), sexo, {}, HOJE)["habitos"]["agua"]
    assert habito["nota"] == nota
    assert habito["resumo"] == resumo


@pytest.mark.parametrize(
    ("frutas", "caseira", "ultra", "nota"),
    [(True, True, False, 10.0), (True, True, True, 6.0), (False, False, False, 2.0), (False, False, True, 0.0)],
)
def test_alimentacao_guia(frutas: bool, caseira: bool, ultra: bool, nota: float) -> None:
    comida = {"frutas_verduras": frutas, "refeicao_caseira": caseira, "ultraprocessados": ultra}
    assert regras.calcular(registro(alimentacao=comida), "feminino", {}, HOJE)["habitos"]["alimentacao"]["nota"] == nota


@pytest.mark.parametrize(("humor", "nota"), [(1, 0.0), (3, 5.0), (5, 10.0)])
def test_humor(humor: int, nota: float) -> None:
    assert regras.calcular(registro(humor=humor), "feminino", {}, HOJE)["habitos"]["humor"]["nota"] == nota


@pytest.mark.parametrize(
    ("horas", "nota", "situacao"), [(0.5, 10.0, "boa"), (2.5, 7.0, "atencao"), (3, 6.0, "alerta"), (8, 0.0, "alerta")]
)
def test_tela_vigitel(horas: float, nota: float, situacao: str) -> None:
    habito = regras.calcular(registro(tela_horas=horas), "feminino", {}, HOJE)["habitos"]["tela"]
    assert habito["nota"] == nota
    assert habito["situacao"] == situacao


def test_energia_e_media_ponderada_com_pesos_iguais_por_padrao() -> None:
    notas = regras.calcular(registro(), "feminino", {}, HOJE)
    assert set(notas["pesos"].values()) == {1.0}
    esperado = sum(h["nota"] for h in notas["habitos"].values()) / 6
    assert notas["energia"] == regras.arredondar(esperado)


def test_pesos_configuraveis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "PRUMO_PESOS", json.dumps({"sono": 5, "atividade": 0, "agua": 0, "alimentacao": 0, "humor": 0, "tela": 0})
    )
    notas = regras.calcular(registro(sono_horas=3.5), "feminino", {}, HOJE)
    assert notas["energia"] == 5.0


def test_pesos_invalidos_falham(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_PESOS", json.dumps({"cafe": 2}))
    with pytest.raises(RuntimeError):
        regras.pesos()


def test_media_7d_sem_historico_e_nula() -> None:
    notas = regras.calcular(registro(), "feminino", {}, HOJE)
    assert all(h["media_7d"] is None for h in notas["habitos"].values())


@pytest.mark.parametrize(
    "alteracao",
    [
        {"sono_horas": 17},
        {"sono_horas": "8"},
        {"sono_qualidade": 2.5},
        {"atividade_intensidade": "intensa"},
        {"agua_litros": -1},
        {"humor": 0},
        {"humor": True},
        {"tela_horas": None},
        {"alimentacao": {"frutas_verduras": True}},
    ],
)
def test_validacao_rejeita_dados_invalidos(alteracao: dict[str, Any]) -> None:
    with pytest.raises(regras.ErroValidacao):
        regras.validar_registro(registro(**alteracao))


def test_validacao_aceita_e_normaliza() -> None:
    dados = regras.validar_registro({**registro(), "campo_extra": "ignorado"})
    assert "campo_extra" not in dados
    assert dados["humor"] == 4


def test_formatacao() -> None:
    assert regras.formatar_horas(5 + 40 / 60) == "5h40"
    assert regras.formatar_horas(7) == "7h"
    assert regras.formatar_numero(1.6) == "1,6"
    assert regras.formatar_numero(2.0) == "2"
    assert regras.arredondar(2.25) == 2.3
