from __future__ import annotations

import itertools
import json
from datetime import date
from typing import Any

import pytest

from prumo_api import handler as api
from prumo_api import regras
from prumo_api.ia import MAX_TOKENS, Coach, analise_mock, contexto_do_dia, tem_sinal_de_alerta, validar_analise
from tests.conftest import USUARIO, Chamar, registro

HOJE = date(2026, 11, 24)


class Gravador:
    """Substitui o Bedrock: guarda o que seria enviado e devolve uma resposta pronta."""

    def __init__(self, resposta: str) -> None:
        self.resposta = resposta
        self.chamadas: list[tuple[str, list[dict[str, Any]]]] = []

    def __call__(self, sistema: str, mensagens: list[dict[str, Any]]) -> str:
        self.chamadas.append((sistema, mensagens))
        return self.resposta


RESPOSTA_OK = json.dumps(
    {
        "titulo": "Dia bom, com o sono pedindo atenção.",
        "resumo": "Seu sono ficou em 5h30, abaixo da faixa de 7 a 9 h.",
        "sugestoes": [{"habito": "sono", "titulo": "Durma 30 min mais cedo", "detalhe": "Celular fora do quarto."}],
    },
    ensure_ascii=False,
)


def notas(**alteracoes: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    r = registro(**alteracoes)
    return r, regras.calcular(r, "feminino", {}, HOJE)


def test_mock_e_deterministico_e_prioriza_o_pior_habito() -> None:
    r, n = notas(sono_horas=4, tela_horas=5, atividade_minutos=150)
    primeira = analise_mock(r, n)
    assert analise_mock(r, n) == primeira
    assert [s["habito"] for s in primeira["sugestoes"]] == ["tela", "sono"]
    assert primeira["fonte"] == "mock"


def test_mock_dia_equilibrado() -> None:
    r, n = notas(atividade_minutos=200, agua_litros=2.5, humor=5, tela_horas=0)
    analise = analise_mock(r, n)
    assert analise["titulo"] == "Um dia equilibrado, siga assim."
    assert len(analise["sugestoes"]) == 1


def test_bedrock_usa_resposta_valida() -> None:
    gravador = Gravador(f"```json\n{RESPOSTA_OK}\n```")
    r, n = notas(sono_horas=5.5)
    analise = Coach("bedrock", gravador).analisar_dia(r, n)
    assert analise["fonte"] == "bedrock"
    assert analise["sugestoes"][0]["habito"] == "sono"


@pytest.mark.parametrize(
    "resposta",
    [
        "não sei responder",
        json.dumps({"titulo": "x", "resumo": "y", "sugestoes": []}),
        json.dumps({"titulo": "x", "resumo": "y", "sugestoes": [{"habito": "cafe", "titulo": "a", "detalhe": "b"}]}),
        json.dumps(
            {"titulo": "x", "resumo": "y", "sugestoes": [{"habito": "sono", "titulo": "a", "detalhe": "b"}] * 3}
        ),
    ],
)
def test_bedrock_resposta_invalida_cai_no_mock(resposta: str) -> None:
    r, n = notas(sono_horas=5.5)
    assert Coach("bedrock", Gravador(resposta)).analisar_dia(r, n) == analise_mock(r, n)


def test_bedrock_com_erro_cai_no_mock() -> None:
    def quebrado(_s: str, _m: list[dict[str, Any]]) -> str:
        raise RuntimeError("sem rede")

    r, n = notas()
    assert Coach("bedrock", quebrado).analisar_dia(r, n)["fonte"] == "mock"


def test_validar_analise_limita_tamanho() -> None:
    with pytest.raises(ValueError):
        validar_analise({"titulo": "x" * 500, "resumo": "y", "sugestoes": []})


def test_contexto_so_tem_numeros_e_rotulos() -> None:
    r, n = notas()
    contexto = contexto_do_dia(r, n)

    def folhas(valor: Any) -> list[Any]:
        if isinstance(valor, dict):
            return [f for v in valor.values() for f in folhas(v)]
        return [valor]

    for folha in folhas(contexto):
        assert folha is None or isinstance(folha, (int, float, bool, str))
    textos = [f for f in folhas(contexto) if isinstance(f, str)]
    assert all("@" not in t for t in textos)


@pytest.mark.usefixtures("com_perfil")
def test_prompt_enviado_ao_llm_nao_tem_identificadores(chamar: Chamar) -> None:
    gravador = Gravador(RESPOSTA_OK)
    api.configurar(repo=api.repo(), coach=Coach("bedrock", gravador))
    hoje = api.hoje_local().isoformat()
    assert chamar("PUT", f"/dias/{hoje}", registro())[0] == 200
    assert chamar("POST", "/chat", {"mensagem": "Como foi minha semana?"})[0] == 200
    assert len(gravador.chamadas) == 2
    for sistema, mensagens in gravador.chamadas:
        enviado = sistema + json.dumps(mensagens, ensure_ascii=False)
        assert USUARIO not in enviado
        assert "USUARIO#" not in enviado
        assert "pessoa@exemplo.com" not in enviado
        assert "@" not in enviado


def test_chat_resume_historico_e_respeita_papeis() -> None:
    gravador = Gravador("Tudo certo.")
    conversa = [
        {"papel": "coach", "texto": "Olá"},
        {"papel": "usuario", "texto": "oi"},
        {"papel": "coach", "texto": "Como posso ajudar?"},
    ]
    resposta, fonte = Coach("bedrock", gravador).responder("E o sono?", {"dias_registrados": 0}, conversa)
    assert (resposta, fonte) == ("Tudo certo.", "bedrock")
    mensagens = gravador.chamadas[0][1]
    assert mensagens[0]["role"] == "user"
    assert mensagens[-1]["role"] == "user"
    papeis = [m["role"] for m in mensagens]
    assert all(a != b for a, b in itertools.pairwise(papeis))


def test_sinal_de_alerta_nao_chama_llm() -> None:
    gravador = Gravador("não deveria")
    resposta, _ = Coach("bedrock", gravador).responder("tive falta de ar", {}, [])
    assert "profissional de saúde" in resposta
    assert gravador.chamadas == []
    assert tem_sinal_de_alerta("Pensei em suicídio")
    assert not tem_sinal_de_alerta("dormi pouco")


def test_limite_de_tokens() -> None:
    assert MAX_TOKENS == 400


def test_modo_invalido() -> None:
    with pytest.raises(RuntimeError):
        Coach("openai")


def test_resumo_mock_preserva_siglas() -> None:
    from prumo_api.ia import _minuscula_inicial

    assert _minuscula_inicial("Faltam 115 min para a meta semanal da OMS") == (
        "faltam 115 min para a meta semanal da OMS"
    )
