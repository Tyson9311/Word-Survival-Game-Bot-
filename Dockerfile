# Use official slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system deps for building wheels and optional extras
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (for better caching)
COPY requirements.txt /app/requirements.txt

# Install Python deps
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

# Create non-root user for container runtime
RUN useradd --create-home --shell /bin/bash botuser && chown -R botuser:botuser /app
USER botuser

# Use environment variable for Telegram token and owner id (set at runtime)
ENV BOT_TOKEN=""
ENV BOT_OWNER_ID="0"

# Command to run the bot
CMD ["python", "bot.py"]