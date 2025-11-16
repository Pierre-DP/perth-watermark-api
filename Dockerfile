# -------------------------------------------------------------------
# STAGE 1: Builder – compiles audiowmark from source
# -------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

ARG LATEST_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# Install build dependencies
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        automake \
        autoconf \
        libtool \
        curl \
        pkg-config \
        autoconf-archive \
        ca-certificates \
        zstd \
        # Core libraries for compiling audiowmark
        libfftw3-dev \
        libsndfile1-dev \
        libgcrypt-dev \
        libzita-resampler-dev \
        libmpg123-dev \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download + safely extract source
RUN set -eux; \
    mkdir -p "${TEMP_DIR}"; \
    curl -fSL \
      "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
      -o /tmp/audiowmark.tar.zst; \
    zstd -d /tmp/audiowmark.tar.zst -o /tmp/audiowmark.tar; \
    tar -xf /tmp/audiowmark.tar -C "${TEMP_DIR}" --strip-components=1; \
    rm /tmp/audiowmark.tar /tmp/audiowmark.tar.zst

# Build audiowmark
RUN set -eux; \
    cd "${TEMP_DIR}"; \
    ./autogen.sh; \
    ./configure --with-fftw-libs="-lfftw3f"; \
    make -j"$(nproc)"; \
    make install

# -------------------------------------------------------------------
# STAGE 2: Runtime Image – minimal environment containing only what 
# is required to run audiowmark
# -------------------------------------------------------------------
FROM debian:bookworm-slim

# Install runtime dependencies only
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        libfftw3-3 \
        libsndfile1 \
        libgcrypt20 \
        libmpg123-0 \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled binary + libraries from builder stage
COPY --from=builder /usr/local/bin/audiowmark /usr/local/bin/audiowmark
COPY --from=builder /usr/local/lib/ /usr/local/lib/

# Default entrypoint
ENTRYPOINT ["/usr/local/bin/audiowmark"]
