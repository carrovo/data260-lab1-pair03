FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY workers/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app/backend

# One image for all three workers. WORKER_NAME, KAFKA_BOOTSTRAP and
# MONGO_URL are set by Docker Compose or the Kubernetes Deployment.
CMD ["python", "-m", "backend.workers.run"]
