import os
import json
import anthropic
from playwright.sync_api import sync_playwright
from notifications.email import EmailNotifier
import logging

class WebMonitor:
    def __init__(self):
        self.config = self.load_config()
        self.client = anthropic.Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
        self.notifiers = self._setup_notifiers()
        
    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return None

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

    def scrape_events(self):
        """Scrape events from configured websites"""
        events = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                url = "https://petalumadowntown.com/calendar"
                logging.info(f"Scraping events from {url}")
                
                # Navigate and wait for Angular to load
                page.goto(url, wait_until='networkidle', timeout=60000)
                
                # Wait for Angular content
                logging.info("Waiting for Angular content to load...")
                page.wait_for_selector('.viewerArea__main.ng-scope', timeout=30000)
                
                # Get events from the viewer area
                event_elements = page.query_selector_all('.viewerArea__main.ng-scope .event-item')
                logging.info(f"Found {len(event_elements)} event elements")
                
                for element in event_elements:
                    try:
                        # Extract title and date
                        title_elem = element.query_selector('.event-title, .event-name')
                        date_elem = element.query_selector('.event-date, .event-time')
                        
                        if title_elem and date_elem:
                            title = title_elem.inner_text().strip()
                            date = date_elem.inner_text().strip()
                            
                            events.append({
                                'title': title,
                                'date': date,
                                'source': 'Petaluma Downtown'
                            })
                            logging.info(f"Added event: {title} on {date}")
                            
                    except Exception as e:
                        logging.error(f"Failed to parse event element: {e}")
                
                if not events:
                    logging.error("No events found in viewer area")
                    # Take a screenshot for debugging
                    page.screenshot(path='/var/log/calendar.png')
                    # Log the viewer area content
                    viewer_area = page.query_selector('.viewerArea__main.ng-scope')
                    if viewer_area:
                        logging.info(f"Viewer area content: {viewer_area.inner_html()[:1000]}...")
                
            except Exception as e:
                logging.error(f"Failed to scrape events: {e}")
                logging.error(f"Page URL: {page.url}")
                try:
                    page.screenshot(path='/var/log/error.png')
                except:
                    pass
                
            browser.close()
        return events

    def analyze_events(self, events):
        """Use Claude to analyze events based on preferences"""
        prompt = f"""Given these events: {events}
        And my preferences: {self.config['preferences']}
        What events would you recommend and why?
        Please format your response in a clear, readable way."""
        
        try:
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content
        except Exception as e:
            logging.error(f"Claude analysis failed: {e}")
            return None

    def send_notification(self, message):
        """Send notification to all configured notifiers"""
        for notifier in self.notifiers:
            notifier.send(message)

    def run(self):
        """Main execution flow"""
        try:
            logging.info("Starting web monitor...")
            # 1. Scrape events
            events = self.scrape_events()
            if not events:
                logging.error("No events found")
                return

            # 2. Analyze with Claude
            logging.info(f"Analyzing {len(events)} events with Claude...")
            recommendations = self.analyze_events(events)
            if not recommendations:
                logging.error("No recommendations generated")
                return

            # 3. Send notifications
            logging.info("Sending notifications...")
            self.send_notification(recommendations)
            logging.info("Process completed successfully")
            
        except Exception as e:
            logging.error(f"Run failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = WebMonitor()
    monitor.run()