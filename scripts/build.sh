#!/usr/bin/env bash
# Gera dist/lambda.zip com o pacote prumo_api e o data/referencias.json.
# Sem dependências externas: o boto3 já vem no runtime Python da Lambda.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf dist
mkdir -p dist/pacote
cp -r src/prumo_api dist/pacote/
find dist/pacote -name '__pycache__' -type d -prune -exec rm -rf {} +
(cd dist/pacote && python3 -m zipfile -c ../lambda.zip prumo_api)
rm -rf dist/pacote
echo "Gerado dist/lambda.zip ($(du -h dist/lambda.zip | cut -f1))"
