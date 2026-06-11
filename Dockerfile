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

# Run as non-root. Entra revalidation updates one redacted runtime evidence
# marker; keep that file writable without granting write access to the source tree.
RUN useradd --create-home --uid 10001 appuser \
    && chown appuser:appuser \
        /app/docs/evidence/uat/ENTRA_CONNECTOR_TRUTH_REVALIDATION_2026-06-08.md
USER appuser

EXPOSE 8000

CMD ["uvicorn", "apps.edr.app:app", "--host", "0.0.0.0", "--port", "8000"]
