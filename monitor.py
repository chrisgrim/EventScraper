import os
import json
import logging
from scrapers.petaluma import PetalumaScraper
from analyzers.claude import ClaudeAnalyzer
from notifications.email import EmailNotifier

class WebMonitor:
    def __init__(self):
        self.config = self.load_config()
        self.scrapers = self._setup_scrapers()
        self.analyzer = self._setup_analyzer()
        self.notifiers = self._setup_notifiers()
        
    def _setup_scrapers(self):
        """Initialize all scrapers"""
        return {
            'petaluma': PetalumaScraper(self.config.get('petaluma', {})),
            # Add more scrapers here
        }
    
    def _setup_analyzer(self):
        """Initialize the analyzer"""
        return ClaudeAnalyzer(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            config=self.config.get('analyzer', {})
        )
    
    async def run(self):
        """Main execution flow"""
        try:
            all_events = []
            
            # Run all scrapers
            for name, scraper in self.scrapers.items():
                logging.info(f"Scraping events from {name}...")
                events = await scraper.scrape()
                if events:
                    all_events.extend(events)
            
            if not all_events:
                logging.error("No events found from any source")
                return

            # Analyze events
            recommendations = self.analyzer.analyze(all_events)
            if not recommendations:
                logging.error("No recommendations generated")
                return

            # Send notifications
            self.send_notification(recommendations)
            
        except Exception as e:
            logging.error(f"Run failed: {e}")
            logging.error(f"Error type: {type(e).__name__}")
            logging.error(f"Error details: {str(e)}")

    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return {}

    def _setup_notifiers(self):
        """Initialize notification handlers"""
        notifiers = []
        if os.getenv('SMTP_SERVER'):
            notifiers.append(EmailNotifier(
                os.getenv('SMTP_SERVER'),
                os.getenv('SMTP_PORT'),
                os.getenv('SMTP_USERNAME'),
                os.getenv('SMTP_PASSWORD'),
                os.getenv('EMAIL_RECIPIENT')
            ))
        return notifiers

    def send_notification(self, message):
        """Send notification to all configured notifiers"""
        try:
            if isinstance(message, list):
                message = "\n".join(str(item) for item in message)
            
            for notifier in self.notifiers:
                try:
                    notifier.send(message)
                except Exception as e:
                    logging.error(f"Notification failed: {e}")
        except Exception as e:
            logging.error(f"Notification failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = WebMonitor()
    import asyncio
    asyncio.run(monitor.run())