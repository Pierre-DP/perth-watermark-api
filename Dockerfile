# -------------------------------------------------------------------
# STAGE 1: Build Stage (Recommended base image for 'apt-get' systems)
# -------------------------------------------------------------------
FROM debian:bookworm-slim

# Set working directory (optional, but good practice)
WORKDIR /app

# Install audiowmark by building from source (v0.6.5)
# This uses a single RUN command to minimize Docker layers and then cleans up
# build dependencies to keep the final image size small.
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
        ffmpeg && \
    # 2. Download and extract the latest stable source (v0.6.5)
    LATEST_VERSION="v0.6.5" && \
    TEMP_DIR="/tmp/audiowmark_build" && \
    mkdir -p ${TEMP_DIR} && \
    # Download the source archive (.tar.zst)
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    # Install zstd to decompress the archive
    apt-get install -y --no-install-recommends zstd && \
    zstd -d /tmp/audiowmark.tar.zst -o /tmp/audiowmark.tar && \
    tar -xf /tmp/audiowmark.tar -C ${TEMP_DIR} --strip-components=1 && \
    # 3. Build and install
    cd ${TEMP_DIR} && \
    ./autogen.sh && \
    ./configure && \
    make -j$(nproc) && \
    make install && \
    # 4. Cleanup (Crucial for a small production image!)
    cd / && \
    rm -rf ${TEMP_DIR} /tmp/audiowmark.tar* && \
    # Remove all development packages and build tools
    apt-get purge -y build-essential automake autoconf libtool pkg-config zstd && \
    # Remove unused dependency files
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    
# -------------------------------------------------------------------
# Add the rest of your application code here, e.g.:
# COPY . . 
# CMD ["python", "app.py"] 
# -------------------------------------------------------------------
