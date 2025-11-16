# ---- Base image -------------------------------------------------
FROM python:3.11-slim

# ---- System dependencies (ffmpeg + libs) ------------------------
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Install audiowmark v0.2.0 ----------------------------------
# The release is a .tar.gz with a versioned folder inside
RUN set -eux; \
    wget -q https://github.com/swesterfeld/audiowmark/releases/download/v0.2.0/audiowmark-0.2.0-linux-x86_64.tar.gz -O /tmp/audiowmark.tar.gz && \
    tar -xzf /tmp/audiowmark.tar.gz -C /tmp && \
    find /tmp -name audiowmark -type f -executable -exec mv {} /usr/local/bin/audiowmark \; && \
    rm -rf /tmp/audiowmark.tar.gz /tmp/audiowmark*

# ---- Python deps ------------------------------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- App --------------------------------------------------------
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
