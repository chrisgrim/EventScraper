# Events Scraper

A Python-based web scraper that collects event information from various venues, processes the data using Claude AI, and sends a formatted email digest of upcoming events.

## Project Structure

```
events-scraper/
├── analyzers/             # Event analysis modules
│   ├── claude.py          # Claude AI integration for event processing
│   ├── base.py            # Base analyzer class
│   ├── date_parser.py     # Date parsing utilities
│   └── __init__.py
├── notifications/         # Notification services
│   ├── email.py           # Email notification service
│   ├── base.py            # Base notifier class
│   └── __init__.py
├── scrapers/              # Web scrapers for different venues
│   ├── petaluma.py        # Petaluma venue scraper (active)
│   ├── california.py      # California Theatre scraper (inactive)
│   ├── northbay.py        # North Bay scraper (inactive)
│   ├── base.py            # Base scraper class
│   └── __init__.py
├── .env                   # Environment variables (not tracked in git)
├── config.json            # Configuration file
├── crontab                # Crontab configuration for Docker
├── Dockerfile             # Docker configuration
├── monitor.py             # Main application entry point
├── requirements.txt       # Python dependencies
├── run                    # Bash script to run the Docker container
├── test_email.py          # Utility script to test email functionality
└── README.md              # This file
```

## How It Works

1. **Scraping**: The application scrapes event information from configured venues using Playwright.
2. **Analysis**: Collected event data is sent to Claude AI for analysis and formatting.
3. **Notification**: The formatted event information is sent as an email digest.

## Configuration

### Environment Variables (.env)

```
ANTHROPIC_API_KEY=your_anthropic_api_key
SMTP_SERVER=your_smtp_server
SMTP_PORT=your_smtp_port
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
EMAIL_RECIPIENT=your_email_recipient
DEBUG=0
TEST_MODE=0
```

### config.json

Basic configuration for scrapers and analyzers:

```json
{
  "petaluma": {},
  "analyzer": {}
}
```

## Running the Application

### Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python monitor.py
```

### With Docker

```bash
# Build the Docker image
docker build -t events-scraper .

# Run in normal mode
docker run -it --rm --env-file .env events-scraper monitor.py

# Run in test mode
docker run -it --rm --env-file .env -e TEST_MODE=1 events-scraper monitor.py
```

### Using the Run Script

```bash
# Make the script executable
chmod +x run

# Run the application
./run
```

### Testing Email Functionality

The repository includes a standalone script for testing email configuration:

```bash
# Test email functionality
python test_email.py
```

This sends a simple test email using the configured SMTP settings, which is useful for verifying email connectivity without running the full scraper.

## Deployment

The application is set up to run weekly on Sunday at 2 AM via a cron job:

```
0 2 * * 0 cd /opt/events-scraper && ./run
```

## Adding New Scrapers

1. Create a new scraper in the `scrapers/` directory, inheriting from `base.py`
2. Implement the `scrape()` method
3. Add the scraper to the `_setup_scrapers()` method in `monitor.py`

## Troubleshooting

- Check logs at `/var/log/events-scraper.log`
- For Docker issues, use `docker logs events-scraper`
- To run in debug mode, set `DEBUG=1` in your .env file
- For email issues, run `python test_email.py` to test SMTP configuration

## Documentation

- `SETUP.md` contains detailed deployment instructions
- `MAINTENANCE.md` provides guidance for routine maintenance and troubleshooting

## License

MIT
