# Use Python base image (Perth requires Python)
FROM python:3.10-slim

# Define audiowmark version
ARG AUDIOWMARK_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# 1. Install all system dependencies (Perth + Audiowmark + SSL certs!)
RUN set -eux; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        # SSL certificates for curl
        ca-certificates \
        # Audiowmark build dependencies
        build-essential \
        automake \
        autoconf \
        libtool \
        curl \
        pkg-config \
        libfftw3-dev \
        libsndfile1-dev \
        libsndfile1 \
        libgcrypt-dev \
        libzita-resampler-dev \
        libmpg123-dev \
        zstd \
        # Perth and audio processing dependencies
        ffmpeg \
        git \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Build and install audiowmark from source
RUN set -eux; \
    mkdir -p ${TEMP_DIR} && \
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${AUDIOWMARK_VERSION}/audiowmark-${AUDIOWMARK_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    zstd -d /tmp/audiowmark.tar.zst -o /tmp/audiowmark.tar && \
    tar -xf /tmp/audiowmark.tar -C "${TEMP_DIR}" --strip-components=1 && \
    cd "${TEMP_DIR}" && \
    ./autogen.sh && \
    ./configure \
        --prefix=/usr/local \
        --enable-single-precision \
        --disable-dependency-tracking && \
    make -j$(nproc) && \
    make install && \
    cd / && \
    rm -rf ${TEMP_DIR} /tmp/audiowmark.*

# 3. Set up Python application
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Verify audiowmark is installed
RUN audiowmark --help || echo "Warning: audiowmark verification failed"

# Expose port (Railway typically uses PORT env variable)
EXPOSE 8000

# Start the API server with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:app"]
