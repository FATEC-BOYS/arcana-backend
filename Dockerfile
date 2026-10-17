FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ make && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.lock ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.lock && rm -rf /wheels && useradd --create-home arcana
COPY pyproject.toml README.md LICENSE NOTICE.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY evaluations ./evaluations
USER arcana
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
