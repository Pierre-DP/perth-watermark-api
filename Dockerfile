# Stage 1: Build Stage (Optional but good practice for speed/caching)
# Use a lightweight official Python image
FROM python:3.10-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app
WORKDIR $APP_HOME

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# --- Start of the section containing the fix ---

# Install system dependencies needed for the application and zstd
# This is a critical step to fix the 'tar' error you reported.
RUN apt-get update && apt-get install -y \
    curl \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Download & install audiowmark v0.6.5 pre-built binary
RUN set -eux; \
    curl -L -o /tmp/audiowmark.tar.zst \
    "https://github.com/swesterfeld/audiowmark/releases/download/v0.6.5/audiowmark-0.6.5-linux-x86_64.tar.zst" && \
    tar -I zstd -xzf /tmp/audiowmark.tar.zst -C /tmp && \
    find /tmp -name "audiowmark" -type f -executable -exec mv {} /usr/local/bin/audiowmark \; && \
    chmod +x /usr/local/bin/audiowmark && \
    rm -rf /tmp/audiowmark.tar.zst /tmp/audiowmark* && \
    audiowmark --version

# --- End of the section containing the fix ---

# Copy the application code
COPY . $APP_HOME

# Expose the application port (adjust if your app uses a different port)
EXPOSE 8000

# Run the application using gunicorn (common for Python APIs)
# You may need to adjust 'api:app' based on your entry point (e.g., 'main:app')
CMD ["gunicorn", "-b", "0.0.0.0:8000", "api:app"]
