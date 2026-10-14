FROM node:22-alpine AS ui-builder

WORKDIR /workspace/src/apps/claims-handler-ui
COPY src/apps/claims-handler-ui/package.json src/apps/claims-handler-ui/package-lock.json ./
RUN npm ci
COPY src/apps/claims-handler-ui/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /workspace
RUN apt-get update \
    && apt-get install -y --no-install-recommends libltdl7 libkrb5-3 libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.24
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY data ./data
COPY src/apps/claims-api ./src/apps/claims-api
COPY scripts/validation/runtime_smoke.py ./scripts/validation/runtime_smoke.py
COPY scripts/initialize_sql.py scripts/initialize_knowledge.py ./scripts/
COPY infrastructure/sql ./infrastructure/sql
COPY --from=ui-builder /workspace/src/apps/claims-handler-ui/dist ./src/apps/claims-handler-ui/dist

USER 10001:10001
EXPOSE 8000
CMD ["/workspace/.venv/bin/uvicorn", "app.main:app", "--app-dir", "src/apps/claims-api", "--host", "0.0.0.0", "--port", "8000"]
