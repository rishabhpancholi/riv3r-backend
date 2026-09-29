# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.12.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/

# Install dependencies separately so application-only changes reuse this layer.
COPY pyproject.toml uv.lock ./
COPY docs/README.md ./docs/README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev && \
    groupadd --system app && \
    useradd --system --gid app --home-dir /app app && \
    chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
