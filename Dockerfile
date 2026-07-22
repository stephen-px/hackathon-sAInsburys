FROM python:3.11-slim

WORKDIR /app

# System deps (none needed beyond Python stdlib for SQLite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY sainsburys/ ./sainsburys/

RUN pip install --no-cache-dir \
    slack-bolt \
    anthropic \
    apscheduler \
    python-dotenv \
    flask

# Default command — overridden per service in docker-compose.yml
CMD ["python", "sainsburys/app.py"]
