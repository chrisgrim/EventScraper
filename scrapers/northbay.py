from .base import BaseScraper
from playwright.async_api import async_playwright
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
                    'venue': event.get('venue', '')
                }
        
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(event_data['datetimes']),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'venue': event_data['venue'],
                'multiple_dates': len(event_data['datetimes']) > 1
            })
        
        return grouped_events

    async def scrape(self):
        """Scrape North Bay Stage & Screen events"""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()
                await page.goto('https://northbaystageandscreen.com/onstage/')
                
                events = []
                
                # Each show is separated by asterisk dividers
                show_sections = await page.query_selector_all('p, div.wp-block-image')
                
                current_event = {}
                
                for section in show_sections:
                    text = await section.inner_text()
                    
                    if '***' in text:  # Divider between shows
                        if current_event and 'title' in current_event:
                            events.append(current_event)
                            current_event = {}
                        continue
                        
                    if not text.strip():
                        continue
                        
                    # Extract title and theater
                    if await section.query_selector('strong'):
                        title_text = await section.inner_text()
                        if ' – ' in title_text:  # Title and theater are separated by em dash
                            title, theater = title_text.split(' – ', 1)
                            current_event['title'] = title.strip()
                            current_event['venue'] = theater.strip()
                            
                    # Extract dates and location
                    if 'has-text-align-center' in (await section.get_attribute('class') or ''):
                        text = await section.inner_text()
                        if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                            current_event['datetime'] = text.strip()
                            
                    # Extract image URL
                    img = await section.query_selector('img')
                    if img:
                        current_event['image_url'] = await img.get_attribute('src')
                        
                    # Extract description (paragraphs without center alignment)
                    if not 'has-text-align-center' in (await section.get_attribute('class') or ''):
                        desc = await section.inner_text()
                        if desc and not desc.startswith('with ') and 'Directed by' not in desc:
                            current_event['description'] = desc.strip()
                
                # Add the last event if exists
                if current_event and 'title' in current_event:
                    events.append(current_event)
                
                # Group events with same title
                events = self._group_events(events)
                
                return events
                
            except Exception as e:
                logging.error(f"Failed to scrape North Bay Stage & Screen events: {e}")
                return []
                
            finally:
                await browser.close()