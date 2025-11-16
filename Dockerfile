# Use a lean Debian base image, as implied by the package names in your logs
FROM debian:bookworm-slim

# Define variables for versioning and temporary directory
ARG LATEST_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# 1. Install dependencies
# 'zstd' is added here to ensure the Zstandard archive can be decompressed by tar.
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
        libfftw3-single-dev \
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
# FIX APPLIED HERE: The URL and file extension are corrected from .tar.xz to .tar.zst.
RUN set -eux; \
    mkdir -p ${TEMP_DIR} && \
    # Download the source archive (.tar.zst)
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    # FIX: Use 'tar -I zstd' for reliable extraction of Zstandard archives
    tar -I zstd -xf /tmp/audiowmark.tar.zst -C "${TEMP_DIR}" --strip-components=1

# 3. Configure and Build
RUN set -eux; \
    cd "${TEMP_DIR}" && \
    ./autogen.sh && \
    # Configure using --enable-single-precision for libfftw3-single-dev
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
