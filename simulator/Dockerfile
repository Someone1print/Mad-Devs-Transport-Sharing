FROM python:3.12-slim-bookworm

# uv binary, pinned to the version that produced uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "scootersim"]
