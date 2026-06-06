FROM python:3.11-slim

LABEL maintainer="ZendanBOT"
LABEL description="ZendanBOT - Professional VPN Sales Telegram Bot"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for database and backups
RUN mkdir -p /app/backups

# Run the bot
CMD ["python", "main.py"]
