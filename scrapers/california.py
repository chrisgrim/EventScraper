from .base import BaseScraper
from playwright.async_api import async_playwright
import logging
from datetime import datetime
import re

class CaliforniaTheatreScraper(BaseScraper):
    def _group_events(self, events):
        """Group events with same title but different dates"""
        event_groups = {}
        
        for event in events:
            # Create a key that includes more than just title to ensure proper grouping
            key = f"{event['title'].lower()}_{event.get('description', '')}"
            
            if key in event_groups:
                # Keep all event details the same, just add the new datetime
                event_groups[key]['datetimes'].append(event['datetime'])
                event_groups[key]['datetimes'].sort()  # Sort chronologically
            else:
                # Store all event details
                event_groups[key] = {
                    'title': event['title'],
                    'datetimes': [event['datetime']],
                    'description': event.get('description', ''),
                    'image_url': event.get('image_url', ''),
                    'url': event.get('url', ''),
                    'venue': event.get('venue', 'California Theatre'),
                    'venue_url': event.get('venue_url', 'https://www.caltheatre.com/')
                }
        
        # Convert groups back to list format
        grouped_events = []
        for event_data in event_groups.values():
            # Format all datetimes in ISO format
            datetime_strs = [dt.strftime('%Y-%m-%d %H:%M:%S') for dt in event_data['datetimes']]
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(datetime_strs),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'url': event_data['url'],
                'venue': event_data['venue'],
                'venue_url': event_data['venue_url']
            })
        
        return grouped_events

    async def scrape(self):
        """Scrape California Theatre events"""
        browser = None
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(timeout=30000)
                page = await browser.new_page()
                await page.goto('https://www.caltheatre.com/', 
                              wait_until='networkidle',
                              timeout=30000)
                
                try:
                    await page.wait_for_selector('[data-hook="event-list-item"]', 
                                              timeout=10000)
                except Exception as e:
                    logging.error(f"Timeout waiting for events: {e}")
                    html = await page.content()
                    with open('cal_theatre_error.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    return []
                
                events = []
                event_elements = await page.query_selector_all('[data-hook="event-list-item"]')
                
                for element in event_elements:
                    try:
                        # Initialize variables
                        img_url = None
                        ticket_url = None
                        
                        # Extract title
                        title = await element.query_selector('[data-hook="ev-list-item-title"]')
                        title_text = await title.inner_text() if title else None
                        
                        # First try to get the date from the compact format
                        date_compact = await element.query_selector('[data-hook="ev-date"]')
                        compact_text = await date_compact.inner_text() if date_compact else None
                        
                        # Then get the full date for the time
                        date_full = await element.query_selector('[data-hook="date"]')
                        full_text = await date_full.inner_text() if date_full else None
                        
                        datetime_obj = None
                        if compact_text and full_text:
                            try:
                                # Extract the year from the full date
                                year_match = re.search(r'\b\d{4}\b', full_text)
                                year = year_match.group(0) if year_match else '2025'
                                
                                # Parse the time from the full date
                                time_match = re.search(r'(\d{1,2}:\d{2} [AP]M)', full_text)
                                time_str = time_match.group(1) if time_match else '12:00 AM'
                                
                                # Combine the compact date with year and time
                                # Convert "Mon, Feb 10" format to datetime
                                date_parts = compact_text.split(', ')
                                if len(date_parts) == 2:
                                    month_day = date_parts[1]
                                    datetime_str = f"{month_day} {year} {time_str}"
                                    datetime_obj = datetime.strptime(datetime_str, '%b %d %Y %I:%M %p')
                            except Exception as e:
                                logging.error(f"Failed to parse date '{compact_text}' with '{full_text}': {e}")
                        
                        # Extract description
                        desc = await element.query_selector('[data-hook="ev-list-item-description"]')
                        desc_text = await desc.inner_text() if desc else None
                        
                        # Extract image URL
                        img = await element.query_selector('img')
                        if img:
                            img_url = await img.get_attribute('src')
                            if img_url:
                                img_url = re.sub(r'(\.(?:jpg|jpeg|png|webp)).*$', r'\1', img_url)
                        
                        # Extract ticket URL
                        ticket_link = await element.query_selector('[data-hook="ev-rsvp-button"]')
                        ticket_url = await ticket_link.get_attribute('href') if ticket_link else None
                        
                        if title_text and datetime_obj:
                            events.append({
                                'title': title_text,
                                'datetime': datetime_obj,
                                'description': desc_text,
                                'image_url': img_url,
                                'url': ticket_url,
                                'venue': 'California Theatre',
                                'venue_url': 'https://www.caltheatre.com/'
                            })
                            
                    except Exception as e:
                        logging.error(f"Error parsing event: {e}")
                        continue
                
                # Click "Load More" if it exists
                while True:
                    try:
                        load_more = await page.query_selector('[data-hook="load-more-button"]')
                        if not load_more:
                            break
                        await load_more.click()
                        await page.wait_for_timeout(1000)
                    except Exception:
                        break
                    
                logging.info(f"Successfully scraped {len(events)} events from California Theatre")
                logging.info(f"Found {len(events)} individual event listings")
                grouped_events = self._group_events(events)
                logging.info(f"Grouped into {len(grouped_events)} unique events")
                return grouped_events
                
            except Exception as e:
                logging.error(f"Failed to scrape California Theatre: {e}")
                return []
                
            finally:
                if browser:
                    await browser.close()