FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip install ".[mqtt]" && \
    pip install pytest pytest-asyncio

EXPOSE 8090

CMD ["python", "-m", "uvicorn", "second_brain.api.main:app", "--host", "0.0.0.0", "--port", "8090"]
