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
    """
    Main application class that orchestrates the event scraping, analysis, and notification workflow.
    
    This class is responsible for:
    1. Scraping events from various venues
    2. Sending events to Claude for analysis
    3. Sending formatted event information via email
    """
    def __init__(self):
        # Debug flags to control application behavior
        self.DEBUG = {
            'SCRAPE_ONLY': False,    # Only perform scraping, no analysis or notifications
            'SKIP_CLAUDE': False,    # Skip sending to Claude for analysis
            'SKIP_EMAIL': False,     # Skip sending email notifications
            'DEBUG_CLAUDE': True,    # Enable detailed logging for Claude API interactions
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
        """
        Initialize and configure all scrapers.
        
        Returns:
            dict: Dictionary of scraper name -> scraper instance
        """
        return {
            # 'california': CaliforniaTheatreScraper(self.config.get('california', {})),
            'petaluma': PetalumaScraper(self.config.get('petaluma', {})),
            # 'northbay': NorthBayScraper(self.config.get('northbay', {}))
        }
    
    def _setup_analyzer(self):
        """
        Initialize and configure the Claude analyzer.
        
        Returns:
            ClaudeAnalyzer: Configured analyzer instance
        """
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
        """
        Run all configured scrapers in parallel and collect their results.
        
        Returns:
            list: Combined list of all scraped events
        """
        all_events = []
        
        async def run_scraper(name, scraper):
            """Run a single scraper asynchronously"""
            try:
                events = await scraper.scrape()
                logger.info(f"Found {len(events)} events from {name}")
                return events
            except Exception as e:
                logger.error(f"Failed to scrape {name}: {e}")
                return []

        # Create tasks for all scrapers
        async def run_all_scrapers():
            """Run all scrapers in parallel"""
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
        """
        Convert event data to a format suitable for analysis.
        
        Args:
            events (list): List of event dictionaries
            
        Returns:
            list: Prepared events ready for Claude analysis
        """
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
        """
        Send events to Claude for analysis and formatting.
        
        Args:
            events (list): List of prepared event dictionaries
            
        Returns:
            str: Formatted HTML of events categorized by time
        """
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
        """
        Main method that executes the entire workflow:
        1. Scrape events (unless in test mode)
        2. Analyze events with Claude
        3. Send email notification
        """
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
        """
        Load configuration from config.json file.
        
        Returns:
            dict: Configuration dictionary
        """
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def _setup_notifiers(self):
        """
        Initialize and configure notification services.
        
        Returns:
            list: List of notifier instances
        """
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
        """
        Send a notification via all configured notifiers.
        
        Args:
            message (str): Message to send
        """
        try:
            if isinstance(message, list):
                message = "\n".join(str(item) for item in message)
            
            for notifier in self.notifiers:
                notifier.send(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    # Run the application
    monitor = WebMonitor()
    monitor.run()