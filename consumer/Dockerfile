FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from root
COPY requirements.txt /tmp/

# Copy models module (includes __init__.py with class definitions and .pkl files)
COPY models /app/ml_models

# Copy consumer code
COPY consumer/ /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Set environment for Docker network and models location
ENV KAFKA_BROKER=kafka:29092
ENV REDIS_URL=redis://redis:6379
ENV ML_MODELS_DIR=/app/ml_models
ENV PYTHONPATH=/app:/app/ml_models

# Run the consumer pipeline
CMD ["python3", "pipeline.py"]
