import os
import json
import logging
from scrapers.petaluma import PetalumaScraper
from analyzers.claude import ClaudeAnalyzer
from notifications.email import EmailNotifier
from scrapers.california import CaliforniaTheatreScraper
from scrapers.northbay import NorthBayScraper
from datetime import datetime
import asyncio  # Add this import at the top

# Set up logging configuration at module level
logger = logging.getLogger(__name__)

class WebMonitor:
    def __init__(self):
        self.DEBUG = {
            'SCRAPE_ONLY': False,
            'SKIP_CLAUDE': False,
            'SKIP_EMAIL': False,
            'DEBUG_CLAUDE': True,
            'TEST_MODE': os.getenv('TEST_MODE', '0').lower() in ('1', 'true')  # Use env var with default False
        }
        self.config = self.load_config()
        
        # Only set up scrapers if NOT in test mode
        if not self.DEBUG['TEST_MODE']:
            self.scrapers = self._setup_scrapers()
        else:
            self.scrapers = {}  # Empty dict for test mode
            logger.info("Test mode enabled - scrapers disabled")
        
        self.analyzer = self._setup_analyzer()
        self.notifiers = self._setup_notifiers()
        
    def _setup_scrapers(self):
        return {
            # 'california': CaliforniaTheatreScraper(self.config.get('california', {})),
            'petaluma': PetalumaScraper(self.config.get('petaluma', {})),
            # 'northbay': NorthBayScraper(self.config.get('northbay', {}))
        }
    
    def _setup_analyzer(self):
        analyzer = ClaudeAnalyzer(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            config=self.config.get('analyzer', {})
        )
        # Set debug level for all relevant loggers if DEBUG_CLAUDE is True
        if self.DEBUG['DEBUG_CLAUDE']:
            logging.getLogger('analyzers.claude').setLevel(logging.DEBUG)
            logging.getLogger('httpx').setLevel(logging.DEBUG)  # For HTTP requests
            logging.getLogger(__name__).setLevel(logging.DEBUG)
        return analyzer
    
    def _scrape_all_events(self):
        all_events = []
        
        async def run_scraper(name, scraper):
            try:
                events = await scraper.scrape()
                logger.info(f"Found {len(events)} events from {name}")
                return events
            except Exception as e:
                logger.error(f"Failed to scrape {name}: {e}")
                return []

        # Create tasks for all scrapers
        async def run_all_scrapers():
            tasks = [
                run_scraper(name, scraper) 
                for name, scraper in self.scrapers.items()
            ]
            results = await asyncio.gather(*tasks)
            for events in results:
                all_events.extend(events)
            return all_events

        # Run the async code in the sync context
        return asyncio.run(run_all_scrapers())
    
    def _prepare_events_for_analysis(self, events):
        prepared_events = []
        for event in events:
            prepared_event = event.copy()
            if isinstance(prepared_event.get('datetime'), datetime):
                prepared_event['datetime'] = prepared_event['datetime'].strftime('%Y-%m-%d %H:%M:%S')
            prepared_events.append(prepared_event)
        if self.DEBUG['DEBUG_CLAUDE']:
            logger.debug(f"Prepared events for analysis: {json.dumps(prepared_events, indent=2)}")
        return prepared_events
    
    def _analyze_events(self, events):
        try:
            if self.analyzer:
                if self.DEBUG['DEBUG_CLAUDE']:
                    logger.debug("Starting Claude analysis...")
                recommendations = self.analyzer.analyze(events)
                if self.DEBUG['DEBUG_CLAUDE']:
                    logger.debug("Claude analysis complete")
                return recommendations
            return None
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None

    def run(self):
        try:
            if self.DEBUG['TEST_MODE']:
                logger.info("Running in test mode - using dummy data")
                if self.analyzer:
                    logger.info("Starting test analysis...")
                    recommendations = self.analyzer.test_analyze()
                    if recommendations:
                        logger.info("Test analysis successful")
                        if not self.DEBUG['SKIP_EMAIL']:
                            self.send_notification(recommendations)
                    return
            
            # Only run this if NOT in test mode
            events = self._scrape_all_events()
            if self.DEBUG['SCRAPE_ONLY']:
                return events
            
            if not self.DEBUG['SKIP_CLAUDE'] and events:
                prepared_events = self._prepare_events_for_analysis(events)
                recommendations = self._analyze_events(prepared_events)
            else:
                return
            
            if not self.DEBUG['SKIP_EMAIL'] and recommendations:
                self.send_notification(recommendations)
                logger.info("Process completed successfully")
            
        except Exception as e:
            logger.error(f"Run failed: {e}")

    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def _setup_notifiers(self):
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
        try:
            if isinstance(message, list):
                message = "\n".join(str(item) for item in message)
            
            for notifier in self.notifiers:
                notifier.send(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    monitor = WebMonitor()
    monitor.run()