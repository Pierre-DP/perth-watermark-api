FROM python:3.11-slim

# Install system deps + audiowmark
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install audiowmark
RUN wget -q https://github.com/swesterfeld/audiowmark/releases/download/v0.2.0/audiowmark-0.2.0-linux-x86_64.tar.gz \
    && tar -xzf audiowmark-0.2.0-linux-x86_64.tar.gz \
    && mv audiowmark-0.2.0-linux-x86_64/audiowmark /usr/local/bin/ \
    && rm -rf audiowmark-0.2.0-linux-x86_64*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
