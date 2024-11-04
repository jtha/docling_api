# Set base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster pip installs
RUN pip install --upgrade pip && \
    pip install uv

# Copy requirements.txt
COPY requirements.txt .

# Install PyTorch CPU dependencies first
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN uv pip install --system --no-cache-dir torch==2.3.1+cpu torchvision==0.18.1+cpu --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Create model directory and set it as a volume
RUN mkdir -p /app/model_artifacts
ENV DOCLING_MODELS_PATH=/app/model_artifacts

# Copy the model download script
COPY download_models.py .

# Download models
RUN python download_models.py

# Create directories for document processing
RUN mkdir -p /app/document_queue /app/document_processed

# Copy the rest of your application
COPY . .

# Expose the port your app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "docling_api.main:app", "--host", "0.0.0.0", "--port", "8000"]