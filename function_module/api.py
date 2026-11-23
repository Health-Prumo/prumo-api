"""Roteamento HTTP; delega os casos de uso aos serviços do Prumo."""

import re
from typing import Any

from function_module.errors import ErroAPI
from function_module.io.http import identificar_usuario, ler_corpo, resposta
from function_module.io.sqlite import RepositorioSQLite
from function_module.logic.schemas import PerfilSchema, RegistroDiaSchema, validar_data
from function_module.servicos import ServicoPrumo
from function_module.settings import carregar_configuracao


def encaminhar(evento: dict[str, Any]) -> dict[str, Any]:
    config = carregar_configuracao()
    if evento.get("version") != "2.0":
        raise ErroAPI(400, "evento_invalido", "Use um evento HTTP API payload 2.0.")
    contexto = evento.get("requestContext") or {}
    metodo = (contexto.get("http") or {}).get("method", "")
    caminho = evento.get("rawPath", "")
    if metodo == "OPTIONS":
        return resposta(204)
    if caminho == "/health" and metodo == "GET":
        return resposta(200, {"status": "ok", "ambiente": config.ambiente, "llm": "mock"})
    usuario = identificar_usuario(evento)
    rota_dia = re.fullmatch(r"/dias/([^/]+)", caminho)
    metodos = {
        "/health": {"GET"},
        "/perfil": {"PUT"},
        "/historico": {"GET"},
        "/dados/exportacao": {"GET"},
        "/dados": {"DELETE"},
    }
    permitidos = {"GET", "PUT"} if rota_dia else metodos.get(caminho)
    if permitidos is None:
        raise ErroAPI(404, "rota_nao_encontrada", "Rota não encontrada.")
    if metodo not in permitidos:
        retorno = resposta(
            405, {"erro": {"codigo": "metodo_invalido", "mensagem": "Método não permitido."}}
        )
        retorno["headers"]["allow"] = ", ".join(sorted(permitidos))
        return retorno
    servico = ServicoPrumo(RepositorioSQLite(config.banco_local))
    if caminho == "/perfil":
        perfil = PerfilSchema().load(ler_corpo(evento))
        return resposta(200, servico.salvar_perfil(usuario, perfil))
    if rota_dia:
        data_dia = validar_data(rota_dia.group(1)).isoformat()
        if metodo == "PUT":
            registro = RegistroDiaSchema().load(ler_corpo(evento))
            return resposta(200, servico.salvar_dia(usuario, data_dia, registro))
        return resposta(200, servico.obter_dia(usuario, data_dia))
    if caminho == "/historico":
        parametros = evento.get("queryStringParameters") or {}
        if set(parametros) - {"inicio", "fim"}:
            raise ErroAPI(400, "parametro_invalido", "Use apenas inicio e fim na consulta.")
        inicio = validar_data(parametros.get("inicio", "0001-01-01")).isoformat()
        fim = validar_data(parametros.get("fim", "9999-12-31")).isoformat()
        if inicio > fim:
            raise ErroAPI(400, "intervalo_invalido", "inicio deve ser anterior ou igual a fim.")
        return resposta(200, servico.historico(usuario, inicio, fim))
    if caminho == "/dados/exportacao":
        return resposta(200, servico.exportar(usuario))
    servico.apagar(usuario)
    return resposta(204)
