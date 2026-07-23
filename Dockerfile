# APX — one artifact (AD-3): the FastAPI app serves the API and the built SPA.
# Multi-stage: build the web, then a slim Python runtime.

# ── build the SPA ──
FROM node:20-slim AS web
WORKDIR /web
COPY apx/web/package.json apx/web/package-lock.json* ./
RUN npm ci
COPY apx/web/ ./
RUN npm run build

# ── the runtime ──
FROM python:3.13-slim
WORKDIR /app

# psycopg[binary] bundles libpq, so no system libpq is needed.
RUN pip install --no-cache-dir uv

# Install pinned dependencies (uv resolves from pyproject); then the package.
COPY pyproject.toml uv.lock* README.md ./
COPY apx/ ./apx/
RUN uv pip install --system --no-cache .

# The built SPA, served by the app at APX_WEB_DIST (its default path).
COPY --from=web /web/dist ./apx/web/dist
ENV APX_WEB_DIST=/app/apx/web/dist

COPY alembic.ini ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
# APX_SECRET_KEY is required (no insecure default); DATABASE_URL points at Postgres;
# LLM_API_KEY / MISTRAL_API_KEY are optional (the cascade runs offline without them).
ENTRYPOINT ["/entrypoint.sh"]
