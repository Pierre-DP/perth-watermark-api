# -------------------------------------------------------------------
# STAGE 1: Builder
# Purpose: Install all build tools, compile the application.
# -------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

# Set the version and temporary directory variables
ARG LATEST_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# 1. Install ALL necessary build dependencies
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
        # FIX: Use xz-utils for .tar.xz extraction
        xz-utils \
        # Core Library Headers
        libfftw3-dev \
        libsndfile1-dev \
        libgcrypt-dev \
        libzita-resampler-dev \
        libmpg123-dev \
        ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Prepare environment, download, and extract source
RUN set -eux; \
    mkdir -p "${TEMP_DIR}"; \
    # FIX: Corrected URL and filename (.tar.xz)
    curl -fSL \
      "https://github.com/swesterfeld/audiowmark/releases/download/v0.6.5/audiowmark-0.6.5.tar.xz" \
      -o /tmp/audiowmark-0.6.5.tar.xz; \
    # Use tar native XZ support (-J) for reliable extraction
    tar -Jxf /tmp/audiowmark-0.6.5.tar.xz -C "${TEMP_DIR}" --strip-components=1; \
    rm /tmp/audiowmark-0.6.5.tar.xz

# 3. Build and install
RUN set -eux; \
    cd "${TEMP_DIR}"; \
    ./autogen.sh; \
    # Explicitly configure to link against the single-precision FFTW library
    ./configure --with-fftw-libs="-lfftw3f"; \
    make -j"$(nproc)"; \
    make install

# -------------------------------------------------------------------
# STAGE 2: Runtime
# Purpose: Create a minimal, clean image for running the binary.
# -------------------------------------------------------------------
FROM debian:bookworm-slim

# 4. Install the necessary *runtime* libraries (non-dev versions)
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        # FIX: Replaced libfftw3-3 with the single-precision runtime library
        libfftw3f3 \
        libsndfile1 \
        libgcrypt20 \
        libmpg123-0 \
        ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 5. Copy the compiled executable and all resulting libraries (including libzita-resampler0)
COPY --from=builder /usr/local/bin/audiowmark /usr/local/bin/
COPY --from=builder /usr/local/lib/ /usr/local/lib/

# Set the entrypoint to the compiled application
ENTRYPOINT ["/usr/local/bin/audiowmark"]
