# AGENTS.md — prumo-api

API do **Prumo**, o coach de bem-estar com IA que responde "como estou hoje?" (FMU Tech Inovação 2026.2, ODS 3).

**Antes de qualquer tarefa, leia o contexto geral** em [Health-Prumo/prumo/AGENTS.md](https://github.com/Health-Prumo/prumo/blob/main/AGENTS.md): o que é o Prumo, decisões, LGPD, AWS e convenções. Este arquivo traz só o que é específico da API.

## Estado atual

Primeira versão funcional (Checkpoint 2): todas as rotas do contrato, motor de regras com testes, Coach em modo mock e com o Bedrock (Nova Micro), DynamoDB e servidor local. Visão geral, rotas, regras e deploy no [README](README.md).

| Onde | O quê |
|---|---|
| `src/prumo_api/handler.py` | entrada `prumo_api.handler.handler`, rotas, auth, CORS |
| `src/prumo_api/regras.py` | motor de regras determinístico (pesos provisórios em `PRUMO_PESOS`) |
| `src/prumo_api/data/referencias.json` | metas oficiais com fonte e ano; populacional (Vigitel/PNS) ainda pendente |
| `src/prumo_api/ia.py` | card e Coach; resposta do LLM validada, com volta ao mock se vier fora do formato |
| `src/prumo_api/repositorio.py` | DynamoDB ou memória/arquivo local |
| `scripts/build.sh`, `scripts/deploy.sh` | pacote `dist/lambda.zip` e publicação em `prumo-<ambiente>-api` |

Pendente: calibrar pesos e parâmetros provisórios com o grupo, indicadores populacionais no `referencias.json`, tarefa diária (hoje só registra a execução) e trechos curados para o RAG.

## Stack definida

- **Python** (3.12 local; na AWS, runtime Lambda Python em **arm64**).
- **Na AWS:** API Gateway **HTTP API** (payload 2.0, autorizador JWT do Cognito) → **AWS Lambda** em subnets privadas → **DynamoDB** e **Amazon Bedrock**. A infraestrutura é do Terraform ([tf-blueprint](https://github.com/Health-Prumo/tf-blueprint) e [tf-environments](https://github.com/Health-Prumo/tf-environments)), não deste repositório.
- **Local:** a mesma função `handler` deve rodar num servidor local em `http://localhost:8000`, para o front ([prumo-web](https://github.com/Health-Prumo/prumo-web)) desenvolver sem AWS.
- **Qualidade:** ruff, mypy, bandit e pytest (`make verificar`), mais gitleaks, rodando no GitHub Actions a cada push e pull request.
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
