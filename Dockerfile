FROM node:22-alpine AS ui-builder

WORKDIR /workspace/src/apps/claims-handler-ui
COPY src/apps/claims-handler-ui/package.json src/apps/claims-handler-ui/package-lock.json ./
RUN npm ci
COPY src/apps/claims-handler-ui/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /workspace
RUN pip install --no-cache-dir uv==0.12.24
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY data ./data
COPY src/apps/claims-api ./src/apps/claims-api
COPY --from=ui-builder /workspace/src/apps/claims-handler-ui/dist ./src/apps/claims-handler-ui/dist

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--app-dir", "src/apps/claims-api", "--host", "0.0.0.0", "--port", "8000"]
