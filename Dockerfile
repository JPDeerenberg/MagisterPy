FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir .

RUN playwright install --with-deps chromium-headless-shell

ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]