from .base import BaseScraper
from playwright.async_api import async_playwright
import logging
from datetime import datetime

class PetalumaScraper(BaseScraper):
    def _group_events(self, events):
        """Group events with same title but different dates"""
        event_groups = {}
        
        for event in events:
            title = event['title'].lower()
            if title in event_groups:
                # Add this datetime to existing event
                event_groups[title]['datetimes'].append(event['datetime'])
                # Sort datetimes chronologically
                event_groups[title]['datetimes'].sort()
            else:
                # Create new event group
                event_groups[title] = {
                    'title': event['title'],  # Keep original case
                    'datetimes': [event['datetime']],
                    'description': event.get('description', ''),
                    'image_url': event.get('image_url', ''),
                    'url': event.get('url', '')  # Add URL to the group
                }
        
        # Convert groups back to events format, but with multiple dates
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(event_data['datetimes']),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'url': event_data['url'],  # Include URL in final event
                'multiple_dates': len(event_data['datetimes']) > 1
            })
            
            if len(event_data['datetimes']) > 1:
                logging.info(f"Grouped event '{event_data['title']}' occurs on: {', '.join(event_data['datetimes'])}")
        
        return grouped_events

    async def scrape(self):
        """Scrape events from Petaluma Downtown's calendar"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
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
                
                # Extract events
                events = await self._extract_events(page)
                
                # Group events with same title
                events = self._group_events(events)
                
                # Validate events
                valid_events = [e for e in events if self.validate_event(e)]
                logging.info(f"Found {len(valid_events)} valid unique events")
                return valid_events
                
            except Exception as e:
                logging.error(f"Failed to scrape Petaluma events: {e}")
                logging.error(f"Error details: {type(e).__name__}")
                return []
                
            finally:
                await browser.close()
                
    async def _extract_events(self, page):
        """Extract events from the page"""
        try:
            logging.info("Extracting events...")
            events = await page.evaluate('''() => {
                const events = [];
                const cards = document.querySelectorAll('.cardBoard__card');
                console.log("Found cards:", cards.length);
                
                cards.forEach(card => {
                    const event = {};
                    
                    // Extract title and URL
                    const titleElement = card.querySelector('.pincard__main__title a');
                    if (titleElement) {
                        event.title = titleElement.textContent.trim();
                        event.url = titleElement.href;
                        // Convert relative URL to absolute
                        if (event.url && event.url.startsWith('/')) {
                            event.url = 'https://tockify.com' + event.url;
                        }
                        console.log("Found URL:", event.url); // Debug log
                    }
                    
                    // Extract date/time
                    const dateElement = card.querySelector('.pincard__main__when');
                    event.datetime = dateElement ? dateElement.textContent.trim() : '';
                    
                    // Extract description
                    const descElement = card.querySelector('.pincard__main__preview');
                    event.description = descElement ? descElement.textContent.trim() : '';
                    
                    // Extract image URL - try multiple selectors
                    const imgElement = card.querySelector('.pincard__imageSection__image[src], .pincard__imageSection img[src]');
                    event.image_url = imgElement ? imgElement.src : '';
                    console.log("Found image URL:", event.image_url); // Debug log
                    
                    if (event.title) {
                        events.push(event);
                    }
                });
                
                return events;
            }''')
            
            logging.info(f"Extracted {len(events)} events")
            for event in events:
                if event.get('url'):
                    logging.info(f"Event '{event['title']}' has URL: {event['url']}")
                else:
                    logging.warning(f"No URL found for event: {event['title']}")
                
                # Debug image URLs too
                if event.get('image_url'):
                    logging.info(f"Event '{event['title']}' has image: {event['image_url']}")
                else:
                    logging.warning(f"No image found for event: {event['title']}")
                
            return events
            
        except Exception as e:
            logging.error(f"Failed to extract events: {e}")
            logging.error(f"Error details: {type(e).__name__}")
            return []
