import os
import json
import logging
from scrapers.petaluma import PetalumaScraper
from analyzers.claude import ClaudeAnalyzer
from notifications.email import EmailNotifier
from scrapers.california import CaliforniaTheatreScraper
from scrapers.northbay import NorthBayScraper
from datetime import datetime

class WebMonitor:
    def __init__(self):
        # Add debug flags
        self.DEBUG = {
            'SCRAPE_ONLY': False,  # Only run scraping
            'SKIP_CLAUDE': False,   # Skip Claude analysis
            'SKIP_EMAIL': False     # Skip email sending
        }
        self.config = self.load_config()
        self.scrapers = self._setup_scrapers()
        self.analyzer = self._setup_analyzer()
        self.notifiers = self._setup_notifiers()
        
    def _setup_scrapers(self):
        """Initialize all scrapers"""
        return {
            'petaluma': PetalumaScraper(self.config.get('petaluma', {})),
            'california': CaliforniaTheatreScraper(self.config.get('california', {})),
            'northbay': NorthBayScraper(self.config.get('northbay', {}))
        }
    
    def _setup_analyzer(self):
        """Initialize the analyzer"""
        return ClaudeAnalyzer(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            config=self.config.get('analyzer', {})
        )
    
    async def _scrape_all_events(self):
        """Scrape events from all configured sources"""
        all_events = []
        
        for name, scraper in self.scrapers.items():
            try:
                logging.info(f"Scraping events from {name}...")
                events = await scraper.scrape()
                logging.info(f"Found {len(events)} events from {name}")
                
                # Add debug logging for each event's image URL
                for event in events:
                    logging.info(f"Event from {name}: {event['title']}")
                    logging.info(f"Image URL: {event.get('image_url', 'No image URL found')}")
                    logging.info(f"Event URL: {event.get('url', event.get('ticket_url', 'No URL found'))}")
                
                all_events.extend(events)
            except Exception as e:
                logging.error(f"Failed to scrape {name}: {e}")
        
        if all_events:
            logging.info(f"Analyzing {len(all_events)} events with Claude...")
            logging.info("Events to analyze:")
            for i, event in enumerate(all_events, 1):
                logging.info(f"  {i}. {event['title']} ({event['datetime']})")
        else:
            logging.warning("No events found")
        
        return all_events
    
    def _prepare_events_for_analysis(self, events):
        """Convert datetime objects to strings for JSON serialization"""
        prepared_events = []
        for event in events:
            prepared_event = event.copy()
            if isinstance(prepared_event.get('datetime'), datetime):
                prepared_event['datetime'] = prepared_event['datetime'].strftime('%Y-%m-%d %H:%M:%S')
            prepared_events.append(prepared_event)
        return prepared_events
    
    async def run(self):
        """Main execution flow"""
        try:
            logging.info("\n=== STARTING WEB MONITOR ===")
            
            # 1. Scrape events
            logging.info("\n--- SCRAPING EVENTS ---")
            events = await self._scrape_all_events()
            
            if self.DEBUG['SCRAPE_ONLY']:
                logging.info("\n=== DEBUG: STOPPING AFTER SCRAPE ===")
                return events
            
            # 2. Analyze with Claude
            if not self.DEBUG['SKIP_CLAUDE']:
                logging.info("\n--- ANALYZING WITH CLAUDE ---")
                if events:
                    prepared_events = self._prepare_events_for_analysis(events)
                    recommendations = await self._analyze_events(prepared_events)
                else:
                    logging.warning("No events to analyze")
                    return
            else:
                logging.info("\n=== DEBUG: SKIPPING CLAUDE ANALYSIS ===")
                return
            
            # 3. Send notifications
            if not self.DEBUG['SKIP_EMAIL'] and recommendations:
                logging.info("\n--- SENDING EMAIL ---")
                self.send_notification(recommendations)
                logging.info("Process completed successfully")
            else:
                logging.info("\n=== DEBUG: SKIPPING EMAIL ===")
            
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

    async def _analyze_events(self, events):
        """Analyze events using configured analyzer"""
        try:
            if self.analyzer:
                recommendations = await self.analyzer.analyze(events)
                # Add debug logging
                logging.info(f"\nClaude returned {len(recommendations) if recommendations else 0} recommendations")
                logging.info("\nRecommendations received:")
                if isinstance(recommendations, list):
                    for rec in recommendations:
                        logging.info(f"\n{rec}")
                else:
                    logging.info(f"\nRaw response: {recommendations}")
                return recommendations
            else:
                logging.warning("No analyzer configured")
                return None
        except Exception as e:
            logging.error(f"Analysis failed: {e}")
            logging.error(f"Error type: {type(e).__name__}")
            logging.error(f"Error details: {str(e)}")
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = WebMonitor()
    import asyncio
    asyncio.run(monitor.run())