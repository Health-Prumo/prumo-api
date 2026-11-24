"""Motor de regras do Prumo.

Calcula as notas de forma determinística: os mesmos dados dão sempre o mesmo
resultado. Nenhuma nota sai do LLM. As metas vêm de data/referencias.json, e os
parâmetros marcados como provisórios ainda serão calibrados pelo grupo.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from prumo_api import referencias

HABITOS = ("sono", "atividade", "agua", "alimentacao", "humor", "tela")
INTENSIDADES = ("leve", "moderada", "vigorosa")
SEXOS = ("feminino", "masculino", "nao_informar")


class ErroValidacao(ValueError):
    """Dado de entrada fora do formato esperado."""


# ---------------------------------------------------------------- utilidades


def arredondar(valor: float, casas: int = 1) -> float:
    """Arredonda meio para cima (o round() do Python arredonda para o par)."""
    fator = 10**casas
    return float(int(valor * fator + 0.5 + 1e-9)) / fator if valor >= 0 else -arredondar(-valor, casas)


def limitar(valor: float, minimo: float = 0.0, maximo: float = 10.0) -> float:
    return max(minimo, min(maximo, valor))


def formatar_horas(horas: float) -> str:
    """5.6667 -> '5h40'."""
    minutos = round(horas * 60)
    h, m = divmod(minutos, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def formatar_numero(valor: float, casas: int = 1) -> str:
    """1.6 -> '1,6'; 2.0 -> '2'."""
    texto = f"{arredondar(valor, casas):.{casas}f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


# ---------------------------------------------------------------- validação


def _numero(dados: dict[str, Any], campo: str, minimo: float, maximo: float, inteiro: bool = False) -> float:
    valor = dados.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroValidacao(f"O campo '{campo}' precisa ser um número.")
    if inteiro and float(valor) != int(valor):
        raise ErroValidacao(f"O campo '{campo}' precisa ser um número inteiro.")
    if not minimo <= valor <= maximo:
        raise ErroValidacao(
            f"O campo '{campo}' precisa estar entre {formatar_numero(minimo)} e {formatar_numero(maximo)}."
        )
    return float(valor)


def validar_registro(dados: Any) -> dict[str, Any]:
    """Confere o registro do dia e devolve uma cópia normalizada."""
    if not isinstance(dados, dict):
        raise ErroValidacao("O corpo precisa ser um objeto JSON.")
    intensidade = dados.get("atividade_intensidade")
    if intensidade not in INTENSIDADES:
        raise ErroValidacao("O campo 'atividade_intensidade' precisa ser leve, moderada ou vigorosa.")
    alimentacao = dados.get("alimentacao")
    if not isinstance(alimentacao, dict):
        raise ErroValidacao("O campo 'alimentacao' precisa ser um objeto.")
    comida: dict[str, bool] = {}
    for campo in ("frutas_verduras", "refeicao_caseira", "ultraprocessados"):
        valor = alimentacao.get(campo)
        if not isinstance(valor, bool):
            raise ErroValidacao(f"O campo 'alimentacao.{campo}' precisa ser verdadeiro ou falso.")
        comida[campo] = valor
    return {
        "sono_horas": arredondar(_numero(dados, "sono_horas", 0, 16), 2),
        "sono_qualidade": int(_numero(dados, "sono_qualidade", 1, 5, inteiro=True)),
        "atividade_minutos": int(_numero(dados, "atividade_minutos", 0, 600, inteiro=True)),
        "atividade_intensidade": intensidade,
        "agua_litros": arredondar(_numero(dados, "agua_litros", 0, 8), 2),
        "alimentacao": comida,
        "humor": int(_numero(dados, "humor", 1, 5, inteiro=True)),
        "tela_horas": arredondar(_numero(dados, "tela_horas", 0, 16), 2),
    }


# ---------------------------------------------------------------- pesos


def pesos() -> dict[str, float]:
    """Pesos da nota de energia.

    PROVISÓRIOS: o grupo ainda vai definir os pesos. Até lá, todos os hábitos
    valem o mesmo. Para testar outra combinação, defina PRUMO_PESOS com um JSON,
    por exemplo {"sono": 2, "atividade": 1.5}. Hábitos ausentes ficam com peso 1.
    """
    base = dict.fromkeys(HABITOS, 1.0)
    bruto = os.environ.get("PRUMO_PESOS", "").strip()
    if bruto:
        try:
            extra = json.loads(bruto)
        except json.JSONDecodeError as erro:
            raise RuntimeError("PRUMO_PESOS não é um JSON válido.") from erro
        if not isinstance(extra, dict):
            raise RuntimeError("PRUMO_PESOS precisa ser um objeto JSON.")
        for habito, valor in extra.items():
            if habito not in base or isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
                raise RuntimeError(f"Peso inválido em PRUMO_PESOS: {habito}.")
            base[habito] = float(valor)
    if sum(base.values()) <= 0:
        raise RuntimeError("A soma dos pesos em PRUMO_PESOS precisa ser maior que zero.")
    return base


# ---------------------------------------------------------------- notas por hábito


def _media(valores: list[float]) -> float | None:
    return arredondar(sum(valores) / len(valores), 2) if valores else None


def nota_sono(horas: float) -> float:
    minimo, maximo = referencias.metas()["sono"]["faixa_horas"]
    zero_acima = referencias.parametros()["sono"]["nota_zero_acima_horas"]
    if minimo <= horas <= maximo:
        return 10.0
    if horas < minimo:
        return limitar(10 * horas / minimo)
    return limitar(10 * (1 - (horas - maximo) / (zero_acima - maximo)))


def minutos_equivalentes(minutos: float, intensidade: str) -> float:
    meta = referencias.metas()["atividade"]
    return float(minutos) * float(meta[f"fator_{intensidade}"])


def nota_agua(litros: float, meta_litros: float) -> float:
    return limitar(10 * litros / meta_litros)


def nota_alimentacao(alimentacao: dict[str, bool]) -> float:
    p = referencias.parametros()["alimentacao"]
    total = float(p["base"])
    for campo in ("frutas_verduras", "refeicao_caseira", "ultraprocessados"):
        if alimentacao[campo]:
            total += float(p[campo])
    return limitar(total)


def nota_humor(humor: int) -> float:
    return limitar((humor - 1) * 2.5)


def nota_tela(horas: float) -> float:
    p = referencias.parametros()["tela"]
    ideal, zero = float(p["nota_maxima_ate_horas"]), float(p["nota_zero_em_horas"])
    if horas <= ideal:
        return 10.0
    return limitar(10 * (zero - horas) / (zero - ideal))


def meta_agua(sexo: str) -> float:
    tabela = referencias.metas()["agua"]["litros_dia"]
    return float(tabela.get(sexo, tabela["nao_informar"]))


# ---------------------------------------------------------------- cálculo do dia


def _comparar_padrao(valor: float, media: float | None, tolerancia: float) -> str | None:
    if media is None:
        return None
    if valor < media - tolerancia:
        return "abaixo"
    if valor > media + tolerancia:
        return "acima"
    return "igual"


def _habito_sono(horas: float, media: float | None) -> dict[str, Any]:
    minimo, maximo = referencias.metas()["sono"]["faixa_horas"]
    if minimo <= horas <= maximo:
        situacao = "boa"
    elif minimo - 1 <= horas < minimo or maximo < horas <= maximo + 1:
        situacao = "atencao"
    else:
        situacao = "alerta"
    padrao = _comparar_padrao(horas, media, 0.5)
    if padrao == "abaixo" and media is not None:
        resumo = f"Abaixo do seu padrão de {formatar_horas(media)}"
    elif padrao == "acima" and media is not None:
        resumo = f"Acima do seu padrão de {formatar_horas(media)}"
    elif situacao == "boa":
        resumo = f"Dentro da faixa de {minimo} a {maximo} h"
    elif horas < minimo:
        resumo = f"Abaixo da faixa de {minimo} a {maximo} h"
    else:
        resumo = f"Acima da faixa de {minimo} a {maximo} h"
    return {
        "nota": arredondar(nota_sono(horas)),
        "valor": horas,
        "unidade": "h",
        "media_7d": media,
        "situacao": situacao,
        "resumo": resumo,
    }


def _habito_atividade(minutos: int, intensidade: str, semana_min: float, media: float | None) -> dict[str, Any]:
    meta = float(referencias.metas()["atividade"]["meta_semana_min"])
    if semana_min >= meta:
        situacao, resumo = "boa", "Meta semanal da OMS atingida"
    else:
        situacao = "atencao" if semana_min >= meta / 2 else "alerta"
        resumo = f"Faltam {int(meta - semana_min + 0.999)} min para a meta semanal da OMS"
    if intensidade == "leve" and minutos > 0 and semana_min < meta:
        resumo += " (atividade leve ajuda, mas não soma na meta)"
    return {
        "nota": arredondar(limitar(10 * semana_min / meta)),
        "valor": minutos,
        "unidade": "min",
        "media_7d": media,
        "situacao": situacao,
        "resumo": resumo,
        "semana_min": arredondar(semana_min),
        "meta_semana_min": int(meta),
    }


def _habito_agua(litros: float, meta_l: float, media: float | None) -> dict[str, Any]:
    if litros >= meta_l:
        situacao, resumo = "boa", f"Meta de {formatar_numero(meta_l)} L atingida"
    else:
        situacao = "atencao" if litros >= 0.75 * meta_l else "alerta"
        resumo = f"Faltam {formatar_numero(meta_l - litros)} L para {formatar_numero(meta_l)} L"
    return {
        "nota": arredondar(nota_agua(litros, meta_l)),
        "valor": litros,
        "unidade": "L",
        "media_7d": media,
        "situacao": situacao,
        "resumo": resumo,
    }


def _habito_alimentacao(alimentacao: dict[str, bool], media: float | None) -> dict[str, Any]:
    nota = nota_alimentacao(alimentacao)
    if nota >= 8:
        situacao, resumo = "boa", "Alinhada ao Guia Alimentar"
    elif nota >= 5:
        situacao, resumo = "atencao", "Parte do dia seguiu o Guia Alimentar"
    else:
        situacao, resumo = "alerta", "Espaço para mais comida de verdade"
    return {
        "nota": arredondar(nota),
        "valor": arredondar(nota),
        "unidade": "/10",
        "media_7d": media,
        "situacao": situacao,
        "resumo": resumo,
    }


def _habito_humor(humor: int, media: float | None) -> dict[str, Any]:
    if humor >= 4:
        situacao, resumo = "boa", "Disposição boa"
    elif humor == 3:
        situacao, resumo = "atencao", "Disposição moderada"
    else:
        situacao, resumo = "alerta", "Energia baixa hoje"
    return {
        "nota": arredondar(nota_humor(humor)),
        "valor": humor,
        "unidade": "/5",
        "media_7d": media,
        "situacao": situacao,
        "resumo": resumo,
    }


def _habito_tela(horas: float, media: float | None) -> dict[str, Any]:
    indicador = float(referencias.metas()["tela"]["indicador_horas_dia"])
    if horas < indicador - 1:
        situacao, resumo = "boa", f"Abaixo de {formatar_numero(indicador)} h no lazer"
    elif horas < indicador:
        situacao, resumo = "atencao", f"Perto de {formatar_numero(indicador)} h no lazer"
    else:
        situacao, resumo = "alerta", f"{formatar_numero(indicador)} h ou mais no lazer (critério do Vigitel)"
    return {
        "nota": arredondar(nota_tela(horas)),
        "valor": horas,
        "unidade": "h",
        "media_7d": media,
        "situacao": situacao,
        "resumo": resumo,
    }


def calcular(
    registro: dict[str, Any],
    sexo: str,
    anteriores: dict[str, dict[str, Any]],
    data: date,
) -> dict[str, Any]:
    """Calcula as notas do dia.

    `anteriores` mapeia 'aaaa-mm-dd' -> registro dos dias anteriores; só os 7 dias
    imediatamente antes de `data` entram na média e na soma semanal de atividade.
    """
    janela = [
        anteriores[d.isoformat()]
        for d in (date.fromordinal(data.toordinal() - i) for i in range(1, 8))
        if d.isoformat() in anteriores
    ]

    def media(chave: str) -> float | None:
        return _media([float(r[chave]) for r in janela])

    semana_min = minutos_equivalentes(registro["atividade_minutos"], registro["atividade_intensidade"])
    # Soma semanal = hoje + 6 dias anteriores (janela móvel de 7 dias).
    for i in range(1, 7):
        anterior = anteriores.get(date.fromordinal(data.toordinal() - i).isoformat())
        if anterior:
            semana_min += minutos_equivalentes(anterior["atividade_minutos"], anterior["atividade_intensidade"])

    habitos = {
        "sono": _habito_sono(registro["sono_horas"], media("sono_horas")),
        "atividade": _habito_atividade(
            registro["atividade_minutos"], registro["atividade_intensidade"], semana_min, media("atividade_minutos")
        ),
        "agua": _habito_agua(registro["agua_litros"], meta_agua(sexo), media("agua_litros")),
        "alimentacao": _habito_alimentacao(
            registro["alimentacao"], _media([nota_alimentacao(r["alimentacao"]) for r in janela])
        ),
        "humor": _habito_humor(registro["humor"], media("humor")),
        "tela": _habito_tela(registro["tela_horas"], media("tela_horas")),
    }
    p = pesos()
    energia = sum(habitos[h]["nota"] * p[h] for h in HABITOS) / sum(p.values())
    return {"energia": arredondar(energia), "habitos": habitos, "pesos": p}
