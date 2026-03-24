FROM node:22-bookworm-slim AS web-builder

WORKDIR /build/web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    INDEXTTS_STUDIO_ROOT=/app \
    INDEXTTS_STUDIO_HOST=0.0.0.0 \
    INDEXTTS_STUDIO_PORT=8000 \
    INDEXTTS_STUDIO_DATA_DIR=/app/data

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md README.en.md ./
COPY app ./app
COPY data ./data

RUN uv sync --frozen --no-dev

COPY --from=web-builder /build/web/dist ./web/dist

EXPOSE 8000

CMD ["/app/.venv/bin/indextts-studio", "serve"]
