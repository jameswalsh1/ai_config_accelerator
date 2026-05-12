FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/pyproject.toml
# Install a placeholder package so pip resolves dependencies from pyproject.toml
RUN pip install --no-cache-dir --no-build-isolation \
    "fastapi==0.115.12" \
    "uvicorn[standard]==0.34.0" \
    "pydantic==2.12.5" \
    "pydantic-settings==2.7.0" \
    "python-multipart==0.0.20" \
    "sqlalchemy[asyncio]==2.0.41" \
    "alembic==1.14.1" \
    "asyncmy==0.2.10" \
    "cryptography>=48.0.0"

COPY backend /app

RUN chmod +x /app/entrypoint.sh \
  && useradd --no-create-home --shell /bin/false appuser \
  && chown -R appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
