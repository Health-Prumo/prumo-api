"""Texto do card "Seu dia" e respostas do Coach.

O LLM só explica e sugere: recebe as notas prontas (só números e rótulos, sem
nome, e-mail ou id do usuário) e devolve um JSON validado aqui. Se a resposta
vier fora do formato, o card usa o texto fixo do modo mock.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Protocol

from prumo_api import coach as coach_regras
from prumo_api.coach import RESPOSTA_ALERTA, tem_sinal_de_alerta
from prumo_api.regras import HABITOS, formatar_horas, formatar_numero

log = logging.getLogger(__name__)

AVISO = "O Prumo não substitui orientação médica."
MAX_TOKENS = 400
MODELO_PADRAO = "amazon.nova-micro-v1:0"

NOMES = {
    "sono": "sono",
    "atividade": "atividade física",
    "agua": "água",
    "alimentacao": "alimentação",
    "humor": "humor",
    "tela": "tempo de tela",
}

ARTIGOS = {"sono": "o", "atividade": "a", "agua": "a", "alimentacao": "a", "humor": "o", "tela": "o"}

SUGESTOES_MOCK = {
    "sono": ("Durma 30 min mais cedo", "Deixe o celular fora do quarto 1 hora antes de deitar."),
    "atividade": ("Caminhe 20 minutos", "Uma caminhada em ritmo moderado depois do almoço já conta para a meta."),
    "agua": ("Beba 2 copos de água agora", "Deixe uma garrafa à vista e beba um copo a cada refeição."),
    "alimentacao": ("Inclua uma fruta no lanche", "Troque um lanche pronto por uma fruta ou castanhas."),
    "humor": ("Faça uma pausa de 5 minutos", "Respire fundo, alongue-se ou tome um pouco de sol."),
    "tela": ("Desligue as telas 1 hora antes de dormir", "Troque esse tempo por leitura, música ou conversa."),
}

PROMPT_CARD = f"""Você é o Coach Prumo, um coach de bem-estar acolhedor que escreve em português do Brasil.
Você recebe as notas de um dia JÁ CALCULADAS por regras fixas. Não calcule, não altere e não invente números:
cite apenas valores presentes nos dados. Não faça diagnóstico, não prescreva dieta, remédio ou treino.
Tom: acolhedor, nunca culpabilizante ("seu sono ficou abaixo do seu padrão", nunca "você dormiu mal"),
frases curtas, sem exclamações em excesso e sem emojis.
Responda SOMENTE com um JSON neste formato:
{{"titulo": "frase curta (até 60 caracteres) sobre o dia",
  "resumo": "1 ou 2 frases citando os números mais relevantes",
  "sugestoes": [{{"habito": "um de {", ".join(HABITOS)}", "titulo": "ação concreta com tempo (até 40 caracteres)",
                  "detalhe": "como fazer, em uma frase"}}]}}
