import os
import json
import anthropic
from playwright.async_api import async_playwright
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

    async def scrape_petaluma_downtown(self):
        """Scrape events from Petaluma Downtown's calendar"""
        async with async_playwright() as p:
            # Add browser configuration
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # Add viewport and user agent
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                # Enable request/response logging
                page.on('request', lambda req: logging.info(f"Request: {req.url}"))
                page.on('response', lambda res: logging.info(f"Response: {res.url} {res.status}"))
                
                logging.info("Navigating to Tockify calendar directly...")
                response = await page.goto('https://tockify.com/pdaevents', 
                                         wait_until='networkidle',
                                         timeout=90000)
                
                if not response.ok:
                    logging.error(f"Failed to load page: {response.status}")
                    return []
                    
                logging.info("Waiting for initial page load...")
                await page.wait_for_selector('body', timeout=60000)
                
                # Add longer wait for dynamic content
                logging.info("Waiting for dynamic content...")
                await page.wait_for_timeout(10000)
                
                # Check what elements are available
                logging.info("Checking page elements...")
                elements = await page.evaluate('''() => {
                    return {
                        cards: document.querySelectorAll('.cardBoard__card').length,
                        body: document.body.innerHTML.length,
                        classes: Array.from(document.body.classList),
                        html: document.documentElement.outerHTML.substring(0, 200) // First 200 chars
                    }
                }''')
                logging.info(f"Page elements: {elements}")
                
                # Save the page content for debugging
                html = await page.content()
                with open('debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                
                logging.info("Extracting events...")
                events = await page.evaluate('''() => {
                    const events = [];
                    const cards = document.querySelectorAll('.cardBoard__card');
                    console.log("Found cards:", cards.length);
                    
                    cards.forEach(card => {
                        const event = {};
                        
                        // Extract title
                        const titleElement = card.querySelector('.pincard__main__title a');
                        event.title = titleElement ? titleElement.textContent.trim() : '';
                        
                        // Extract date/time
                        const dateElement = card.querySelector('.pincard__main__when');
                        event.datetime = dateElement ? dateElement.textContent.trim() : '';
                        
                        // Extract description
                        const descElement = card.querySelector('.pincard__main__preview');
                        event.description = descElement ? descElement.textContent.trim() : '';
                        
                        // Extract image URL
                        const imgElement = card.querySelector('.pincard__imageSection__image');
                        event.image_url = imgElement ? imgElement.src : '';
                        
                        if (event.title) {
                            events.push(event);
                        }
                    });
                    
                    return events;
                }''')
                
                if not events:
                    logging.warning("No events found in the calendar")
                    return []
                    
                logging.info(f"Successfully scraped {len(events)} events")
                return events
                
            except Exception as e:
                logging.error(f"Failed to scrape events: {e}")
                logging.error(f"Error details: {type(e).__name__}")
                # Save page content on error
                try:
                    html = await page.content()
                    with open('error_page.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                except:
                    pass
                return []
                
            finally:
                await browser.close()

    def analyze_events(self, events):
        if not events:
            logging.error("No events to analyze")
            return None
        
        # Log the original events
        logging.info(f"Total events to analyze: {len(events)}")
        for i, event in enumerate(events):
            logging.info(f"Event {i+1}: {event.get('title', 'No title')} - {event.get('datetime', 'No date')}")
        
        prompt = """Here are my preferences for events:
        
        Strong Interests:
        - Immersive theater
        - Murder mysteries
        - Unique experiences for adults
        
        Moderate Interests:
        - Unique drinking experiences
        - Wine tasting
        - Puzzle hunts
        
        Dislikes:
        - Sports (football, baseball, etc.)
        - Shopping/consumer events
        
        IMPORTANT: 
        1. Analyze ALL events provided, even if they don't match preferences
        2. Give low scores (1-3) to events that don't match preferences
        3. Do not skip any events
        4. Return exactly {total_events} events in your response
        
        Given these ACTUAL events from the calendar:
        {events_json}
        
        Rank ALL these existing events from most to least appealing based on my preferences.
        Format your response in HTML using this EXACT structure, with NO introduction or extra text:
        
        <div class="event">
            <div class="score">Score: [X/10]</div>
            <div class="title">[Event Title]</div>
            <div class="datetime">[Date/Time]</div>
            <div class="image"><img src="[image_url]" alt="[Event Title]"></div>
            <div class="explanation">Why this score: [Brief explanation]</div>
        </div>
        
        Rules:
        1. Start your response with the first <div class="event"> directly
        2. Do not include any introduction or explanation
        3. Do not include any line breaks or extra formatting
        4. Only use the exact HTML structure shown
        5. Include ALL events, even with low scores
        6. Return exactly {total_events} events
        7. Do not skip any events, even if they don't match preferences
        """
        
        try:
            formatted_prompt = prompt.format(
                total_events=len(events),
                events_json=json.dumps(events, indent=2)
            )
            
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2500,
                messages=[{
                    "role": "user", 
                    "content": formatted_prompt
                }]
            )
            
            # Get the content
            content = message.content
            
            # Handle list response
            if isinstance(content, list):
                content = ' '.join(str(item) for item in content)
            
            # Handle string response
            if isinstance(content, str):
                if "TextBlock(text='" in content:
                    content = content.split("TextBlock(text='", 1)[1].rsplit("'", 1)[0]
                
                if "<div class=\"event\">" in content:
                    content = content[content.index("<div class=\"event\">"):]
                    
                content = content.replace('\\n', ' ')
                content = content.replace('\n', ' ')
                content = ' '.join(content.split())
                
                # Count events in response
                event_count = content.count('<div class="event">')
                logging.info(f"Events in Claude's response: {event_count} out of {len(events)}")
            
            return content
            
        except Exception as e:
            logging.error(f"Claude analysis failed: {e}")
            logging.error(f"Error details: {type(e).__name__}")
            logging.error(f"Error value: {str(e)}")
            return None

    def send_notification(self, message):
        """Send notification to all configured notifiers"""
        try:
            # Convert message to string if it's a list
            if isinstance(message, list):
                message = "\n".join(str(item) for item in message)
            
            for notifier in self.notifiers:
                try:
                    notifier.send(message)
                except Exception as e:
                    logging.error(f"Email notification failed: {e}")
        except Exception as e:
            logging.error(f"Notification failed: {e}")

    async def run(self):
        """Main execution flow"""
        try:
            logging.info("Starting web monitor...")
            # 1. Scrape events
            events = await self.scrape_petaluma_downtown()
            if not events:
                logging.error("No events found")
                return

            # 2. Analyze with Claude
            logging.info(f"Analyzing {len(events)} events with Claude...")
            recommendations = self.analyze_events(events)
            if not recommendations:
                logging.error("No recommendations generated")
                return

            # Print recommendations to console
            print("\n=== Event Recommendations ===\n")
            print(recommendations)
            print("\n===========================\n")

            # 3. Send notifications
            logging.info("Sending notifications...")
            self.send_notification(recommendations)
            logging.info("Process completed successfully")
            
        except Exception as e:
            logging.error(f"Run failed: {e}")
            logging.error(f"Error type: {type(e).__name__}")
            logging.error(f"Error details: {str(e)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = WebMonitor()
    import asyncio
    asyncio.run(monitor.run())