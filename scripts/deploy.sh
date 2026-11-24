#!/usr/bin/env bash
# Publica dist/lambda.zip na função da Lambda do ambiente (padrão: dev).
# Uso: scripts/deploy.sh [ambiente]
set -euo pipefail
cd "$(dirname "$0")/.."

AMBIENTE="${1:-dev}"
FUNCAO="prumo-${AMBIENTE}-api"
PERFIL="prumo"
REGIAO="us-east-1"
CONTA="444331926746"

conta_atual="$(aws sts get-caller-identity --profile "$PERFIL" --query Account --output text)"
if [ "$conta_atual" != "$CONTA" ]; then
  echo "Conta errada: $conta_atual (esperada $CONTA). Rode 'aws login --profile $PERFIL'." >&2
  exit 1
fi

scripts/build.sh

echo "Publicando em $FUNCAO..."
aws lambda update-function-code \
  --function-name "$FUNCAO" \
  --zip-file fileb://dist/lambda.zip \
  --profile "$PERFIL" --region "$REGIAO" \
  --query 'LastUpdateStatus' --output text

aws lambda wait function-updated-v2 --function-name "$FUNCAO" --profile "$PERFIL" --region "$REGIAO"
echo "Pronto: $FUNCAO atualizada."
