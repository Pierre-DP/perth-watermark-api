# Use a lean Debian base image
FROM debian:bookworm-slim

# Define variables for versioning and temporary directory
ARG LATEST_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# 1. Install dependencies
# FIX: Removed 'libfftw3-single-dev' as it's not available in Debian Bookworm.
# 'libfftw3-dev' includes the necessary single-precision components for the build.
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
        libgcrypt-dev \
        libzita-resampler-dev \
        libmpg123-dev \
        ffmpeg \
        zstd && \
    # Clean up apt cache to keep the image size small
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Prepare environment, download, and extract source
# (Previous fix for .tar.zst is maintained)
RUN set -eux; \
    mkdir -p ${TEMP_DIR} && \
    # Download the source archive (.tar.zst)
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    # Use 'tar -I zstd' for extraction
    tar -I zstd -xf /tmp/audiowmark.tar.zst -C "${TEMP_DIR}" --strip-components=1

# 3. Configure and Build
# The --enable-single-precision flag correctly tells the configure script to use
# the single-precision libraries provided within the main libfftw3-dev package.
RUN set -eux; \
    cd "${TEMP_DIR}" && \
    ./autogen.sh && \
    ./configure \
        --prefix=/usr/local \
        --enable-single-precision \
        --disable-dependency-tracking && \
    make -j$(nproc)

# 4. Install and Cleanup
RUN set -eux; \
    cd "${TEMP_DIR}" && \
    make install && \
    # Clean up temporary files and the build directory
    cd / && \
    rm -rf ${TEMP_DIR} /tmp/audiowmark.tar*

# Set the entrypoint to the compiled binary
ENTRYPOINT ["/usr/local/bin/audiowmark"]
