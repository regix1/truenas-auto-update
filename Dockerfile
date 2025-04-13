FROM python:3.12-slim

# Install cron for scheduling
RUN apt-get update && \
    apt-get install -y cron && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY docker-entrypoint.sh .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Create log file for cron
RUN touch /var/log/cron.log

# Set the entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]