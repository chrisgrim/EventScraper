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
RUN crontab /etc/cron.d/scraper-cron

# Create log directory
RUN mkdir -p /var/log && touch /var/log/scraper.log && chmod 666 /var/log/scraper.log

# Start cron and tail the logs
CMD service cron start && tail -f /var/log/scraper.log