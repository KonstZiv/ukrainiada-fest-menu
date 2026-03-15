# Production image — multistage build with uv.
# Based on https://docs.astral.sh/uv/guides/integration/docker/

FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer, no source code needed).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable --no-dev

# Copy source and install project itself.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

# --- Runtime stage ---
FROM python:3.14-slim

RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

COPY --from=builder /app /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8000

CMD ["uvicorn", "core_settings.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
