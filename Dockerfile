# syntax=docker/dockerfile:1

# Empacotamento futuro para Lambda. O modo AWS continua bloqueado pela aplicação.
FROM public.ecr.aws/lambda/python:3.12 AS lambda-deps
COPY requirements/ /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/production.txt --target /opt/deps

FROM public.ecr.aws/lambda/python:3.12 AS lambda
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=lambda-deps /opt/deps/ ${LAMBDA_TASK_ROOT}/
COPY main.py ${LAMBDA_TASK_ROOT}/
COPY function_module/ ${LAMBDA_TASK_ROOT}/function_module/
CMD ["main.lambda_handler"]

# Alvo padrão: protótipo local com HTTP e SQLite, sem ferramentas de teste na imagem.
FROM python:3.12-slim AS local
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PRUMO_AMBIENTE=local PRUMO_LLM_MODO=mock \
    PRUMO_HOST_LOCAL=0.0.0.0 PRUMO_PORTA=8000 \
    PRUMO_BANCO_LOCAL=/app/.local/prumo.sqlite3
WORKDIR /app
COPY requirements/ /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/local.txt \
    && groupadd --gid 10001 prumo \
    && useradd --uid 10001 --gid prumo --no-create-home prumo \
    && mkdir /app/.local \
    && chown prumo:prumo /app/.local
COPY main.py local_server.py ./
COPY function_module/ ./function_module/
USER 10001:10001
EXPOSE 8000
CMD ["python", "local_server.py"]
