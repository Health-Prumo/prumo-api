"""Coach Prumo por regras: entende o assunto da pergunta e responde com os números do usuário.

Não há modelo de linguagem aqui. A pergunta é normalizada (minúsculas, sem acento) e
comparada com listas de termos por assunto. O assunto com mais termos encontrados
vence; no empate, vale a ordem de ASSUNTOS. Os textos usam só o resumo numérico do
histórico (sem nome, e-mail ou outro identificador) e as metas oficiais.

A mesma pergunta com os mesmos dados dá sempre a mesma resposta, o que deixa o Coach
previsível para a apresentação. O roteiro de perguntas testadas está no README.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any

from .regras import formatar_horas, formatar_numero

AVISO = "O Prumo não substitui orientação médica."

NOMES = {
    "sono": "sono",
    "atividade": "atividade física",
    "agua": "água",
    "alimentacao": "alimentação",
    "humor": "humor",
    "tela": "tempo de tela",
}

# Relatos que pedem avaliação profissional, não conselho de hábito. Vencem qualquer outro assunto.
SINAIS_DE_ALERTA = (
    "dor no peito",
    "falta de ar",
    "desmai",
    "suicid",
    "me matar",
    "tirar minha vida",
    "nao quero mais viver",
    "autolesao",
    "me machucar",
    "me cortar",
    "sangramento",
    "convuls",
    "palpitac",
    "formigamento",
    "paralisia",
    "visao turva",
    "confusao mental",
    "febre alta",
)

RESPOSTA_ALERTA = (
    "O que você descreveu merece atenção de um profissional de saúde. "
    "Procure um médico ou uma unidade de saúde. Em caso de urgência, ligue 192 (SAMU). "
    "Se estiver passando por sofrimento emocional, o CVV atende 24 horas pelo 188. " + AVISO
)

# Termos por assunto. Cada termo é o início de uma palavra (ex.: "dorm" acha dormir, dormi, dormindo);
# termos terminados em "$" precisam ser a palavra inteira (ex.: "oi$").
ASSUNTOS: dict[str, tuple[str, ...]] = {
    "prescricao": (
        "remedio",
        "medicament",
        "suplement",
        "whey",
        "creatina",
        "vitamina",
        "melatonina",
        "emagrec",
        "perder peso",
        "engordar",
        "ganhar massa",
        "caloria",
        "dieta",
        "jejum",
        "diagnost",
        "doenca",
        "tratamento",
        "receita medica",
        "dose",
    ),
    "nota": (
        "nota",
        "calcul",
        "pontua",
        "pontos",
        "peso dos",
        "pesos",
        "como funciona a energia",
        "como e feita",
        "de onde vem",
        "criterio",
    ),
    "semana": (
        "semana",
        "mes$",
        "mes passado",
        "resumo",
        "como estou",
        "como fui",
        "como foi",
        "como vai",
        "evolu",
        "progresso",
        "historico",
        "ultimos dias",
        "balanco",
        "melhorei",
        "piorei",
    ),
    "cansaco": (
        "cansad",
        "cansaco",
        "sem energia",
        "pouca energia",
        "energia baixa",
        "desanim",
        "exaust",
        "fadiga",
        "indisposi",
        "sonolen",
        "esgotad",
        "sem disposicao",
    ),
    "sono": (
        "dorm",
        "sono",
        "insonia",
        "acord",
        "deitar",
        "cochil",
        "descans",
        "cama$",
        "madrugada",
    ),
    "alimentacao": (
        "lanche",
        "lanchinho",
        "comer",
        "comida",
        "aliment",
        "jantar",
        "janta$",
        "almoc",
        "cafe da manha",
        "fruta",
        "verdura",
        "legume",
        "ultraprocess",
        "processad",
        "receita",
        "fome",
        "doce",
        "refeic",
        "petisco",
        "salgad",
        "refrigerante",
        "fast food",
        "saudave",
        "nutri",
    ),
    "agua": ("agua", "hidrat", "beber", "bebo", "sede", "copo", "garrafa", "litro"),
    "atividade": (
        "exercic",
        "atividade",
        "caminh",
        "academia",
        "treino",
        "treinar",
        "correr",
        "corrida",
        "alonga",
        "sedentar",
        "esporte",
        "bike",
        "bicicleta",
        "pedal",
        "andar",
        "movimento",
        "musculac",
        "academia",
        "oms",
        "150 min",
        "minutos por semana",
    ),
    "tela": (
        "tela",
        "celular",
        "redes sociais",
        "rede social",
        "instagram",
        "tiktok",
        "youtube",
        "serie",
        "tv$",
        "televis",
        "computador",
        "videogame",
        "jogar",
        "rolando o feed",
        "scroll",
    ),
    "humor": (
        "estress",
        "ansie",
        "ansios",
        "humor",
        "triste",
        "chatead",
        "nervos",
        "irritad",
        "preocupad",
        "sozinh",
        "pra baixo",
        "para baixo",
        "desmotivad",
        "angusti",
        "relaxar",
        "calma",
    ),
    "hoje": (
        "o que devo",
        "o que posso",
        "o que eu faco",
        "o que fazer",
        "dica",
        "sugest",
        "melhorar",
        "hoje",
        "por onde comec",
        "comecar",
        "foco",
        "priorid",
        "plano",
        "meta",
    ),
    "privacidade": (
        "meus dados",
        "privacidade",
        "lgpd",
        "apagar",
        "excluir",
        "exportar",
        "seguranca",
        "quem ve",
        "compartilh",
    ),
    "sobre": (
        "quem e voce",
        "quem voce e",
        "o que voce",
        "como voce funciona",
        "o que e o prumo",
        "ajuda$",
        "me ajuda com o que",
        "inteligencia artificial",
        "ia$",
        "robo",
        "chatgpt",
    ),
    "saudacao": ("oi$", "ola$", "bom dia", "boa tarde", "boa noite", "e ai", "tudo bem", "opa$", "hey$"),
    "agradecimento": ("obrigad", "valeu", "brigad", "agradec", "show$", "otimo$", "legal$", "perfeito"),
}

# Assuntos que só valem quando nada mais foi reconhecido (ex.: "oi, como melhorar meu sono?" é sono).
SOCIAIS = ("saudacao", "agradecimento")


def normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9$ ]", " ", sem_acento).split())


def _padrao(termo: str) -> re.Pattern[str]:
    inteiro = termo.endswith("$")
    corpo = re.escape(termo.rstrip("$"))
    return re.compile(rf"\b{corpo}\b" if inteiro else rf"\b{corpo}")


_PADROES = {assunto: [_padrao(t) for t in termos] for assunto, termos in ASSUNTOS.items()}


def tem_sinal_de_alerta(texto: str) -> bool:
    normalizado = normalizar(texto)
    return any(termo in normalizado for termo in SINAIS_DE_ALERTA)


def identificar_assunto(mensagem: str) -> str:
    """Devolve o assunto da pergunta, ou 'fora' se nenhum termo for reconhecido."""
    if tem_sinal_de_alerta(mensagem):
        return "alerta"
    texto = normalizar(mensagem)
    contagem = {a: sum(1 for p in padroes if p.search(texto)) for a, padroes in _PADROES.items()}
    if contagem["prescricao"]:
        return "prescricao"
    ordem = list(ASSUNTOS)
    principais = [a for a in ordem if a not in SOCIAIS and contagem[a]]
    if principais:
        return max(principais, key=lambda a: (contagem[a], -ordem.index(a)))
    sociais = [a for a in SOCIAIS if contagem[a]]
    return sociais[0] if sociais else "fora"


# ---------------------------------------------------------------- utilitários de texto


def _h(valor: float) -> str:
    return formatar_horas(valor)


def _n(valor: float) -> str:
    return formatar_numero(valor)


def _l(valor: float) -> str:
    return f"{formatar_numero(valor)} L"


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return singular if quantidade == 1 else plural


def _tem_dados(r: dict[str, Any]) -> bool:
    return bool(r.get("dias_registrados"))


def _periodo(r: dict[str, Any]) -> str:
    q = int(r["dias_registrados"])
    return "No seu único dia registrado" if q == 1 else f"Nos seus últimos {q} dias registrados"


def _tendencia(r: dict[str, Any], chave: str) -> str | None:
    """Compara a primeira e a segunda metade dos últimos 7 dias: 'subiu', 'caiu' ou 'estável'."""
    pontos = [p[chave] for p in r.get("ultimos_7_dias", []) if p.get(chave) is not None]
    if len(pontos) < 4:
        return None
    meio = len(pontos) // 2
    antes, depois = sum(pontos[:meio]) / meio, sum(pontos[meio:]) / (len(pontos) - meio)
    limiar = 0.5 if chave in ("energia", "sono_h", "tela_h") else 1
    if depois - antes >= limiar:
        return "subiu"
    if antes - depois >= limiar:
        return "caiu"
    return "estável"


def _sem_dados(tema: str) -> str:
    return (
        f"Ainda não tenho registros seus para falar de {tema} com os seus números. "
        "Registre o seu dia (leva menos de 1 minuto) e eu passo a comparar com o seu próprio padrão. "
    )


# ---------------------------------------------------------------- respostas por assunto


def _sono(r: dict[str, Any]) -> str:
    dicas = [
        "mantenha horários parecidos para deitar e acordar, inclusive no fim de semana",
        "deixe o celular longe da cama 1 hora antes de dormir",
        "evite café, chá preto e energético depois das 16h",
        "deixe o quarto escuro, silencioso e fresco",
    ]
    if not _tem_dados(r):
        return (
            "Para adultos, a referência é dormir de 7 a 9 horas por noite (National Sleep Foundation). "
            f"Três ajustes que costumam ajudar: {dicas[0]}; {dicas[1]}; e {dicas[2]}. "
            + _sem_dados("o seu sono")
            + AVISO
        )
    sono = float(r["sono_medio_h"])
    if sono < 7:
        situacao = f"você dormiu em média {_h(sono)}, abaixo da faixa de 7 a 9 horas"
    elif sono > 9:
        situacao = f"você dormiu em média {_h(sono)}, acima da faixa de 7 a 9 horas"
    else:
        situacao = f"você dormiu em média {_h(sono)}, dentro da faixa de 7 a 9 horas"
    texto = f"{_periodo(r)}, {situacao}."
    if r.get("sono_qualidade_media") is not None:
        texto += f" A qualidade que você deu ao sono ficou em {_n(r['sono_qualidade_media'])} de 5."
    escolhidas = [dicas[0]]
    if r.get("tela_media_h", 0) >= 3:
        texto += f" Seu tempo de tela no lazer está em {_h(r['tela_media_h'])} por dia, e isso pode atrasar o sono."
        escolhidas.append(dicas[1])
    else:
        escolhidas.append(dicas[3])
    escolhidas.append(dicas[2])
    texto += f" Para esta semana: {escolhidas[0]}; {escolhidas[1]}; e {escolhidas[2]}."
    if sono < 7:
        texto += " Uma meta realista é deitar 30 minutos mais cedo por 3 noites e ver como sua energia responde."
    return texto + " " + AVISO


def _alimentacao(r: dict[str, Any]) -> str:
    lanches = (
        "Ideias de lanche no estilo do Guia Alimentar: uma fruta com um punhado de castanhas ou amendoim; "
        "iogurte natural com banana e aveia; pão integral com ovo mexido; ou tapioca com queijo branco e tomate."
    )
    jantar = (
        " Para chegar bem ao jantar, faça o lanche umas 3 horas antes: ele segura a fome sem tirar o apetite, "
        "e você evita beliscar ultraprocessados no caminho."
    )
    regra = (
        " A regra de ouro do Guia Alimentar é preferir alimentos in natura ou minimamente processados "
        "e preparações caseiras aos ultraprocessados."
    )
    if not _tem_dados(r):
        return lanches + jantar + regra + " " + _sem_dados("a sua alimentação").strip()
    dias = int(r["dias_registrados"])
    frutas = int(r.get("dias_frutas_verduras", 0))
    ultra = int(r.get("dias_ultraprocessados", 0))
    texto = f"{_periodo(r)}, você comeu frutas ou verduras em {frutas} de {dias} {_plural(dias, 'dia', 'dias')}"
    texto += f" e marcou ultraprocessados em {ultra}."
    if ultra > dias / 2:
        texto += " Um bom primeiro passo é trocar o lanche pronto da tarde por uma opção caseira."
    elif frutas < dias:
        texto += " Dá para incluir uma fruta no lanche dos dias que ficaram sem."
    else:
        texto += " Você está bem alinhado ao Guia Alimentar."
    return texto + " " + lanches + jantar


def _agua(r: dict[str, Any]) -> str:
    meta = float(r.get("meta_agua_l") or 2.0)
    dicas = (
        "Deixe uma garrafa à vista na mesa, beba um copo a cada refeição e outro ao acordar. "
        "Frutas como melancia e laranja também ajudam."
    )
    if not _tem_dados(r):
        return (
            f"A referência da EFSA é de cerca de {_l(meta)} por dia, somando a água dos alimentos. "
            + dicas
            + " "
            + _sem_dados("a sua hidratação").strip()
        )
    media = float(r["agua_media_l"])
    falta = meta - media
    texto = f"{_periodo(r)}, você bebeu em média {_l(media)} por dia, e a sua meta é {_l(meta)} (EFSA)."
    if falta > 0.05:
        copos = max(1, round(falta / 0.25))
        texto += f" Faltam cerca de {_l(falta)}, o que dá {copos} {_plural(copos, 'copo', 'copos')}"
        texto += " de 250 mL a mais por dia."
    else:
        texto += " Você está batendo a meta, ótimo."
    return texto + " " + dicas


def _atividade(r: dict[str, Any]) -> str:
    base = (
        "A OMS recomenda de 150 a 300 minutos por semana de atividade moderada (ou 75 a 150 de vigorosa), "
        "além de fortalecimento muscular 2 vezes por semana."
    )
    ideias = (
        " Ideias que cabem na rotina: caminhar 20 minutos depois do almoço, descer um ponto antes do ônibus, "
        "usar a escada ou fazer 10 minutos de alongamento e agachamentos em casa."
    )
    if not _tem_dados(r):
        return base + ideias + " " + _sem_dados("a sua atividade").strip()
    semana = float(r.get("atividade_semana_min") or 0)
    meta = int(r.get("meta_semana_min") or 150)
    if semana >= meta:
        texto = f"Nos últimos 7 dias você somou {int(semana)} minutos, e a meta da OMS de {meta} está batida."
        texto += " Se quiser evoluir, inclua fortalecimento muscular 2 vezes por semana."
    else:
        falta = int(meta - semana + 0.999)
        texto = f"Nos últimos 7 dias você somou {int(semana)} de {meta} minutos da meta da OMS. Faltam {falta} minutos."
        por_dia = max(10, round(falta / 5 / 5) * 5)
        texto += f" Dá para fechar com uns {por_dia} minutos de caminhada em 5 dias."
        texto += " Lembre que 1 minuto vigoroso conta como 2 moderados, e atividade leve não entra na conta."
    return texto + ideias


def _tela(r: dict[str, Any]) -> str:
    dicas = (
        " Algumas trocas simples: tire as notificações das redes sociais, defina um limite de tempo no próprio celular "
        "e troque a última hora antes de dormir por leitura, música ou conversa."
    )
    if not _tem_dados(r):
        return (
            "O Vigitel acompanha quantos adultos passam 3 horas ou mais por dia em telas no tempo livre."
            + dicas
            + " "
            + _sem_dados("o seu tempo de tela").strip()
        )
    tela = float(r["tela_media_h"])
    texto = f"{_periodo(r)}, seu tempo de tela no lazer ficou em {_h(tela)} por dia."
    if tela >= 3:
        texto += " Está acima de 3 horas, o critério usado pelo Vigitel. Reduzir 30 minutos por dia já faz diferença."
    else:
        texto += " Está abaixo de 3 horas, o critério usado pelo Vigitel. Bom sinal."
    tendencia = _tendencia(r, "tela_h")
    if tendencia == "subiu":
        texto += " Nos últimos dias ele aumentou."
    return texto + dicas


def _humor(r: dict[str, Any]) -> str:
    acoes = (
        " Algumas coisas que costumam ajudar: uma caminhada curta ao ar livre, 5 minutos de respiração lenta "
        "(inspire em 4 tempos, solte em 6), conversar com alguém de confiança e manter o sono em dia."
    )
    persistente = (
        " Se o desânimo, a ansiedade ou a tristeza durarem mais de duas semanas ou atrapalharem sua rotina, "
        "procure um profissional de saúde. O CVV atende 24 horas pelo 188."
    )
    if not _tem_dados(r):
        return "Sinto muito que você esteja assim." + acoes + persistente + " " + AVISO
    humor = float(r["humor_medio_1a5"])
    texto = f"{_periodo(r)}, seu humor e sua energia ficaram em média {_n(humor)} de 5."
    if r.get("sono_medio_h", 8) < 7:
        texto += f" Seu sono médio de {_h(r['sono_medio_h'])} pode estar pesando."
    return texto + acoes + persistente + " " + AVISO


def _cansaco(r: dict[str, Any]) -> str:
    if not _tem_dados(r):
        return (
            "Cansaço costuma ter a ver com sono curto, pouca movimentação, pouca água e muito tempo de tela. "
            + _sem_dados("o seu cansaço")
            + AVISO
        )
    causas = []
    if r.get("sono_medio_h", 8) < 7:
        causas.append(f"seu sono está em {_h(r['sono_medio_h'])} por noite, abaixo de 7 horas")
    if r.get("tela_media_h", 0) >= 3:
        causas.append(f"o tempo de tela está em {_h(r['tela_media_h'])} por dia")
    if float(r.get("atividade_semana_min") or 0) < float(r.get("meta_semana_min") or 150):
        causas.append(f"a atividade somou {int(r.get('atividade_semana_min') or 0)} minutos na semana")
    meta_agua = float(r.get("meta_agua_l") or 2.0)
    if r.get("agua_media_l", meta_agua) < meta_agua * 0.75:
        causas.append(f"a água está em {_l(r['agua_media_l'])} por dia")
    texto = f"{_periodo(r)}, sua energia média ficou em {_n(r['energia_media'])} de 10."
    tendencia = _tendencia(r, "energia")
    if tendencia == "caiu":
        texto += " E ela caiu nos últimos dias."
    if causas:
        texto += " O que os seus registros mostram: " + "; ".join(causas) + "."
        texto += " Comece pelo sono: deitar 30 minutos mais cedo por 3 noites costuma ter o maior efeito."
    else:
        texto += " Seus hábitos estão dentro das metas, então vale observar outros fatores, como estresse e rotina."
    texto += " Se o cansaço continuar mesmo com bons hábitos, procure um profissional de saúde."
    return texto + " " + AVISO


def _semana(r: dict[str, Any]) -> str:
    if not _tem_dados(r):
        return _sem_dados("a sua semana").strip() + " Assim que tiver alguns dias, eu te mostro a evolução."
    texto = f"{_periodo(r)}: energia média de {_n(r['energia_media'])} de 10"
    texto += f", sono de {_h(r['sono_medio_h'])}, {_l(r['agua_media_l'])} de água por dia"
    texto += f" e {_h(r['tela_media_h'])} de tela no lazer."
    texto += f" Na semana, a atividade somou {int(r.get('atividade_semana_min') or 0)} de "
    texto += f"{int(r.get('meta_semana_min') or 150)} minutos da meta da OMS."
    tendencia = _tendencia(r, "energia")
    if tendencia == "subiu":
        texto += " Sua energia subiu nos últimos dias."
    elif tendencia == "caiu":
        texto += " Sua energia caiu nos últimos dias."
    notas = r.get("notas_medias_0a10") or {}
    if notas:
        melhor = max(notas, key=lambda h: notas[h])
        pior = r.get("habito_mais_baixo") or min(notas, key=lambda h: notas[h])
        texto += f" Seu ponto mais forte é {NOMES[melhor]} ({_n(notas[melhor])} de 10)"
        texto += f", e o que tem mais espaço para melhorar é {NOMES[pior]} ({_n(notas[pior])} de 10)."
    return texto


def _hoje(r: dict[str, Any]) -> str:
    sugestoes = {
        "sono": "deite 30 minutos mais cedo hoje e deixe o celular fora do quarto",
        "atividade": "faça uma caminhada de 20 minutos depois do almoço",
        "agua": "deixe uma garrafa à vista e beba um copo a cada refeição",
        "alimentacao": "troque o lanche pronto por uma fruta com castanhas",
        "humor": "reserve 5 minutos para uma pausa, com respiração lenta ou um pouco de sol",
        "tela": "desligue as telas 1 hora antes de dormir",
    }
    if not _tem_dados(r):
        return (
            "Para começar, registre o seu dia: com ele eu calculo sua energia e aponto o hábito com mais espaço "
            "para melhorar. Enquanto isso, uma caminhada de 20 minutos e um copo de água já são um bom começo."
        )
    notas = r.get("notas_medias_0a10") or {}
    ordem = sorted(notas, key=lambda h: notas[h]) if notas else ["atividade"]
    primeiro = ordem[0]
    texto = f"O hábito com mais espaço para melhorar é {NOMES[primeiro]}"
    texto += f", com nota média {_n(notas.get(primeiro, 0))} de 10."
    texto += f" Para hoje: {sugestoes[primeiro]}."
    if len(ordem) > 1 and notas.get(ordem[1], 10) < 7:
        texto += f" Se sobrar fôlego, {sugestoes[ordem[1]]}."
    return texto + " Pequenas mudanças repetidas valem mais do que uma grande mudança que não se sustenta."


def _nota(r: dict[str, Any]) -> str:
    texto = (
        "A nota de energia vai de 0 a 10 e é calculada pelo código, com regras fixas, sem inteligência artificial. "
        "Cada hábito recebe uma nota: sono pela faixa de 7 a 9 horas (National Sleep Foundation); atividade pela soma "
        "dos últimos 7 dias contra os 150 minutos da OMS; água pela meta da EFSA; alimentação pelas 3 perguntas do "
        "Guia Alimentar; tela pelo critério de 3 horas do Vigitel; e humor pelo que você informa. "
        "A energia é a média ponderada dessas notas."
    )
    pesos = r.get("pesos") or {}
    if pesos and len(set(pesos.values())) == 1:
        texto += " Hoje todos os hábitos têm o mesmo peso."
    notas = r.get("notas_medias_0a10") or {}
    if _tem_dados(r) and notas:
        partes = [f"{NOMES[h]} {_n(v)}" for h, v in notas.items()]
        texto += " Suas notas médias: " + ", ".join(partes) + "."
    return texto + " Os mesmos dados sempre dão a mesma nota."


def _prescricao(_r: dict[str, Any]) -> str:
    return (
        "Remédios, suplementos, dietas e diagnósticos ficam fora do que eu posso orientar: isso precisa de um "
        "médico ou nutricionista, que conhece o seu caso. Eu posso ajudar com hábitos do dia a dia, como sono, "
        "lanches no estilo do Guia Alimentar, água, atividade física e tempo de tela. " + AVISO
    )


def _privacidade(_r: dict[str, Any]) -> str:
    return (
        "Seus registros ficam guardados na AWS, em us-east-1, e só você tem acesso pelo seu login. "
        "Eu uso só números (horas, minutos, litros e notas), nunca o seu nome ou e-mail. "
        "Na aba Perfil você pode exportar todos os seus dados ou apagar a sua conta a qualquer momento, "
        "como prevê a LGPD."
    )


def _sobre(_r: dict[str, Any]) -> str:
    return (
        "Sou o Coach Prumo. Leio os números que você registra e comparo com o seu próprio padrão e com metas "
        "oficiais (OMS, Guia Alimentar, Vigitel). Não uso inteligência artificial generativa: as respostas seguem "
        "regras transparentes, então os mesmos dados dão sempre a mesma resposta. "
        "Posso falar sobre sono, cansaço, lanches e alimentação, água, atividade física, tempo de tela, humor, "
        "o resumo da sua semana e como sua nota é calculada."
    )


def _saudacao(r: dict[str, Any]) -> str:
    if _tem_dados(r):
        return (
            f"Olá! Sua energia média recente está em {_n(r['energia_media'])} de 10. "
            "Quer ver o resumo da semana ou dicas para algum hábito? Pode perguntar sobre sono, lanches, água, "
            "atividade física ou tempo de tela."
        )
    return (
        "Olá! Registre o seu dia e eu te ajudo a entender como está a sua rotina. "
        "Pode perguntar também sobre sono, lanches, água ou atividade."
    )


def _agradecimento(_r: dict[str, Any]) -> str:
    return "Por nada! Estou por aqui quando quiser rever a semana ou pegar uma dica. Cuide-se."


def _fora(_r: dict[str, Any]) -> str:
    return (
        "Ainda não sei responder a isso. Eu converso sobre os seus hábitos: sono, cansaço, lanches e alimentação, "
        "água, atividade física, tempo de tela, humor, o resumo da sua semana e como sua nota é calculada. "
        'Tente, por exemplo: "Como foi minha semana?" ou "Dicas para dormir melhor".'
    )


RESPOSTAS: dict[str, Callable[[dict[str, Any]], str]] = {
    "prescricao": _prescricao,
    "nota": _nota,
    "semana": _semana,
    "cansaco": _cansaco,
    "sono": _sono,
    "alimentacao": _alimentacao,
    "agua": _agua,
    "atividade": _atividade,
    "tela": _tela,
    "humor": _humor,
    "hoje": _hoje,
    "privacidade": _privacidade,
    "sobre": _sobre,
    "saudacao": _saudacao,
    "agradecimento": _agradecimento,
    "fora": _fora,
}


def responder(mensagem: str, resumo: dict[str, Any]) -> str:
    """Resposta do Coach por regras, a partir da pergunta e do resumo numérico do histórico."""
    assunto = identificar_assunto(mensagem)
    if assunto == "alerta":
        return RESPOSTA_ALERTA
    texto = RESPOSTAS[assunto](resumo).strip()
    # Regra do projeto: toda resposta lembra que o Prumo não substitui orientação médica.
    return texto if texto.endswith(AVISO) else f"{texto} {AVISO}"