Dê 1 ou 2 sugestões, priorizando os hábitos com menor nota."""

PROMPT_CHAT = f"""Você é o Coach Prumo, um coach de bem-estar acolhedor que conversa em português do Brasil.
Você conhece um resumo numérico do histórico recente da pessoa (calculado por regras fixas).
Use apenas esses números; se não souber, diga que não há dados suficientes. Não invente números.
Não faça diagnóstico e não prescreva dieta, remédio ou treino. Se a pessoa relatar sintomas preocupantes,
oriente procurar um profissional de saúde (SAMU 192; CVV 188 para sofrimento emocional).
Responda em até 4 frases curtas, com no máximo 2 sugestões práticas, tom acolhedor e nunca culpabilizante.
Lembre, quando fizer sentido, que {AVISO[0].lower()}{AVISO[1:]}"""


class ChamadorLLM(Protocol):
    def __call__(self, sistema: str, mensagens: list[dict[str, Any]]) -> str: ...


def _minuscula_inicial(texto: str) -> str:
    """Baixa só a primeira letra, preservando siglas como OMS."""
    return texto[:1].lower() + texto[1:]


# ---------------------------------------------------------------- contexto (só números)


def contexto_do_dia(registro: dict[str, Any], notas: dict[str, Any]) -> dict[str, Any]:
    """Monta o que vai ao LLM: só números e rótulos, nada que identifique a pessoa."""
    habitos = {
        h: {
            "nota": notas["habitos"][h]["nota"],
            "valor": notas["habitos"][h]["valor"],
            "unidade": notas["habitos"][h]["unidade"],
            "media_7d": notas["habitos"][h]["media_7d"],
            "situacao": notas["habitos"][h]["situacao"],
            "resumo": notas["habitos"][h]["resumo"],
        }
        for h in HABITOS
    }
    habitos["atividade"]["semana_min"] = notas["habitos"]["atividade"]["semana_min"]
    habitos["atividade"]["meta_semana_min"] = notas["habitos"]["atividade"]["meta_semana_min"]
    habitos["atividade"]["intensidade"] = registro["atividade_intensidade"]
    habitos["sono"]["qualidade_1a5"] = registro["sono_qualidade"]
    habitos["alimentacao"]["respostas"] = dict(registro["alimentacao"])
    return {"energia_0a10": notas["energia"], "habitos": habitos}


def _prioridades(notas: dict[str, Any]) -> list[str]:
    """Hábitos fora da situação 'boa', do menor para o maior (ordem fixa no empate)."""
    candidatos = [h for h in HABITOS if notas["habitos"][h]["situacao"] != "boa"]
    return sorted(candidatos, key=lambda h: (notas["habitos"][h]["nota"], HABITOS.index(h)))


# ---------------------------------------------------------------- modo mock


def analise_mock(registro: dict[str, Any], notas: dict[str, Any]) -> dict[str, Any]:
    energia = notas["energia"]
    habitos = notas["habitos"]
    foco = _prioridades(notas)
    if not foco:
        titulo = "Um dia equilibrado, siga assim."
    elif energia >= 5:
        titulo = f"Bom dia, com {ARTIGOS[foco[0]]} {NOMES[foco[0]]} pedindo atenção."
    else:
        titulo = "Dia de pegar leve e cuidar de você."

    frases = [f"Sua energia ficou em {formatar_numero(energia)} de 10."]
    if foco:
        h = foco[0]
        frases.append(f"{NOMES[h].capitalize()}: {_minuscula_inicial(habitos[h]['resumo'])}.")
    else:
        sono = habitos["sono"]["valor"]
        frases.append(f"Você dormiu {formatar_horas(sono)} e manteve os hábitos dentro das metas.")

    escolhidos = foco[:2] or ["atividade"]
    sugestoes = [{"habito": h, "titulo": SUGESTOES_MOCK[h][0], "detalhe": SUGESTOES_MOCK[h][1]} for h in escolhidos]
    return {"titulo": titulo, "resumo": " ".join(frases), "sugestoes": sugestoes, "fonte": "mock", "aviso": AVISO}


def resposta_chat_mock(mensagem: str, resumo: dict[str, Any]) -> str:
    """Coach por regras (sem modelo de linguagem). Ver coach.py."""
    return coach_regras.responder(mensagem, resumo)


# ---------------------------------------------------------------- Bedrock


def _extrair_json(texto: str) -> Any:
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < inicio:
        raise ValueError("Resposta sem JSON.")
    return json.loads(texto[inicio : fim + 1])


def _texto_ok(valor: Any, maximo: int) -> bool:
    return isinstance(valor, str) and 0 < len(valor.strip()) <= maximo


def validar_analise(bruto: Any) -> dict[str, Any]:
    if not isinstance(bruto, dict):
        raise ValueError("Análise não é objeto.")
    if not _texto_ok(bruto.get("titulo"), 120) or not _texto_ok(bruto.get("resumo"), 500):
        raise ValueError("Título ou resumo inválido.")
    sugestoes = bruto.get("sugestoes")
    if not isinstance(sugestoes, list) or not 1 <= len(sugestoes) <= 2:
        raise ValueError("Sugestões precisam ser 1 ou 2.")
    limpas = []
    for s in sugestoes:
        if (
            not isinstance(s, dict)
            or s.get("habito") not in HABITOS
            or not _texto_ok(s.get("titulo"), 80)
            or not _texto_ok(s.get("detalhe"), 240)
        ):
            raise ValueError("Sugestão inválida.")
        limpas.append({"habito": s["habito"], "titulo": s["titulo"].strip(), "detalhe": s["detalhe"].strip()})
    return {
        "titulo": bruto["titulo"].strip(),
        "resumo": bruto["resumo"].strip(),
        "sugestoes": limpas,
        "fonte": "bedrock",
        "aviso": AVISO,
    }


def chamador_bedrock() -> ChamadorLLM:
    import boto3  # importado só quando o Bedrock é usado de propósito

    cliente = boto3.client("bedrock-runtime")
    modelo = os.environ.get("PRUMO_MODELO_ID", MODELO_PADRAO)

    def chamar(sistema: str, mensagens: list[dict[str, Any]]) -> str:
        resposta = cliente.converse(
            modelId=modelo,
            system=[{"text": sistema}],
            messages=mensagens,  # type: ignore[arg-type]
            inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0.3},
        )
        blocos = resposta["output"]["message"]["content"]  # type: ignore[typeddict-item]
        return "".join(b.get("text", "") for b in blocos)

    return chamar


class Coach:
    """Gera o card e as respostas do chat, em modo mock ou com o Bedrock."""

    def __init__(self, modo: str | None = None, chamador: ChamadorLLM | None = None) -> None:
        self.modo = modo or os.environ.get("PRUMO_IA", "mock")
        if self.modo not in ("mock", "bedrock"):
            raise RuntimeError("PRUMO_IA precisa ser mock ou bedrock.")
        self._chamador = chamador

    @property
    def chamador(self) -> ChamadorLLM:
        if self._chamador is None:
            self._chamador = chamador_bedrock()
        return self._chamador

    def analisar_dia(self, registro: dict[str, Any], notas: dict[str, Any]) -> dict[str, Any]:
        if self.modo == "mock":
            return analise_mock(registro, notas)
        contexto = contexto_do_dia(registro, notas)
        mensagens = [{"role": "user", "content": [{"text": json.dumps(contexto, ensure_ascii=False)}]}]
        try:
            return validar_analise(_extrair_json(self.chamador(PROMPT_CARD, mensagens)))
        except Exception:  # resposta fora do formato ou falha do Bedrock: usa o texto fixo
            log.exception("Falha ao gerar a análise pelo Bedrock; usando o modo mock.")
            return analise_mock(registro, notas)

    def responder(self, mensagem: str, resumo: dict[str, Any], conversa: list[dict[str, Any]]) -> tuple[str, str]:
        """Devolve (resposta, fonte). `conversa` são as últimas mensagens, em ordem."""
        if tem_sinal_de_alerta(mensagem):
            return RESPOSTA_ALERTA, "mock"
        if self.modo == "mock":
            return resposta_chat_mock(mensagem, resumo), "mock"
        mensagens: list[dict[str, Any]] = []
        for item in conversa[-6:]:
            papel = "user" if item["papel"] == "usuario" else "assistant"
            texto = str(item["texto"])[:500]
            if mensagens and mensagens[-1]["role"] == papel:
                mensagens[-1]["content"][0]["text"] += "\n" + texto
            else:
                mensagens.append({"role": papel, "content": [{"text": texto}]})
        if mensagens and mensagens[0]["role"] != "user":
            mensagens.pop(0)
        pergunta = (
            f"Resumo do meu histórico (números calculados pelo app): {json.dumps(resumo, ensure_ascii=False)}\n\n"
            f"Minha pergunta: {mensagem}"
        )
        if mensagens and mensagens[-1]["role"] == "user":
            mensagens[-1]["content"][0]["text"] += "\n" + pergunta
        else:
            mensagens.append({"role": "user", "content": [{"text": pergunta}]})
        try:
            texto = self.chamador(PROMPT_CHAT, mensagens).strip()
            if not texto:
                raise ValueError("Resposta vazia.")
            return texto[:1500], "bedrock"
        except Exception:
            log.exception("Falha ao responder pelo Bedrock; usando o modo mock.")
            return resposta_chat_mock(mensagem, resumo), "mock"
