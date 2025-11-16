FROM debian:bookworm-slim
# -------------------------------------------------------------------
# Install audiowmark by building from source (v0.6.5)
# Note: This requires standard C/C++ build tools and development libraries.
# Assumes a Debian/Ubuntu-based base image (e.g., node:lts-slim or python:3.12-slim).
# -------------------------------------------------------------------

RUN set -eux; \
    # 1. Install build tools and dependencies
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        automake \
        autoconf \
        libtool \
        curl \
        pkg-config \
        libfftw3-dev \
        libsndfile1-dev \
        libgcrypt20-dev \
        libzita-resampler-dev \
        libmpg123-dev \
        ffmpeg \
        ffprobe && \
    # 2. Download and extract the latest stable source (v0.6.5)
    LATEST_VERSION="v0.6.5" && \
    TEMP_DIR="/tmp/audiowmark_build" && \
    mkdir -p ${TEMP_DIR} && \
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    # We must use zstd to decompress the .zst file, then tar to extract
    apt-get install -y --no-install-recommends zstd && \
    zstd -d /tmp/audiowmark.tar.zst -o /tmp/audiowmark.tar && \
    tar -xf /tmp/audiowmark.tar -C ${TEMP_DIR} --strip-components=1 && \
    # 3. Build and install
    cd ${TEMP_DIR} && \
    ./autogen.sh && \
    ./configure && \
    make -j$(nproc) && \
    make install && \
    # 4. Cleanup
    cd / && \
    rm -rf ${TEMP_DIR} /tmp/audiowmark.tar* && \
    apt-get purge -y build-essential automake autoconf libtool pkg-config zstd && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    
