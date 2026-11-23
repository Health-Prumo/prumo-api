"""Persistência somente local, com as chaves previstas para o DynamoDB."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class RepositorioSQLite:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute(
                "CREATE TABLE IF NOT EXISTS itens ("
                "pk TEXT NOT NULL, sk TEXT NOT NULL, dados TEXT NOT NULL, PRIMARY KEY (pk, sk))"
            )

    def _conectar(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho, timeout=10)
        conexao.execute("PRAGMA secure_delete = ON")
        return conexao

    def obter(self, usuario: str, chave: str) -> dict[str, Any] | None:
        with closing(self._conectar()) as conexao:
            linha = conexao.execute(
                "SELECT dados FROM itens WHERE pk = ? AND sk = ?", (f"USUARIO#{usuario}", chave)
            ).fetchone()
        return json.loads(linha[0]) if linha else None

    def salvar(self, usuario: str, chave: str, dados: dict[str, Any]) -> None:
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute(
                "INSERT INTO itens (pk, sk, dados) VALUES (?, ?, ?) "
                "ON CONFLICT(pk, sk) DO UPDATE SET dados = excluded.dados",
                (
                    f"USUARIO#{usuario}",
                    chave,
                    json.dumps(dados, ensure_ascii=False, allow_nan=False),
                ),
            )

    def listar(self, usuario: str) -> list[tuple[str, dict[str, Any]]]:
        with closing(self._conectar()) as conexao:
            linhas = conexao.execute(
                "SELECT sk, dados FROM itens WHERE pk = ? ORDER BY sk", (f"USUARIO#{usuario}",)
            ).fetchall()
        return [(chave, json.loads(dados)) for chave, dados in linhas]

    def apagar(self, usuario: str) -> None:
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute("DELETE FROM itens WHERE pk = ?", (f"USUARIO#{usuario}",))
