FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md .env.example ./
COPY apps ./apps
COPY docs ./docs
COPY scripts ./scripts
COPY n8n ./n8n
COPY .github ./.github

RUN pip install --no-cache-dir -e ".[dev]"

# Run as non-root. The app persists artifacts to MinIO/Postgres only; the
# legacy /staging, /final, /logs bind mounts are not written by the app.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "apps.edr.app:app", "--host", "0.0.0.0", "--port", "8000"]
