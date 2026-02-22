# ---- API Server (FastAPI) ----
FROM python:3.11-slim AS api

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
COPY api/requirements.txt ./api/
RUN pip install --no-cache-dir -r requirements.txt -r api/requirements.txt

# Copy source code
COPY history_tales_agent/ ./history_tales_agent/
COPY api/ ./api/

EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]


# ---- Web Frontend (Next.js) ----
FROM node:18-alpine AS web-builder

WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ .
RUN npm run build

FROM node:18-alpine AS web
WORKDIR /app/web
COPY --from=web-builder /app/web/.next/standalone ./
COPY --from=web-builder /app/web/.next/static ./.next/static
COPY --from=web-builder /app/web/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
