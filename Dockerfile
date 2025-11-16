# -------------------------------------------------------------------
# STAGE 1: Builder
# Purpose: Install all build tools, compile the application, and then
#          clean up the build directory.
# -------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

# Set the version for the source code to be downloaded
ARG LATEST_VERSION="v0.6.5"
ENV TEMP_DIR="/tmp/audiowmark_build"

# Install all necessary build dependencies and run the compilation
RUN set -eux; \
    # 1. Update and install ALL dependencies, including build tools
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
        zstd && \
    # 2. Prepare environment and download source
    mkdir -p ${TEMP_DIR} && \
    curl -L "https://github.com/swesterfeld/audiowmark/releases/download/${LATEST_VERSION}/audiowmark-${LATEST_VERSION}.tar.zst" \
    -o /tmp/audiowmark.tar.zst && \
    # 3. Decompress and extract
    zstd -d /tmp/audiowmark.tar.zst -o /tmp/audiowmark.tar && \
    tar -xf /tmp/audiowmark.tar -C ${TEMP_DIR} --strip-components=1 && \
    # 4. Build and install to /usr/local
    cd ${TEMP_DIR} && \
    ./autogen.sh && \
    ./configure && \
    make -j$(nproc) && \
    make install && \
    # 5. Clean up temporary files, build directory, and apt lists
    cd / && \
    rm -rf ${TEMP_DIR} /tmp/audiowmark.tar* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# -------------------------------------------------------------------
# STAGE 2: Production Image
# Purpose: Start from a minimal base and only copy the compiled binary
#          and its necessary *runtime* libraries.
# -------------------------------------------------------------------
FROM debian:bookworm-slim

# Copy the compiled executable (and its dependencies) from the builder stage
# /usr/local/bin/audiowmark is the compiled binary
# /usr/local/lib/* contains any shared libraries audiowmark built/installed
COPY --from=builder /usr/local/bin/audiowmark /usr/local/bin/
COPY --from=builder /usr/local/lib/ /usr/local/lib/

# The final image should already have the runtime dependencies like libfftw3,
# libsndfile1, libmpg123, and ffmpeg dependencies installed by default on
# debian:bookworm-slim, or they will be dynamically linked and available.

# If you need to ensure ALL runtime dependencies are present, you might
# add a final apt-get install here, but usually, a base image like
# bookworm-slim is sufficient for standard C/C++ dependencies.
# Example:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#   libfftw3-3 libsndfile1 libgcrypt20 libzita-resampler0 libmpg123-0 ffmpeg && \
#   rm -rf /var/lib/apt/lists/*

# Set the entrypoint to the compiled application
ENTRYPOINT ["/usr/local/bin/audiowmark"]

# Default command if none is provided
# CMD ["--help"]
