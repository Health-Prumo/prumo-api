"""Modos reais precisam ser ativados somente quando implementados."""

import pytest

from function_module.settings import carregar_configuracao


@pytest.mark.parametrize(
    ("nome", "valor"),
    [
        ("PRUMO_AMBIENTE", "producao"),
        ("AWS_LAMBDA_FUNCTION_NAME", "prumo-api"),
        ("PRUMO_LLM_MODO", "bedrock"),
        ("PRUMO_USUARIO_LOCAL", ""),
        ("PRUMO_ORIGEM_FRONT", "http://localhost:5173.exemplo.com"),
        ("PRUMO_ORIGEM_FRONT", "http://localhost:5173/caminho"),
        ("PRUMO_PORTA", "0"),
        ("PRUMO_PORTA", "texto"),
        ("PRUMO_HOST_LOCAL", "192.168.1.10"),
    ],
)
def test_rejeita_configuracao_invalida(
    monkeypatch: pytest.MonkeyPatch, nome: str, valor: str
) -> None:
    monkeypatch.setenv(nome, valor)
    with pytest.raises(ValueError):
        carregar_configuracao()


def test_caminho_relativo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_BANCO_LOCAL", ".local/exemplo.sqlite3")
    assert carregar_configuracao().banco_local.is_absolute()
