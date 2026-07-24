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

# OCR system dependencies: the Tesseract engine + French language data, and poppler
# (pdf2image rasterises scanned PDFs). Everything else is psycopg[binary]'s bundled
# libpq, so no system libpq is needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fra poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Install pinned dependencies (uv resolves from pyproject); then the package.
COPY pyproject.toml uv.lock* README.md ./
COPY apx/ ./apx/
RUN uv pip install --system --no-cache .

# The built SPA, served by the app at APX_WEB_DIST (its default path).
COPY --from=web /web/dist ./apx/web/dist
ENV APX_WEB_DIST=/app/apx/web/dist
# OCR is available in this image (Tesseract installed above), so enable the fallback.
ENV APX_OCR=1
# Behind HTTPS in deployment: mark the session cookie Secure and send HSTS.
ENV APX_COOKIE_SECURE=1
# Behind the platform's proxy: trust its appended X-Forwarded-For (rightmost entry) for the
# rate-limit/audit client IP. Only safe because the proxy fronts the app — never set this
# when the app is directly reachable (the header would be client-spoofable).
ENV APX_TRUST_FORWARDED_FOR=1
# Encryption in transit to the store (AD-31): require TLS on the DB connection. A hosted
# managed Postgres offers it; a same-machine loopback may override APX_DB_SSLMODE=disable.
ENV APX_DB_SSLMODE=require
# Encryption at rest (AD-31): BOTH layers are supplied per-deployment, never baked here.
#  - layer 1, APX_ENCRYPTION_KEY (the application key), and
#  - layer 2, APX_VOLUME_ENCRYPTED (the operator's attestation that the data volume is
#    encrypted, backed by a provider-managed encrypted volume or dm-crypt/LUKS).
# Baking APX_VOLUME_ENCRYPTED=1 into the image would be a permissive default — the gate would
# pass on an unencrypted disk with no conscious act. The start-up gate refuses to boot unless
# the deployment sets both. (Same reasoning as never baking the key: the attestation must be
# a deliberate per-deployment decision.)

COPY alembic.ini ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
# APX_SECRET_KEY and APX_ENCRYPTION_KEY are required (no insecure default — the start-up gate
# refuses to boot without the encryption key); DATABASE_URL points at Postgres;
# LLM_API_KEY / MISTRAL_API_KEY are optional (the cascade runs offline without them).
ENTRYPOINT ["/entrypoint.sh"]
