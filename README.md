# prumo-api

API do **Prumo**, o coach de bem-estar com IA que responde "como estou hoje?". Projeto do FMU Tech Inovação 2026.2, ODS 3.

A proposta, as regras de pontuação e a arquitetura ficam no repositório central [Health-Prumo/prumo](https://github.com/Health-Prumo/prumo). Detalhes para quem for contribuir (pessoas ou agentes de IA) em [AGENTS.md](AGENTS.md).

## Como funciona

```
Registro do dia ─► regras.py (nota determinística) ─► ia.py (texto do card) ─► DynamoDB
                     metas de data/referencias.json      Nova Micro ou mock
```

- **O código calcula, o LLM só explica.** A nota de energia e a avaliação de cada hábito saem de `regras.py`. Ao LLM vão só números e rótulos, sem nome, e-mail ou id.
- **Modo mock** (padrão): textos fixos, sem custo. O Bedrock só é usado com `PRUMO_IA=bedrock`.
- A mesma função `handler` roda na Lambda (API Gateway HTTP API, payload 2.0) e no servidor local.

| Arquivo | Papel |
|---|---|
| `src/prumo_api/handler.py` | rotas, autenticação, CORS, erros |
| `src/prumo_api/regras.py` | validação e motor de regras |
| `src/prumo_api/data/referencias.json` | metas oficiais com fonte e ano; parâmetros provisórios |
| `src/prumo_api/ia.py` | card "Seu dia" e Coach (mock ou Bedrock Converse) |
| `src/prumo_api/repositorio.py` | DynamoDB (tabela única) ou memória/arquivo local |
| `src/prumo_api/servidor_local.py` | servidor em `http://localhost:8000` |

## Rodar localmente

Requer Python 3.12.

```bash
make instalar   # cria .venv e instala as ferramentas
make local      # API em http://localhost:8000, IA em modo mock, login local
```

No modo local, qualquer `Authorization: Bearer local-<algo>` é aceito, e os dados ficam em `.dados-locais.json` (fora do git).

```bash
curl -X PUT localhost:8000/perfil -H 'Authorization: Bearer local-dev' \
  -H 'Content-Type: application/json' -d '{"sexo":"feminino","consentimento_aceito":true}'
```

## Rotas

| Método | Rota | O que faz |
|---|---|---|
| GET | `/saude` | verificação, sem login |
| GET / PUT | `/perfil` | perfil e consentimento (obrigatório para registrar) |
| GET / PUT | `/dias/{aaaa-mm-dd}` | registro do dia, notas e card "Seu dia" |
| GET | `/historico?dias=30` | pontos para os gráficos (1 a 90 dias) |
| GET / POST | `/chat` | conversa com o Coach |
| GET | `/exportar` | todos os dados do usuário |
| DELETE | `/conta` | apaga todos os dados do usuário |

O contrato completo (campos, tipos e erros) é o mesmo usado pelo [prumo-web](https://github.com/Health-Prumo/prumo-web).

## Regras de pontuação

| Hábito | Referência | Regra |
|---|---|---|
| Sono | 7 a 9 h (NSF, 2015) | 10 na faixa; abaixo, proporcional a 7 h; acima, cai até 0 em 18 h |
| Atividade | 150 min/semana (OMS, 2020) | soma do dia com os 6 anteriores; vigorosa vale 2, moderada 1, leve 0 (não entra na meta da OMS) |
| Água | 2,0 L mulheres / 2,5 L homens (EFSA, 2010) | proporcional à meta, até 10; sem sexo informado usa 2,0 L |
| Alimentação | Guia Alimentar (2014) | base 2, +4 frutas e verduras, +4 refeição caseira, −4 ultraprocessados *(provisório)* |
| Humor | autodeclarado | 1 a 5 vira 0 a 10 |
| Tela no lazer | Vigitel: 3 h ou mais por dia | 10 até 1 h, cai até 0 em 6 h *(provisório)* |

A **nota de energia** é a média ponderada das seis notas. **Os pesos são provisórios** (todos 1) até o grupo definir; para testar outra combinação, use `PRUMO_PESOS`. Cada hábito também traz a média dos 7 dias anteriores do próprio usuário.

Os indicadores populacionais do Vigitel e da PNS ainda não entram no cálculo: estão marcados como pendentes em `referencias.json`.

## Testes e qualidade

```bash
make verificar   # ruff, mypy, bandit e pytest
```

O GitHub Actions roda o mesmo a cada push e pull request, gera o pacote da Lambda e procura segredos com o gitleaks.

## Variáveis de ambiente

Ver [`.env.example`](.env.example).

| Variável | Uso |
|---|---|
| `PRUMO_TABELA` | nome da tabela do DynamoDB (sem ela, usa memória/arquivo local) |
| `PRUMO_IA` | `mock` (padrão) ou `bedrock` |
| `PRUMO_MODELO_ID` | padrão `amazon.nova-micro-v1:0` |
| `PRUMO_ORIGENS` | origens liberadas no CORS, separadas por vírgula |
| `PRUMO_AUTH` | `local` só no desenvolvimento (bloqueado na Lambda) |
| `PRUMO_PESOS` | pesos da nota de energia em JSON (opcional) |
| `PRUMO_FUSO_HORAS` | fuso do "hoje" (padrão −3) |

## Deploy

A infraestrutura (Lambda `prumo-dev-api`, API Gateway, DynamoDB, Cognito) vem do Terraform em [tf-environments](https://github.com/Health-Prumo/tf-environments). Este repositório só publica o código:

```bash
aws login --profile prumo
make deploy      # build + aws lambda update-function-code em prumo-dev-api
```

O script confere se a conta é a do Prumo antes de publicar. Handler da Lambda: `prumo_api.handler.handler` (Python 3.12, arm64).
