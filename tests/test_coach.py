"""Coach por regras: assunto reconhecido, uso dos números e previsibilidade (roteiro da apresentação)."""

from typing import Any

import pytest

from prumo_api.coach import AVISO, RESPOSTA_ALERTA, identificar_assunto, responder

RESUMO: dict[str, Any] = {
    "dias_registrados": 5,
    "energia_media": 5.4,
    "sono_medio_h": 5.75,
    "atividade_media_min_dia": 12,
    "agua_media_l": 1.2,
    "humor_medio_1a5": 3,
    "tela_media_h": 4.5,
    "notas_medias_0a10": {"sono": 6.1, "atividade": 3.5, "agua": 6, "alimentacao": 7, "humor": 5, "tela": 3},
    "habito_mais_baixo": "tela",
    "sono_qualidade_media": 2.6,
    "dias_frutas_verduras": 2,
    "dias_refeicao_caseira": 4,
    "dias_ultraprocessados": 3,
    "atividade_semana_min": 60,
    "meta_semana_min": 150,
    "meta_agua_l": 2.0,
    "pesos": {"sono": 1, "atividade": 1, "agua": 1, "alimentacao": 1, "humor": 1, "tela": 1},
    "ultimos_7_dias": [
        {"dia": -5, "energia": 7.0, "sono_h": 7.0, "tela_h": 3.0},
        {"dia": -4, "energia": 6.5, "sono_h": 6.5, "tela_h": 3.5},
        {"dia": -3, "energia": 5.0, "sono_h": 5.5, "tela_h": 5.0},
        {"dia": -2, "energia": 4.5, "sono_h": 5.0, "tela_h": 5.5},
        {"dia": -1, "energia": 4.0, "sono_h": 5.0, "tela_h": 5.5},
    ],
}
VAZIO: dict[str, Any] = {"dias_registrados": 0, "meta_agua_l": 2.0}

# Roteiro da apresentação: pergunta -> assunto esperado.
ROTEIRO = [
    ("Oi", "saudacao"),
    ("Como foi minha semana?", "semana"),
    ("Por que estou tão cansado?", "cansaco"),
    ("Dicas para dormir melhor", "sono"),
    ("Tem alguma ideia de um lanche bom da tarde? Algo saudável para chegar bem no jantar", "alimentacao"),
    ("Lanches saudáveis", "alimentacao"),
    ("Quanta água eu devo beber?", "agua"),
    ("Quanto falta para a meta da OMS?", "atividade"),
    ("Passo muito tempo no celular", "tela"),
    ("Estou me sentindo ansioso", "humor"),
    ("O que eu faço hoje para melhorar?", "hoje"),
    ("Como a minha nota é calculada?", "nota"),
    ("Posso tomar melatonina?", "prescricao"),
    ("Quero fazer uma dieta para emagrecer", "prescricao"),
    ("O que acontece com os meus dados?", "privacidade"),
    ("Quem é você?", "sobre"),
    ("Obrigado!", "agradecimento"),
    ("Qual a capital da França?", "fora"),
    ("Estou com dor no peito", "alerta"),
]


@pytest.mark.parametrize(("pergunta", "assunto"), ROTEIRO)
def test_roteiro_reconhece_o_assunto(pergunta: str, assunto: str) -> None:
    assert identificar_assunto(pergunta) == assunto


@pytest.mark.parametrize(("pergunta", "_assunto"), ROTEIRO)
@pytest.mark.parametrize("resumo", [RESUMO, VAZIO])
def test_roteiro_responde_sem_erro_e_e_deterministico(pergunta: str, _assunto: str, resumo: dict[str, Any]) -> None:
    primeira = responder(pergunta, resumo)
    assert primeira == responder(pergunta, resumo)
    assert 40 < len(primeira) < 1200
    assert "None" not in primeira and "{" not in primeira


def test_saudacao_com_pergunta_vale_a_pergunta() -> None:
    assert identificar_assunto("Oi, como melhorar meu sono?") == "sono"
    assert identificar_assunto("Bom dia! Dicas de lanche?") == "alimentacao"


def test_respostas_usam_os_numeros_do_usuario() -> None:
    assert "5h45" in responder("Dicas para dormir melhor", RESUMO)
    assert "60 de 150 minutos" in responder("Quanto falta para a meta da OMS?", RESUMO)
    assert "1,2 L" in responder("Quanta água devo beber?", RESUMO)
    assert "2 de 5" in responder("Lanches saudáveis", RESUMO)
    semana = responder("Como foi minha semana?", RESUMO)
    assert "5,4 de 10" in semana and "caiu" in semana and "tempo de tela" in semana
    assert "tempo de tela" in responder("O que eu faço hoje?", RESUMO)


def test_cansaco_aponta_as_causas_registradas() -> None:
    texto = responder("Estou cansado", RESUMO)
    assert "abaixo de 7 horas" in texto and "tela" in texto and "60 minutos" in texto
    assert AVISO in texto


def test_alerta_e_prescricao_encaminham_para_profissional() -> None:
    assert responder("Tive falta de ar", RESUMO) == RESPOSTA_ALERTA
    assert "médico ou nutricionista" in responder("Qual suplemento devo tomar?", RESUMO)


def test_sem_registro_pede_para_registrar() -> None:
    assert "Registre" in responder("Como foi minha semana?", VAZIO)


def test_fora_do_escopo_sugere_perguntas() -> None:
    texto = responder("Me conta uma piada", RESUMO)
    assert "Ainda não sei responder" in texto and "Como foi minha semana?" in texto
