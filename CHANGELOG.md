# Histórico de alterações

## Não lançado

- Adapta a organização do template com handler fino, rotas e tratamento HTTP separados.
- Centraliza erros e logs operacionais sem dados de saúde, tokens ou identificadores.
- Adiciona scripts PowerShell/Bash, comandos compartilhados com CI e depuração VS Code.
- Adiciona Docker local opcional e alvo de empacotamento Lambda para uma etapa futura.
- Preserva `servidor_local.py` como entrada compatível com `local_server.py`.
- Adiciona servidor local que executa o handler HTTP API 2.0.
- Adiciona consentimento, registro diário, histórico, exportação e exclusão.
- Persiste dados locais em SQLite e apresenta card mock sem custo.
- Mantém a nota pendente até aprovação das fórmulas e dos pesos.
- Substitui exemplos de livros pelo contrato de registros do Prumo.
- Configura ruff, mypy, pytest, bandit, gitleaks, CodeQL e Dependabot.
- Protege arquivos de ambiente e documenta o fluxo de desenvolvimento local.

## Estrutura inicial

- Organiza módulos de lógica, integrações, requisitos e testes.
