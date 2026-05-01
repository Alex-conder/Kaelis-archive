# Kaelis Production Docker Image
# Usage:
#   docker build -t kaelis/kaelis:v0.4.0 .
#   docker run -p 5000:5000 --env-file .env kaelis/kaelis:v0.4.0

FROM python:3.13-slim

LABEL maintainer="Kaelis Team <team@kaelis.ai>"
LABEL version="0.4.0"
LABEL description="Kaelis AI Agent Operating System"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health', timeout=5)" || exit 1

# Run production server
CMD ["python", "prod_server.py"]
