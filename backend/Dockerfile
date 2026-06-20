# Образ собирается из КОРНЯ проекта (context: .), чтобы в него попал и frontend.
#   docker build -f backend/Dockerfile .
FROM python:3.12-slim

# .pyc не пишем, stdout не буферизуем (логи видны сразу).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала зависимости — слой кешируется, пока requirements не меняются.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения и статический лендинг.
COPY backend/app ./app
COPY frontend ./frontend
ENV FRONTEND_DIR=/app/frontend

# Каталоги под логи и SQLite + непривилегированный пользователь.
RUN mkdir -p logs data && useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
