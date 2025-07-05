FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
        python3-dev \
        build-essential \
        g++ \
        git \
        unixodbc-dev \
        freetds-dev \
        libodbc1 \
        odbcinst && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code
COPY . .

# Create media directory (STATIC_ROOT is handled by collectstatic)
# Your settings.py defines MEDIA_ROOT as BASE_DIR / 'tmp'
RUN mkdir -p /usr/src/app/tmp

EXPOSE 8000

# DEBUGGING: List all files to check the container's file structure
CMD ["ls", "-R"]