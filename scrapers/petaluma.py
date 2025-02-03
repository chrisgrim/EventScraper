from .base import BaseScraper
from playwright.async_api import async_playwright
import logging
from datetime import datetime
import re

class PetalumaScraper(BaseScraper):
    def _parse_date(self, date_text):
        """Parse date text into ISO format"""
        try:
            # Handle multiple dates
            if ' and ' in date_text:
                date_strings = date_text.split(' and ')
                parsed_dates = []
                for date_str in date_strings:
                    parsed = self._parse_single_date(date_str.strip())
                    if parsed:
                        parsed_dates.append(parsed)
                return ' and '.join(parsed_dates) if parsed_dates else None
            else:
                return self._parse_single_date(date_text)
                
        except Exception as e:
            logging.warning(f"Error parsing date '{date_text}': {e}")
            return None

    def _parse_single_date(self, date_text):
        """Parse a single date string into ISO format"""
        try:
            # Extract the base date part (before any time range)
            if ' - ' in date_text:
                date_text = date_text.split(' - ')[0]
            
            # Split into components
            parts = date_text.strip().split()
            if len(parts) < 3:  # Need at least: [Weekday, Month, Day]
                return None
            
            # Handle different date formats
            if parts[0] in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                parts = parts[1:]  # Remove weekday
            
            # Get components
            month = parts[0]
            day = parts[1].rstrip(',')  # Remove any trailing comma
            year = str(datetime.now().year)  # Simply use current year
            
            # Parse time
            time = "00:00:00"  # Default time
            time_str = parts[-1].lower()  # Last part should be time
            
            if 'am' in time_str or 'pm' in time_str:
                if ':' in time_str:
                    hour, minute = time_str.replace('am','').replace('pm','').split(':')
                    hour = int(hour)
                    minute = int(minute)
                    
                    if 'pm' in time_str.lower() and hour != 12:
                        hour += 12
                    elif 'am' in time_str.lower() and hour == 12:
                        hour = 0
                        
                    time = f"{hour:02d}:{minute:02d}:00"
                else:
                    hour = int(time_str.replace('am','').replace('pm',''))
                    if 'pm' in time_str.lower() and hour != 12:
                        hour += 12
                    elif 'am' in time_str.lower() and hour == 12:
                        hour = 0
                    time = f"{hour:02d}:00:00"
            
            # Construct and validate the date
            try:
                date_str = f"{month} {day} {year}"
                date_obj = datetime.strptime(date_str, '%B %d %Y')
                return f"{date_obj.strftime('%Y-%m-%d')} {time}"
            except ValueError:
                # Try abbreviated month format
                try:
                    date_obj = datetime.strptime(date_str, '%b %d %Y')
                    return f"{date_obj.strftime('%Y-%m-%d')} {time}"
                except ValueError as e:
                    logging.warning(f"Failed to parse date '{date_str}': {e}")
                    return None
            
        except Exception as e:
            logging.warning(f"Error parsing single date '{date_text}': {e}")
            return None

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
                    'url': event.get('url', ''),
                    'venue': 'Petaluma Downtown',
                    'venue_url': 'https://tockify.com/pdaevents'
                }
        
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(event_data['datetimes']),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'url': event_data['url'],
                'venue': event_data['venue'],
                'venue_url': event_data['venue_url'],
                'multiple_dates': len(event_data['datetimes']) > 1
            })
        
        return grouped_events

    async def scrape(self):
        """Scrape events from Petaluma Downtown's calendar"""
        browser = None
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                response = await page.goto('https://tockify.com/pdaevents', 
                                       wait_until='networkidle',
                                       timeout=90000)
                
                if not response.ok:
                    logging.error(f"Failed to load page: {response.status}")
                    return []
                    
                await page.wait_for_selector('body', timeout=60000)
                await page.wait_for_timeout(10000)
                
                events = await self._extract_events(page)
                events = self._group_events(events)
                valid_events = [e for e in events if self.validate_event(e)]
                
                logging.info(f"Successfully scraped {len(valid_events)} events from Petaluma")
                return valid_events
                
            except Exception as e:
                logging.error(f"Failed to scrape Petaluma events: {e}")
                return []
                
            finally:
                if browser:
                    await browser.close()
                
    async def _extract_events(self, page):
        """Extract events from the page"""
        try:
            events = await page.evaluate('''() => {
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
                    if (dateElement) {
                        event.datetime = dateElement.textContent.trim();
                    }
                    
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
            
            validated_events = []
            for event in events:
                try:
                    if isinstance(event['datetime'], str):
                        parsed_date = self._parse_date(event['datetime'])
                        if parsed_date:  # Only add events with valid dates
                            event['datetime'] = parsed_date
                            validated_events.append(event)
                        else:
                            logging.warning(f"Skipping event '{event['title']}' - Could not parse date: {event['datetime']}")
                except Exception as e:
                    logging.warning(f"Error processing event: {event['title']} - {str(e)}")
                    continue
            
            return validated_events
            
        except Exception as e:
            logging.error(f"Failed to extract events: {e}")
            return []
