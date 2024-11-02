# Use buildx syntax
FROM --platform=$TARGETPLATFORM python:3.9-slim

# Add platform-specific arguments
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Set working directory
WORKDIR /app

# Install system dependencies with platform-specific considerations
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    python3-dev \
    tesseract-ocr \
    git \
    # Handle platform-specific dependencies
    $(case "${TARGETPLATFORM}" in \
        "linux/amd64") echo "amd64-specific-package" ;; \
        "linux/arm64") echo "arm64-specific-package" ;; \
        *) echo "Unsupported platform: ${TARGETPLATFORM}" && exit 1 ;; \
    esac) \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster pip installs
RUN pip install "uv==$(pip index versions uv | grep -v 'a|b|rc' | head -n1)"

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies using uv
RUN uv pip install --no-cache-dir -r requirements.txt

# Create model directory and set it as a volume
RUN mkdir -p /app/model_artifacts
ENV DOCLING_MODELS_PATH=/app/model_artifacts

# Copy the model download script
COPY download_models.py .

# Download models during build with platform-specific handling
RUN case "${TARGETPLATFORM}" in \
        "linux/amd64") \
            echo "Downloading models for amd64..." && \
            python download_models.py \
            ;; \
        "linux/arm64") \
            echo "Downloading models for arm64..." && \
            python download_models.py \
            ;; \
        *) \
            echo "Unsupported platform: ${TARGETPLATFORM}" && exit 1 \
            ;; \
    esac

# Create directories for document processing
RUN mkdir -p /app/document_queue /app/document_processed

# Copy the rest of your application
COPY . .

# Expose the port your app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "docling_api.main:app", "--host", "0.0.0.0", "--port", "8000"]