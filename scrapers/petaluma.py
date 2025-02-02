from .base import BaseScraper
from playwright.sync_api import sync_playwright
import logging
from datetime import datetime

class PetalumaScraper(BaseScraper):
    def _group_events(self, events):
        """Group events with same title but different dates"""
        event_groups = {}
        
        for event in events:
            title = event['title'].lower()
            if title in event_groups:
                event_groups[title]['datetimes'].append(event['datetime'])
                event_groups[title]['datetimes'].sort()
            else:
                event_groups[title] = {
                    'title': event['title'],
                    'datetimes': [event['datetime']],
                    'description': event.get('description', ''),
                    'image_url': event.get('image_url', ''),
                    'url': event.get('url', '')
                }
        
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(event_data['datetimes']),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'url': event_data['url'],
                'multiple_dates': len(event_data['datetimes']) > 1
            })
        
        return grouped_events

    def scrape(self):
        """Scrape events from Petaluma Downtown's calendar"""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            try:
                response = page.goto('https://tockify.com/pdaevents', 
                                   wait_until='networkidle',
                                   timeout=90000)
                
                if not response.ok:
                    logging.error(f"Failed to load page: {response.status}")
                    return []
                    
                page.wait_for_selector('body', timeout=60000)
                page.wait_for_timeout(10000)
                
                events = self._extract_events(page)
                events = self._group_events(events)
                valid_events = [e for e in events if self.validate_event(e)]
                
                logging.info(f"Successfully scraped {len(valid_events)} events from Petaluma")
                return valid_events
                
            except Exception as e:
                logging.error(f"Failed to scrape Petaluma events: {e}")
                return []
                
            finally:
                browser.close()
                
    def _extract_events(self, page):
        """Extract events from the page"""
        try:
            events = page.evaluate('''() => {
                const events = [];
                const cards = document.querySelectorAll('.cardBoard__card');
                
                cards.forEach(card => {
                    const event = {};
                    
                    const titleElement = card.querySelector('.pincard__main__title a');
                    if (titleElement) {
                        event.title = titleElement.textContent.trim();
                        event.url = titleElement.href;
                        if (event.url && event.url.startsWith('/')) {
                            event.url = 'https://tockify.com' + event.url;
                        }
                    }
                    
                    const dateElement = card.querySelector('.pincard__main__when');
                    event.datetime = dateElement ? dateElement.textContent.trim() : '';
                    
                    const descElement = card.querySelector('.pincard__main__preview');
                    event.description = descElement ? descElement.textContent.trim() : '';
                    
                    const imgElement = card.querySelector('.pincard__imageSection__image[src], .pincard__imageSection img[src]');
                    event.image_url = imgElement ? imgElement.src : '';
                    
                    if (event.title) {
                        events.push(event);
                    }
                });
                
                return events;
            }''')
            
            return events
            
        except Exception as e:
            logging.error(f"Failed to extract events: {e}")
            return []
