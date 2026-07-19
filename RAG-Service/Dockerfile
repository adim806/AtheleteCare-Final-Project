FROM python:3.11-slim

WORKDIR /app

# System dependencies for llama-cpp-python and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY models/ ./models/

# Pre-populate the vector store at build time (requires data/ to be present)
RUN python -m app.ingest || echo "WARNING: ingest skipped – run manually if data/ is empty"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
