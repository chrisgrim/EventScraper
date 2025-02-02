from .base import BaseScraper
from playwright.sync_api import sync_playwright
import logging
from datetime import datetime
import re

class NorthBayScraper(BaseScraper):
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
                    'venue': event.get('venue', ''),
                    'url': event.get('url', '')
                }
        
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(event_data['datetimes']),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'venue': event_data['venue'],
                'url': event_data['url'],
                'multiple_dates': len(event_data['datetimes']) > 1
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

    def scrape(self):  # Remove async
        """Scrape North Bay Stage & Screen events"""
        with sync_playwright() as p:  # Change to with and sync_playwright
            browser = p.chromium.launch()  # Remove await
            try:
                page = browser.new_page()  # Remove await
                page.goto('https://northbaystageandscreen.com/onstage/')  # Remove await
                
                events = []
                current_event = {}
                
                sections = page.query_selector_all('div.wp-block-image, p')  # Remove await
                
                for section in sections:
                    text = section.inner_text()  # Remove await
                    tag_name = section.evaluate('el => el.tagName.toLowerCase()')  # Remove await
                    
                    if tag_name == 'div':
                        if current_event and 'title' in current_event:
                            events.append(current_event)
                        
                        current_event = {}
                        
                        try:
                            img = section.query_selector('img')  # Remove await
                            if img:
                                orig_file = img.get_attribute('data-orig-file')  # Remove await
                                src = img.get_attribute('src')  # Remove await
                                current_event['image_url'] = orig_file or src
                        except Exception as e:
                            logging.error(f"Error extracting image: {e}")
                    
                    elif tag_name == 'p':
                        link = section.query_selector('a[rel*="noopener"]')  # Remove await
                        if link:
                            url = link.get_attribute('href')  # Remove await
                            if current_event:
                                current_event['url'] = url
                        
                        if '***' in text or not text.strip():
                            continue
                            
                        if section.query_selector('strong'):  # Remove await
                            title_text = section.inner_text()  # Remove await
                            if ' – ' in title_text:
                                title, theater = title_text.split(' – ', 1)
                                current_event['title'] = title.strip()
                                current_event['venue'] = theater.strip()
                        
                        if 'has-text-align-center' in (section.get_attribute('class') or ''):  # Remove await
                            if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                                try:
                                    location, date_range = text.split('*')
                                    current_event['venue'] = location.strip()
                                    current_event['datetime'] = date_range.strip()
                                except Exception:
                                    current_event['datetime'] = text.strip()
                        
                        elif not 'has-text-align-center' in (section.get_attribute('class') or ''):  # Remove await
                            desc = section.inner_text()  # Remove await
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
                browser.close()  # Remove await