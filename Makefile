.PHONY: instalar local testes lint verificar build deploy

instalar:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

local:
	PYTHONPATH=src .venv/bin/python -m prumo_api.servidor_local

testes:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests
	.venv/bin/mypy
	.venv/bin/bandit -q -r src -c pyproject.toml

verificar: lint testes

build:
	scripts/build.sh

deploy:
	scripts/deploy.sh dev
