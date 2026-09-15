FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY alembic.ini ./
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations

RUN uv pip install --system .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations

RUN useradd --system --create-home appuser && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
