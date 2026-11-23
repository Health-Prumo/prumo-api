# prumo-api

API do **Prumo**, o coach de bem-estar com IA que responde "como estou hoje?".

Protótipo local em Python 3.12, com Flask como adaptador HTTP, handler no formato
API Gateway HTTP API 2.0, SQLite e respostas mock. Não exige conta AWS, credenciais
ou Docker. Use dados fictícios: a identidade local é compartilhada por todas as
requisições dessa instância.

A proposta e as decisões estão no [repositório central](https://github.com/Health-Prumo/prumo).
Leia também [AGENTS.md](AGENTS.md).

## Iniciar no Windows / PowerShell

Na raiz do repositório:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/development.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe local_server.py
```

Copie o exemplo somente se ainda não tiver um `.env`. Não é necessário ativar a
venv nem alterar a política de execução do PowerShell. Se o projeto foi movido e
a venv deixou de funcionar, recrie-a com uma instalação válida de Python 3.12.

A API atende em **http://localhost:8000**, vinculada apenas a `127.0.0.1`.
O comando anterior `python servidor_local.py` continua disponível por compatibilidade.
Em outro terminal:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

No Linux/macOS, use `python3.12 -m venv .venv` e `.venv/bin/python` nos comandos.

## Experimentar o fluxo

O consentimento abaixo é um contrato técnico de demonstração para dados fictícios,
versão `prototipo-local-v1`. Não substitui a preparação do termo real do produto.

```powershell
$api = 'http://localhost:8000'
$perfil = Get-Content -Raw -Encoding UTF8 examples/perfil.json
$registro = Get-Content -Raw -Encoding UTF8 examples/registro-dia.json

Invoke-RestMethod "$api/perfil" -Method Put -ContentType 'application/json' -Body $perfil
Invoke-RestMethod "$api/dias/2026-11-23" -Method Put -ContentType 'application/json' -Body $registro
Invoke-RestMethod "$api/dias/2026-11-23"
Invoke-RestMethod "$api/historico?inicio=2026-11-01&fim=2026-11-30"
Invoke-RestMethod "$api/dados/exportacao"
```

Para apagar **todos os dados do usuário local**, incluindo o consentimento:

```powershell
Invoke-RestMethod "$api/dados" -Method Delete
```

Depois da exclusão, é necessário registrar o consentimento novamente.
Os dados sobrevivem ao reinício do servidor em `.local/prumo.sqlite3`.
Essa pasta e os arquivos de ambiente são ignorados pelo Git.

## Contrato HTTP

| Método e rota | Resultado |
|---|---|
| `GET /health` | Estado da API; não verifica a disponibilidade do banco |
| `PUT /perfil` | Registra consentimento e versão do termo; data/hora atribuída pelo servidor |
| `PUT /dias/{AAAA-MM-DD}` | Substitui o registro completo do dia; repetir não cria duplicata |
| `GET /dias/{AAAA-MM-DD}` | Registro, resumo do histórico e card mock |
| `GET /historico?inicio=...&fim=...` | Dias em ordem crescente, limites inclusivos e opcionais |
| `GET /dados/exportacao` | Todos os itens armazenados do usuário |
| `DELETE /dados` | Exclui todos os itens do usuário e responde 204 |

Envie `Content-Type: application/json` em requisições PUT. O limite é 64 KiB.
Consulte [examples/registro-dia.json](examples/registro-dia.json) para os campos.
Todos são obrigatórios. Campos desconhecidos são rejeitados, incluindo identificadores
e notas enviados pelo cliente. Datas são dias de calendário informados pelo front,
sem conversão implícita de fuso horário.

Horas aceitam decimais de 0 a 24; qualidade do sono, humor e energia aceitam inteiros
de 1 a 5; atividade aceita minutos inteiros de 0 a 1440 e intensidade
`leve`, `moderada` ou `vigorosa`; água aceita litros de 0 a 20.
Esses limites são validações técnicas, **não recomendações de saúde**.
As respostas de alimentação são booleanas.

Erros usam `{"erro": {"codigo": "...", "mensagem": "..."}}`.
Validação retorna 422 e `erro.campos`; JSON inválido retorna 400, identidade ausente
401, consentimento ausente 403, recurso inexistente 404, método incorreto 405,
corpo grande 413, tipo de conteúdo incorreto 415 e indisponibilidade 503.
Falhas inesperadas retornam 500 sem detalhes internos.

O frontend deve aceitar:

```json
{
  "nota": null,
  "status_avaliacao": "regras_pendentes",
  "resumo_historico": {"dias_registrados": 0, "medias": {}},
  "card": {"modo": "mock"}
}
```

Esse trecho mostra apenas parte da resposta. O card completo contém título, texto,
até duas sugestões e o aviso de que o Prumo não substitui orientação médica.
Não apresenta diagnóstico nem nota simulada.

## Cálculo e limitações do protótipo

A média usa os **sete dias de calendário anteriores** à data consultada, excluindo
o próprio dia. Dias sem registro não são tratados como zero. Cada média informa
a quantidade de dias usados. Editar um registro passado atualiza as médias nas
consultas seguintes.

A nota 0–10 e a avaliação contra metas oficiais ainda não estão implementadas:
fórmulas, referências e pesos precisam ser aprovados pelo grupo. Não existe peso
padrão escondido. A próxima etapa deve versionar essas regras, carregar os pesos
por configuração validada e persistir a versão do cálculo junto da nota.

O modo mock não recebe identificadores, não chama LLM e não precisa de boto3.
Chat, RAG, Scheduler, Cognito real, DynamoDB e Bedrock permanecem pendentes.
Antes de ativar Bedrock, implementar Converse com
`amazon.nova-micro-v1:0` configurável, teto de 400 tokens, resumo permitido do
histórico e verificação de que os dados enviados não contêm identificadores.

O histórico e a exportação locais leem todos os itens do usuário. Paginação e
consultas por intervalo devem entrar no adaptador DynamoDB antes de uso em escala.
A exclusão cobre o banco ativo; cópias manuais e backups ficam fora do protótipo.

## Configuração

Veja [.env.example](.env.example). O servidor carrega o arquivo na raiz do projeto,
preservando valores já definidos no ambiente. Reinicie o servidor após alterar
configurações. Chamadas diretas ao handler leem as variáveis do processo, sem carregar
`.env` automaticamente.

| Variável | Padrão | Uso |
|---|---|---|
| `PRUMO_AMBIENTE` | `local` | Somente `local` ou `teste` |
| `PRUMO_PORTA` | `8000` | Porta do servidor |
| `PRUMO_HOST_LOCAL` | `127.0.0.1` | Interface local; `0.0.0.0` somente para escuta dentro do Docker |
| `PRUMO_ORIGEM_FRONT` | `http://localhost:5173` | Origem exata permitida pelo CORS local |
| `PRUMO_USUARIO_LOCAL` | `usuario-demo` | Identidade fictícia fixada pelo servidor |
| `PRUMO_BANCO_LOCAL` | `.local/prumo.sqlite3` | Caminho absoluto ou relativo à raiz |
| `PRUMO_LLM_MODO` | `mock` | Outros modos falham explicitamente |

O servidor injeta a identidade no evento; headers e corpo não podem escolher outro
usuário. Isso **não implementa login real**. O handler lê
`requestContext.authorizer.jwt.claims.sub`, contrato que será preenchido pelo
autorizador Cognito na AWS. O modo local é bloqueado dentro da Lambda para impedir
uso acidental de SQLite ou autenticação de demonstração no deploy.

## Organização inspirada no template

O template `function-docker_py_lambda` foi consultado somente para leitura.
A organização aproveita suas entradas, scripts, logging e depuração, com adaptações
para o contrato e os dados do Prumo:

```text
main.py                         # lambda_handler e alias handler; sem regras de negócio
local_server.py                 # Adaptador HTTP API 2.0 na porta 8000
servidor_local.py               # Compatibilidade com o comando anterior
function_module/
  api.py                       # Rotas, identidade e coordenação HTTP
  errors.py                    # Erros públicos da aplicação
  servicos.py                  # Casos de uso: perfil, dias, histórico e dados
  settings.py                  # Configuração validada por ambiente
  logger.py                    # Status, duração e classe de erro; sem dados de saúde
  logic/
    decorator.py               # Fronteira do handler: erros e telemetria
    functions.py               # Cálculos determinísticos, sem I/O
    schemas.py                 # Validação Marshmallow dos contratos do Prumo
  io/
    http.py                    # Corpo JSON/base64 e respostas HTTP
    repositorio.py             # Contrato para adaptadores de persistência
    sqlite.py                  # Persistência do protótipo
    llm.py                     # Card mock sem rede
    aws.py                     # Local reservado aos adaptadores AWS futuros
scripts/
  dev.py                       # Comandos compartilhados por Windows, Bash e CI
  invoke.py                    # Executa um evento JSON sem abrir servidor
  __run_local_server.ps1/.sh    # Atalhos equivalentes aos do template
  __test.ps1/.sh
  __format_and_validate.ps1/.sh
requirements/
  base.txt                     # Dependências do handler
  local.txt                    # Adaptador HTTP, sem ferramentas de teste
  development.txt              # Local + ferramentas de qualidade
  production.txt               # Somente dependências do handler
  constraints.txt              # Versões resolvidas
tests/                         # Contrato, lógica, HTTP, configuração e scripts
examples/                      # Eventos e registros fictícios
.vscode/                       # Depuração, descoberta de testes e Ruff
Dockerfile                     # Alvos local (padrão) e lambda (preparação futura)
compose.yaml                   # Protótipo local com volume SQLite
```

O decorator preserva os status e o corpo HTTP sem criar outro envelope JSON.
O servidor não importa fixtures de testes. A configuração não busca segredos nem
abre clientes AWS durante imports. Os logs contêm apenas evento operacional,
status HTTP, duração e classe do erro, sem corpo, token, usuário ou traceback.
O mock, os pesos pendentes e o bloqueio do modo local na Lambda continuam ativos.

A tabela local usa `USUARIO#<id>` e `PERFIL | DIA#<data>`, preservando as chaves
previstas para o DynamoDB. Isso não emula todos os comportamentos do DynamoDB.
A infraestrutura AWS continua nos repositórios Terraform.

## Comandos de desenvolvimento e qualidade

Os comandos abaixo funcionam sem ativar a venv nem alterar políticas do PowerShell.
Todos usam `scripts/dev.py`, que interrompe a execução na primeira falha:

```powershell
.\.venv\Scripts\python.exe scripts/dev.py run
.\.venv\Scripts\python.exe scripts/dev.py test
.\.venv\Scripts\python.exe scripts/dev.py check
.\.venv\Scripts\python.exe scripts/dev.py format
.\.venv\Scripts\python.exe scripts/dev.py audit
.\.venv\Scripts\python.exe scripts/dev.py event examples/evento-health.json
```

`run` permanece aberto até Ctrl+C. `test` aceita argumentos adicionais do pytest.
`check` verifica lint, formatação, tipos e bandit; `format` aplica formatação e
correções automáticas antes de verificar. `audit` consulta vulnerabilidades online.
`event` carrega o `.env` e imprime a resposta do handler para o arquivo informado.

Também estão disponíveis `scripts/__run_local_server.ps1`, `scripts/__test.ps1` e
`scripts/__format_and_validate.ps1`. Em Bash/Git Bash, execute os equivalentes com
`bash scripts/__test.sh`, por exemplo. Esses atalhos encontram a venv a partir da
pasta do projeto, mesmo quando chamados de outro diretório.

No VS Code, selecione a venv e use **Prumo: API local** para depurar requisições HTTP
ou **Prumo: evento HTTP API 2.0** para depurar uma invocação isolada. Os testes são
descobertos automaticamente e a formatação usa Ruff.

## Docker local opcional

Com Docker e Compose instalados:

```powershell
docker compose up --build --wait
Invoke-RestMethod http://localhost:8000/health
docker compose down
```

O container executa como usuário sem privilégios e publica somente
`127.0.0.1:8000`. O volume `dados-prumo` persiste os registros entre reinícios;
`docker compose down` preserva esse volume. O banco do container é separado do
arquivo `.local/prumo.sqlite3` usado na execução direta. O `.dockerignore` limita
o contexto aos fontes e requisitos, excluindo ambientes, bancos, testes e caches.
O Compose define as variáveis explicitamente; não monta o `.env` da máquina.

O alvo `lambda` mantém o empacotamento em estágios do template, usando Python 3.12:

```powershell
docker build --platform linux/arm64 --target lambda -t prumo-api:lambda .
```

Esse alvo é **preparação de empacotamento, ainda não um deploy funcional**: os
adaptadores AWS e a autenticação real continuam pendentes. A configuração bloqueia
o uso de SQLite dentro da Lambda. A construção arm64 pode exigir emulação na
máquina de desenvolvimento. Não publique a imagem como aplicação pronta.

As imagens seguem as orientações de [imagens Python da AWS](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html)
e [builds em estágios do Docker](https://docs.docker.com/build/building/multi-stage/).

## Dependências e CI

As versões resolvidas ficam em `requirements/constraints.txt`; a instalação
carrega essas restrições via `base.txt`. Atualize dependências e restrições juntas,
rode as verificações e confira também a instalação Linux usada no CI.

O GitHub Actions usa os mesmos comandos em Windows e Linux a cada push e PR,
verifica o container local e configura gitleaks, CodeQL e Dependabot.
O hook de gitleaks usa Go; instale Go antes da primeira
execução do pre-commit. Depois:

```powershell
.\.venv\Scripts\python.exe -m pre_commit install
```

O hook verifica os arquivos preparados para commit. O CI verifica o histórico Git.
Nenhuma etapa faz deploy nem precisa de credenciais AWS.
