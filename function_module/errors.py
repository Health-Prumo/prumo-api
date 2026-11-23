"""Erros de aplicação com mensagens públicas e status HTTP definidos."""


class ErroAPI(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
