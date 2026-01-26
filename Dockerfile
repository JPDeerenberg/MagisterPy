FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

WORKDIR /app

COPY . /app

RUN pip install .

RUN playwright install chromium

ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]