FROM python:3.11-slim

# Install system deps (ffmpeg + libs)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install audiowmark v0.2.0 (use curl + explicit extract)
RUN set -eux; \
    curl -L -o /tmp/audiowmark.tar.gz \
    "https://github.com/swesterfeld/audiowmark/releases/download/v0.2.0/audiowmark-0.2.0-linux-x86_64.tar.gz" && \
    tar -xzf /tmp/audiowmark.tar.gz -C /tmp && \
    # Find executable in any nested folder
    find /tmp -name "audiowmark" -type f -executable -exec mv {} /usr/local/bin/audiowmark \; && \
    chmod +x /usr/local/bin/audiowmark && \
    rm -rf /tmp/audiowmark.tar.gz /tmp/audiowmark*

# Verify install
RUN audiowmark --version

# Python deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
