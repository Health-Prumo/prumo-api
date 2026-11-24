from __future__ import annotations

from datetime import UTC, timedelta

import pytest

from prumo_api import handler as api
from prumo_api.repositorio import RepositorioMemoria
from tests.conftest import USUARIO, Chamar, registro


def hoje() -> str:
    return api.hoje_local().isoformat()


def test_saude_sem_login(chamar: Chamar) -> None:
    status, corpo, _ = chamar("GET", "/saude", usuario=None)
    assert (status, corpo) == (200, {"status": "ok"})


def test_rota_protegida_exige_login(chamar: Chamar) -> None:
    status, corpo, _ = chamar("GET", "/perfil", usuario=None)
    assert status == 401
    assert corpo["erro"] == "nao_autenticado"


def test_rota_inexistente_e_metodo_errado(chamar: Chamar) -> None:
    assert chamar("GET", "/nada")[0] == 404
    assert chamar("PATCH", "/perfil")[0] == 405


def test_perfil_inexistente(chamar: Chamar) -> None:
    status, corpo, _ = chamar("GET", "/perfil")
    assert status == 404
    assert corpo["erro"] == "perfil_inexistente"


def test_perfil_exige_consentimento(chamar: Chamar) -> None:
    status, corpo, _ = chamar("PUT", "/perfil", {"sexo": "feminino", "consentimento_aceito": False})
    assert status == 403
    assert corpo["erro"] == "consentimento_necessario"


def test_perfil_valida_sexo(chamar: Chamar) -> None:
    assert chamar("PUT", "/perfil", {"sexo": "x", "consentimento_aceito": True})[0] == 400


def test_perfil_mantem_data_do_consentimento(chamar: Chamar) -> None:
    _, primeiro, _ = chamar("PUT", "/perfil", {"sexo": "feminino", "consentimento_aceito": True})
    _, segundo, _ = chamar("PUT", "/perfil", {"sexo": "masculino", "consentimento_aceito": True})
    assert segundo["consentimento"] == primeiro["consentimento"]
    assert segundo["sexo"] == "masculino"
    assert chamar("GET", "/perfil")[1] == segundo


def test_registrar_dia_sem_consentimento(chamar: Chamar) -> None:
    status, corpo, _ = chamar("PUT", f"/dias/{hoje()}", registro())
    assert status == 403
    assert corpo["erro"] == "consentimento_necessario"


@pytest.mark.usefixtures("com_perfil")
def test_registrar_e_ler_o_dia(chamar: Chamar) -> None:
    status, dia, _ = chamar("PUT", f"/dias/{hoje()}", registro(sono_horas=5.5))
    assert status == 200
    assert dia["data"] == hoje()
    assert 0 <= dia["notas"]["energia"] <= 10
    assert set(dia["notas"]["habitos"]) == {"sono", "atividade", "agua", "alimentacao", "humor", "tela"}
    assert 1 <= len(dia["analise"]["sugestoes"]) <= 2
    assert dia["analise"]["fonte"] == "mock"
    assert dia["analise"]["aviso"] == "O Prumo não substitui orientação médica."
    assert chamar("GET", f"/dias/{hoje()}")[1] == dia


@pytest.mark.usefixtures("com_perfil")
def test_registro_repetido_da_mesma_nota(chamar: Chamar) -> None:
    primeira = chamar("PUT", f"/dias/{hoje()}", registro())[1]["notas"]
    segunda = chamar("PUT", f"/dias/{hoje()}", registro())[1]["notas"]
    assert primeira == segunda


@pytest.mark.usefixtures("com_perfil")
def test_registro_invalido(chamar: Chamar) -> None:
    status, corpo, _ = chamar("PUT", f"/dias/{hoje()}", registro(humor=9))
    assert status == 400
    assert corpo["erro"] == "dados_invalidos"


@pytest.mark.usefixtures("com_perfil")
def test_data_futura_ou_invalida(chamar: Chamar) -> None:
    amanha = (api.hoje_local() + timedelta(days=2)).isoformat()
    assert chamar("PUT", f"/dias/{amanha}", registro())[0] == 400
    assert chamar("PUT", "/dias/24-11-2026", registro())[0] == 400


def test_dia_inexistente(chamar: Chamar) -> None:
    assert chamar("GET", f"/dias/{hoje()}")[1]["erro"] == "dia_inexistente"


@pytest.mark.usefixtures("com_perfil")
def test_historico_usa_media_dos_dias_anteriores(chamar: Chamar) -> None:
    base = api.hoje_local()
    for i in range(3, 0, -1):
        chamar("PUT", f"/dias/{(base - timedelta(days=i)).isoformat()}", registro(sono_horas=8))
    dia = chamar("PUT", f"/dias/{base.isoformat()}", registro(sono_horas=6))[1]
    assert dia["notas"]["habitos"]["sono"]["media_7d"] == 8
    status, corpo, _ = chamar("GET", "/historico", query={"dias": "7"})
    assert status == 200
    datas = [p["data"] for p in corpo["dias"]]
    assert datas == sorted(datas)
    assert len(datas) == 4
    assert set(corpo["dias"][0]) == {
        "data",
        "energia",
        "sono_horas",
        "atividade_minutos",
        "agua_litros",
        "alimentacao_nota",
        "humor",
        "tela_horas",
    }


