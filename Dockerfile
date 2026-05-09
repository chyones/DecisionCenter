FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md .env.example ./
COPY apps ./apps
COPY docs ./docs
COPY scripts ./scripts
COPY n8n ./n8n
COPY .github ./.github

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "apps.edr.app:app", "--host", "0.0.0.0", "--port", "8000"]
