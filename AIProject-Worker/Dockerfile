FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./
COPY worker worker
COPY main.py ./

RUN pip install --no-cache-dir .

CMD ["python", "main.py"]
