FROM python:3.11-slim

# Install system deps (ffmpeg + zstd + libs)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    zstd \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install audiowmark v0.6.5 (single-line to avoid parse errors)
RUN curl -L -o /tmp/audiowmark.tar.zst "https://github.com/swesterfeld/audiowmark/releases/download/v0.6.5/audiowmark-0.6.5-linux-x86_64.tar.zst" && \
    tar -I zstd -xzf /tmp/audiowmark.tar.zst -C /tmp && \
    mv /tmp/audiowmark-0.6.5-linux-x86_64/bin/audiowmark /usr/local/bin/audiowmark && \
    chmod +x /usr/local/bin/audiowmark && \
    rm -rf /tmp/audiowmark.tar.zst /tmp/audiowmark* && \
    audiowmark --version

# Python app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
