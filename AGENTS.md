# AGENTS.md — prumo-api

API do **Prumo**, o coach de bem-estar com IA que responde "como estou hoje?" (FMU Tech Inovação 2026.2, ODS 3).

**Antes de qualquer tarefa, leia o contexto geral** em [Health-Prumo/prumo/AGENTS.md](https://github.com/Health-Prumo/prumo/blob/main/AGENTS.md): o que é o Prumo, decisões, LGPD, AWS e convenções. Este arquivo traz só o que é específico da API.

## Estado atual

Protótipo local implementado: servidor em `localhost:8000` chamando o mesmo
`main.handler` no formato HTTP API 2.0, SQLite, consentimento, registro diário,
histórico, exportação/exclusão e card mock. A nota permanece `null` com
`status_avaliacao=regras_pendentes` até aprovação das fórmulas e dos pesos.
Os adaptadores AWS, login real, chat, RAG e Scheduler ainda não estão implementados.
O modo local é bloqueado na Lambda. Instruções de execução e limites no README.
Organização inspirada no template `function-docker_py_lambda`: `main.py` fino,
`local_server.py`, rotas em `function_module/api.py`, decorator de erros, logs sem
dados sensíveis, scripts PowerShell/Bash e configurações VS Code. O comando anterior
`servidor_local.py` continua funcionando. Docker local é opcional; o alvo `lambda`
é somente preparação de empacotamento, sem liberar execução AWS.

## Stack definida

- **Python** (3.12 local; na AWS, runtime Lambda Python em **arm64**).
- **Na AWS:** API Gateway **HTTP API** (payload 2.0, autorizador JWT do Cognito) → **AWS Lambda** em subnets privadas → **DynamoDB** e **Amazon Bedrock**. A infraestrutura é do Terraform ([tf-blueprint](https://github.com/Health-Prumo/tf-blueprint) e [tf-environments](https://github.com/Health-Prumo/tf-environments)), não deste repositório.
- **Local:** a mesma função `handler` deve rodar num servidor local em `http://localhost:8000`, para o front ([prumo-web](https://github.com/Health-Prumo/prumo-web)) desenvolver sem AWS.
- **Testes** com pytest e lint com ruff, rodando no GitHub Actions a cada push e pull request.
- **Configuração** por variáveis de ambiente, documentadas num `.env.example`.

## Responsabilidades da API

1. **Registro do dia:** sono, atividade física, água, alimentação, humor/energia e tempo de tela.
2. **Motor de regras (determinístico):** calcula a nota de energia (0 a 10) e a avaliação de cada hábito, comparando com a média dos últimos 7 dias do usuário e com as metas oficiais. Regras em `docs/03-solucao.md` do repositório `prumo`. Os pesos da nota ainda serão definidos pelo grupo: **não invente pesos**, deixe-os configuráveis e documentados.
3. **Card "Seu dia" pelo LLM:** recebe os números prontos e escreve o texto com no máximo 2 sugestões.
4. **Histórico** para os gráficos e **chat** do Coach (função secundária).
5. **Tarefa diária** disparada pelo EventBridge Scheduler.

## Regras que não podem ser quebradas

- **O código calcula; o LLM só explica.** A nota nunca sai do LLM. Os mesmos dados dão sempre a mesma nota, e isso precisa ter teste.
- **Ao LLM vão só números e o resumo do histórico**, nunca nome, e-mail ou outro identificador (LGPD: dado de saúde é sensível).
- **Modelo:** Amazon Nova Micro (`amazon.nova-micro-v1:0`) pela API Converse do Bedrock, com o ID numa variável de ambiente. Não use Claude no Bedrock: é cobrado pelo AWS Marketplace, fora dos créditos da conta.
- **Modo mock do LLM** (respostas fixas, sem custo) é o padrão no desenvolvimento e nos testes. Só use o Bedrock de verdade de propósito.
- **Limites de custo:** `maxTokens` de 400 na saída; o histórico do chat vai resumido, nunca inteiro.
- **Sem diagnóstico:** se o usuário relatar sintomas preocupantes, a resposta orienta procurar um profissional de saúde.
- **Exportar e apagar:** o usuário pode exportar e apagar todos os seus dados.
- **Fontes científicas (RAG):** a curadoria está em `docs/07-pesquisa-rag.md` do `prumo`. Evite banco vetorial gerenciado (Bedrock Knowledge Bases com OpenSearch Serverless custa mais de US$ 100 por mês); prefira trechos curados versionados no repositório.

## Modelo de dados (DynamoDB, tabela única)

| PK | SK | Conteúdo |
|---|---|---|
| `USUARIO#<id>` | `PERFIL` | dados do perfil e consentimento |
| `USUARIO#<id>` | `DIA#<aaaa-mm-dd>` | registro do dia e notas calculadas |
| `USUARIO#<id>` | `CHAT#<timestamp>` | mensagens do Coach, com TTL no atributo `expira_em` (90 dias) |

O `<id>` é o `sub` do token do Cognito.

## Convenções

- Código, comentários e mensagens em português do Brasil (nomes em inglês são aceitos, mas mantenha um padrão por módulo).
- Commits em português, no imperativo ("Adiciona…", "Corrige…"), com a identidade git pessoal do integrante.
- Rode testes e lint antes de commitar.
- Não commite `.venv/`, `__pycache__/` nem `.env` com valores reais. Nunca coloque chave de acesso da AWS no código.
