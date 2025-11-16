# Use Python base image (needed for Flask and Perth)
FROM python:3.10-slim

# Define audiowmark version
ARG AUDIOWMARK_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# 1. Install all system dependencies
RUN set -eux; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
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
        ffmpeg \
        zstd && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Build and install audiowmark from source
RUN set -eux; \
    mkdir -p ${TEMP_DIR} && \
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${AUDIOWMARK_VERSION}/audiowmark-${AUDIOWMARK_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    tar -I zstd -xf /tmp/audiowmark.tar.zst -C "${TEMP_DIR}" --strip-components=1 && \
    cd "${TEMP_DIR}" && \
    ./autogen.sh && \
    ./configure \
        --prefix=/usr/local \
        --enable-single-precision \
        --disable-dependency-tracking && \
    make -j$(nproc) && \
    make install && \
    cd / && \
    rm -rf ${TEMP_DIR} /tmp/audiowmark.tar*

# 3. Set up Python application
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Verify audiowmark is available
RUN audiowmark --version || echo "Warning: audiowmark check failed"

# Expose port for Railway
EXPOSE 8000

# Run the Flask app with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:app"]
