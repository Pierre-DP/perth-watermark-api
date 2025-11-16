# -------------------------------------------------------------------
# STAGE 1: Builder
# Purpose: Install all build tools, compile the application.
# -------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

# Set the version and temporary directory variables
ARG LATEST_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# 1. Install ALL necessary build dependencies, including autotools macros
RUN set -eux; \
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
        zstd \
        autoconf-archive && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Prepare environment, download, and extract source
RUN set -eux; \
    mkdir -p ${TEMP_DIR} && \
    # Download the source archive (.tar.zst)
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    # FIX: Use tar with the -I zstd flag for reliable extraction
    tar -xf /tmp/audiowmark.tar.zst -C ${TEMP_DIR} --strip-components=1 -I zstd && \
    rm /tmp/audiowmark.tar.zst

# 3. Build and install
RUN set -eux; \
    cd ${TEMP_DIR} && \
    ./autogen.sh && \
    ./configure && \
    make -j$(nproc) && \
    make install

# -------------------------------------------------------------------
# STAGE 2: Production Image
# Purpose: Create a minimal, clean image for running the binary.
# -------------------------------------------------------------------
FROM debian:bookworm-slim

# Copy the compiled executable and any resulting libraries from the builder stage
COPY --from=builder /usr/local/bin/audiowmark /usr/local/bin/
COPY --from=builder /usr/local/lib/ /usr/local/lib/

# Install the necessary *runtime* libraries
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        libfftw3-3 \
        libsndfile1 \
        libgcrypt20 \
        libzita-resampler0 \
        libmpg123-0 \
        ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the entrypoint to the compiled application
ENTRYPOINT ["/usr/local/bin/audiowmark"]
