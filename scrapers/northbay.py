from .base import BaseScraper
from playwright.async_api import async_playwright
import logging
from datetime import datetime, timedelta
import re

class NorthBayScraper(BaseScraper):
    def _group_events(self, events):
        """Group events with same title but different dates"""
        event_groups = {}
        
        for event in events:
            title = event['title'].lower()
            if title in event_groups:
                # For date ranges, we don't want to split and sort
                if 'to' in str(event['datetime']):
                    if 'to' not in str(event_groups[title]['datetime']):
                        event_groups[title]['datetime'] = event['datetime']
            else:
                event_groups[title] = {
                    'title': event['title'],
                    'datetime': event['datetime'],
                    'description': event.get('description', ''),
                    'image_url': event.get('image_url', ''),
                    'venue': event.get('venue', ''),
                    'venue_url': 'https://northbaystageandscreen.com/',
                    'url': event.get('url', '')
                }
        
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': event_data['datetime'],  # Keep the date range as is
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'venue': event_data['venue'],
                'venue_url': event_data['venue_url'],
                'url': event_data['url']
            })
        
        return grouped_events

    def _truncate_description(self, description, word_limit=60):
        """Truncate description to specified word limit and add ellipsis if needed"""
        if not description:
            return ""
        
        words = description.split()
        if len(words) <= word_limit:
            return description
        
        truncated = ' '.join(words[:word_limit])
        return f"{truncated}..."

    def _parse_date_range(self, date_text):
        """Parse date range text into a formatted string"""
        try:
            # Remove any asterisks and extra whitespace
            date_text = date_text.replace('*', '').strip()
            
            # Handle date range format "Month Day – Month Day"
            if '–' in date_text or '-' in date_text:
                # Standardize dash character
                date_text = date_text.replace('–', '-')
                
                # Split location and date if present
                if '*' in date_text:
                    location, date_range = date_text.split('*')
                else:
                    date_range = date_text
                
                start_str, end_str = date_range.split('-')
                start_str = start_str.strip()
                end_str = end_str.strip()
                
                # Add year to the dates
                year = '2025'  # Or get dynamically
                
                # If end date doesn't include month, use start month
                if not any(month in end_str for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                    start_month = start_str.split()[0]
                    end_str = f"{start_month} {end_str}"
                
                # Parse dates
                start_date = datetime.strptime(f"{start_str} {year}", "%B %d %Y")
                end_date = datetime.strptime(f"{end_str} {year}", "%B %d %Y")
                
                # Format as a date range string
                return f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            
            return date_text
            
        except Exception as e:
            logging.error(f"Error parsing date range '{date_text}': {e}")
            return date_text

    async def scrape(self):
        """Scrape North Bay Stage & Screen events"""
        browser = None
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto('https://northbaystageandscreen.com/onstage/')
                
                events = []
                current_event = {}
                
                sections = await page.query_selector_all('div.wp-block-image, p')
                
                for section in sections:
                    text = await section.inner_text()
                    tag_name = await section.evaluate('el => el.tagName.toLowerCase()')
                    
                    if tag_name == 'div':
                        if current_event and 'title' in current_event:
                            events.append(current_event)
                        
                        current_event = {}
                        
                        try:
                            img = await section.query_selector('img')
                            if img:
                                orig_file = await img.get_attribute('data-orig-file')
                                src = await img.get_attribute('src')
                                current_event['image_url'] = orig_file or src
                        except Exception as e:
                            logging.error(f"Error extracting image: {e}")
                    
                    elif tag_name == 'p':
                        link = await section.query_selector('a[rel*="noopener"]')
                        if link:
                            url = await link.get_attribute('href')
                            if current_event:
                                current_event['url'] = url
                        
                        if '***' in text or not text.strip():
                            continue
                            
                        if await section.query_selector('strong'):
                            title_text = await section.inner_text()
                            if ' – ' in title_text:
                                title, theater = title_text.split(' – ', 1)
                                current_event['title'] = title.strip()
                                current_event['venue'] = theater.strip()
                        
                        section_class = await section.get_attribute('class') or ''
                        if 'has-text-align-center' in section_class:
                            if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                                try:
                                    if '*' in text:
                                        location, date_range = text.split('*')
                                        current_event['venue'] = location.strip()
                                        current_event['datetime'] = self._parse_date_range(date_range.strip())
                                    else:
                                        current_event['datetime'] = self._parse_date_range(text.strip())
                                except Exception as e:
                                    logging.error(f"Error parsing date section: {e}")
                                    current_event['datetime'] = text.strip()
                        
                        elif not 'has-text-align-center' in section_class:
                            desc = await section.inner_text()
                            if desc and not desc.startswith('with ') and 'Directed by' not in desc:
                                current_event['description'] = self._truncate_description(desc.strip())
                
                if current_event and 'title' in current_event:
                    events.append(current_event)
                
                events = self._group_events(events)
                
                logging.info(f"Successfully scraped {len(events)} events from North Bay Stage & Screen")
                return events
                
            except Exception as e:
                logging.error(f"Failed to scrape North Bay Stage & Screen events: {e}")
                return []
                
            finally:
                if browser:
                    await browser.close()