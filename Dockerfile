FROM python:3.11-slim

WORKDIR /app

# Node + Xvfb back the /authenticate flow: vendor/uk-grocery-cli's auth-server
# drives a real (non-headless) Playwright/Chromium login, which needs a
# display — Xvfb gives it a virtual one. Only the `bot` service actually uses
# this; see docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg xvfb xauth \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY sainsburys/ ./sainsburys/
COPY vendor/uk-grocery-cli/ ./vendor/uk-grocery-cli/

RUN cd vendor/uk-grocery-cli \
    && npm install \
    && npx playwright install --with-deps chromium

RUN pip install --no-cache-dir \
    slack-bolt \
    anthropic \
    apscheduler \
    python-dotenv \
    flask \
    requests

# Default command — overridden per service in docker-compose.yml
CMD ["python", "sainsburys/app.py"]