def test_historico_valida_parametro(chamar: Chamar) -> None:
    assert chamar("GET", "/historico", query={"dias": "500"})[0] == 400
    assert chamar("GET", "/historico", query={"dias": "abc"})[0] == 400


@pytest.mark.usefixtures("com_perfil")
def test_chat_responde_e_guarda(chamar: Chamar) -> None:
    chamar("PUT", f"/dias/{hoje()}", registro())
    status, corpo, _ = chamar("POST", "/chat", {"mensagem": "Como foi minha semana?"})
    assert status == 200
    assert corpo["fonte"] == "mock"
    assert "não substitui orientação médica" in corpo["resposta"]
    mensagens = chamar("GET", "/chat")[1]["mensagens"]
    assert [m["papel"] for m in mensagens] == ["usuario", "coach"]


@pytest.mark.usefixtures("com_perfil")
def test_chat_orienta_profissional_em_sintoma_preocupante(chamar: Chamar) -> None:
    corpo = chamar("POST", "/chat", {"mensagem": "Estou com DOR NO PEITO desde ontem"})[1]
    assert "profissional de saúde" in corpo["resposta"]
    assert "192" in corpo["resposta"]


@pytest.mark.usefixtures("com_perfil")
def test_chat_valida_mensagem(chamar: Chamar) -> None:
    assert chamar("POST", "/chat", {"mensagem": ""})[0] == 400
    assert chamar("POST", "/chat", {"mensagem": "x" * 501})[0] == 400


@pytest.mark.usefixtures("com_perfil")
def test_exportar_e_apagar_conta(chamar: Chamar, ambiente: RepositorioMemoria) -> None:
    chamar("PUT", f"/dias/{hoje()}", registro())
    chamar("POST", "/chat", {"mensagem": "oi"})
    exportado = chamar("GET", "/exportar")[1]
    assert exportado["perfil"]["sexo"] == "feminino"
    assert len(exportado["dias"]) == 1
    assert len(exportado["chat"]) == 2
    assert chamar("DELETE", "/conta")[0] == 204
    assert ambiente.exportar(USUARIO) == {"perfil": None, "dias": [], "chat": []}
    assert chamar("GET", "/perfil")[0] == 404


@pytest.mark.usefixtures("com_perfil")
def test_usuarios_isolados(chamar: Chamar) -> None:
    chamar("PUT", f"/dias/{hoje()}", registro())
    outro = "9a9a9a9a-0000-4000-8000-000000000002"
    assert chamar("GET", f"/dias/{hoje()}", usuario=outro)[0] == 404


def test_cors_origem_permitida(chamar: Chamar) -> None:
    _, _, cabecalhos = chamar("GET", "/saude", usuario=None, origem="http://localhost:5173")
    assert cabecalhos["Access-Control-Allow-Origin"] == "http://localhost:5173"
    status, _, cabecalhos = chamar("OPTIONS", "/dias/2026-11-24", usuario=None, origem="https://app.healthprumo.online")
    assert status == 204
    assert "PUT" in cabecalhos["Access-Control-Allow-Methods"]


def test_cors_origem_desconhecida(chamar: Chamar) -> None:
    _, _, cabecalhos = chamar("GET", "/saude", usuario=None, origem="https://site-estranho.com")
    assert "Access-Control-Allow-Origin" not in cabecalhos


def test_auth_local(chamar: Chamar, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_AUTH", "local")
    evento = {
        "rawPath": "/perfil",
        "headers": {"Authorization": "Bearer local-teste"},
        "requestContext": {"http": {"method": "GET"}},
    }
    assert api.handler(evento)["statusCode"] == 404  # autenticado, ainda sem perfil
    evento["headers"] = {"Authorization": "Bearer outro"}
    assert api.handler(evento)["statusCode"] == 401


def test_auth_local_bloqueado_na_lambda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_AUTH", "local")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "prumo-dev-api")
    evento = {
        "rawPath": "/perfil",
        "headers": {"Authorization": "Bearer local-teste"},
        "requestContext": {"http": {"method": "GET"}},
    }
    assert api.handler(evento)["statusCode"] == 500


def test_corpo_invalido(chamar: Chamar) -> None:
    evento = {
        "rawPath": "/perfil",
        "body": "{nao é json",
        "requestContext": {"http": {"method": "PUT"}, "authorizer": {"jwt": {"claims": {"sub": USUARIO}}}},
    }
    assert api.handler(evento)["statusCode"] == 400


def test_tarefa_diaria() -> None:
    assert api.handler({"source": "aws.scheduler"}) == {"ok": True}


def test_chat_some_depois_de_7_dias() -> None:
    from datetime import datetime, timedelta

    from prumo_api.repositorio import RepositorioMemoria, chat_vigente

    agora = datetime(2026, 11, 24, 12, tzinfo=UTC)
    assert chat_vigente({"em": (agora - timedelta(days=6, hours=23)).isoformat()}, agora)
    assert not chat_vigente({"em": (agora - timedelta(days=7, minutes=1)).isoformat()}, agora)

    repo = RepositorioMemoria(None)
    velha = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    nova = datetime.now(UTC).isoformat()
    repo.adicionar_chat("u1", "usuario", "antiga", velha)
    repo.adicionar_chat("u1", "usuario", "recente", nova)
    assert [m["texto"] for m in repo.listar_chat("u1", 50)] == ["recente"]
    assert [m["texto"] for m in repo.exportar("u1")["chat"]] == ["recente"]
