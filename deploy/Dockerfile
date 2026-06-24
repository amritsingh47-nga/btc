FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
ENV PYTHONPATH=/app/src

# config.yaml and .env are mounted at runtime (see docker-compose.yml).
ENTRYPOINT ["python", "-m", "amazon_job_detector"]
CMD ["run", "--config", "/app/config.yaml"]
