# --- frontend build ---
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- backend + static ---
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 STATIC_DIR=/app/static STORAGE=firestore
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/dist ./static
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
