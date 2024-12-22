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

    async def scrape(self):
        """Scrape North Bay Stage & Screen events"""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()
                await page.goto('https://northbaystageandscreen.com/onstage/')
                
                events = []
                current_event = {}
                
                # Get all sections that could be part of an event
                sections = await page.query_selector_all('div.wp-block-image, p')
                
                for i, section in enumerate(sections):
                    text = await section.inner_text()
                    tag_name = await section.evaluate('el => el.tagName.toLowerCase()')
                    
                    # If we find an image div, it's the start of a new event
                    if tag_name == 'div':
                        # Save previous event if it exists
                        if current_event and 'title' in current_event:
                            events.append(current_event)
                        
                        # Start new event
                        current_event = {}
                        
                        # Extract image
                        try:
                            img = await section.query_selector('img')
                            if img:
                                orig_file = await img.get_attribute('data-orig-file')
                                src = await img.get_attribute('src')
                                current_event['image_url'] = orig_file or src
                                logging.info(f"Found image URL: {current_event['image_url']}")
                        except Exception as e:
                            logging.error(f"Error extracting image: {e}")
                    
                    # Process text content
                    elif tag_name == 'p':
                        # Debug: Log the class attribute
                        class_attr = await section.get_attribute('class')
                        logging.info(f"Found paragraph with class: {class_attr}")
                        
                        # Try to get any link with noopener, regardless of container class
                        link = await section.query_selector('a[rel*="noopener"]')
                        if link:
                            url = await link.get_attribute('href')
                            logging.info(f"Found link with href: {url}")
                            if current_event:  # Make sure we have a current event to add the URL to
                                current_event['url'] = url
                                logging.info(f"Added URL to event: {current_event.get('title', 'Untitled')}")
                        
                        if '***' in text:  # Divider between shows
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
                            if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                                try:
                                    # Example: "Napa * January 31 – February 22"
                                    location, date_range = text.split('*')
                                    current_event['venue'] = location.strip()
                                    current_event['datetime'] = date_range.strip()
                                except Exception as e:
                                    logging.error(f"Error parsing date: {text} - {e}")
                                    current_event['datetime'] = text.strip()
                        
                        # Extract description
                        elif not 'has-text-align-center' in (await section.get_attribute('class') or ''):
                            desc = await section.inner_text()
                            if desc and not desc.startswith('with ') and 'Directed by' not in desc:
                                current_event['description'] = self._truncate_description(desc.strip())
                
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