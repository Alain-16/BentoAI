FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY alembic.ini README.md ./

RUN uv sync --frozen --no-dev


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 bentoai

WORKDIR /app

COPY --from=builder --chown=bentoai:bentoai /app/.venv /app/.venv
COPY --from=builder --chown=bentoai:bentoai /app/src /app/src
COPY --from=builder --chown=bentoai:bentoai /app/alembic /app/alembic
COPY --from=builder --chown=bentoai:bentoai /app/alembic.ini /app/alembic.ini
COPY --chown=bentoai:bentoai docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER bentoai

EXPOSE 8000

ENTRYPOINT [ "/app/docker-entrypoint.sh" ]

CMD ["uvicorn", "bentoai.main:app", "--host", "0.0.0.0", "--port", "8000"]

