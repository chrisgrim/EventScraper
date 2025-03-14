FROM mcr.microsoft.com/playwright/python:v1.41.0

WORKDIR /app

# Install cron
RUN apt-get update && apt-get -y install cron

# Copy requirements first (better for caching)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Add crontab file and set permissions
COPY crontab /etc/cron.d/scraper-cron
RUN chmod 0644 /etc/cron.d/scraper-cron

# Create log directory
RUN mkdir -p /var/log && touch /var/log/scraper.log && chmod 666 /var/log/scraper.log

# Clean up to reduce image size
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Entry point set to python script directly (not using cron within container)
ENTRYPOINT ["python"]
CMD ["monitor.py"]