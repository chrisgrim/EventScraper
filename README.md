# Event Scraper

An automated event scraping system built with Python and Playwright. This tool monitors various event websites and collects information about upcoming events.

## Features

- Web scraping using Playwright
- Docker containerization
- Automated scheduling with cron
- Event analysis with Claude AI
- Notification system

## Setup

1. Clone the repository:
```bash
git clone git@github.com:chrisgrim/EventScraper.git
```

2. Build and run with Docker:
```bash
docker build -t web-monitor .
docker run -d --name web-monitor --env-file .env web-monitor
```

## Configuration

Create a `.env` file with your API keys and settings:
```
ANTHROPIC_API_KEY=your_api_key
```

## License

MIT
