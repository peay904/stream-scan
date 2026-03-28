FROM python:3.12-slim

# Timezone support
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY templates/ ./templates/
COPY images/ ./images/

# Create volume mount points
RUN mkdir -p /output /state

# Default environment
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV SCAN_DAY=friday
ENV SCAN_HOUR=6
ENV SERVICES=netflix,hulu,prime,max,peacock,paramount,apple,disney
ENV FORCE_RUN=false
ENV WEB_PORT=7777

EXPOSE 7777

CMD ["python", "-m", "src.main"]
