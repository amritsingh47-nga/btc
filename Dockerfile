# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye

# Set environment variables
# PREVENT Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# PREVENT Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# Set the working directory to /app
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir python-multipart uvicorn gunicorn

# Copy the rest of the application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Run the signal engine + dashboard. Cycle interval comes from
# config.yaml (cycle.interval_minutes, default 15).
CMD ["python", "main.py", "--mode", "continuous"]
