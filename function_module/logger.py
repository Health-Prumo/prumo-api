"""Logs operacionais sem corpo, identidade, cabeçalhos ou mensagens de exceção."""

import json
import logging


def configurar_logging() -> None:
    """Configura somente o logger do Prumo, sem alterar handlers de terceiros."""
    logger = logging.getLogger("prumo")
    if not logger.handlers:
        saida = logging.StreamHandler()
        saida.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(saida)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def registrar_execucao(status: int, duracao_ms: float, tipo_erro: str | None = None) -> None:
    dados = {
        "evento": "requisicao_finalizada",
        "status": status,
        "duracao_ms": round(duracao_ms, 2),
        "tipo_erro": tipo_erro,
    }
    nivel = logging.ERROR if status >= 500 else logging.INFO
    logging.getLogger("prumo.api").log(nivel, json.dumps(dados, ensure_ascii=False))
