from .base import BaseScraper
from playwright.async_api import async_playwright
import logging
from datetime import datetime

class CaliforniaTheatreScraper(BaseScraper):
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
                    'image_url': event.get('image_url', '')
                }
        
        # Convert groups back to events format, but with multiple dates
        grouped_events = []
        for event_data in event_groups.values():
            grouped_events.append({
                'title': event_data['title'],
                'datetime': ' and '.join(event_data['datetimes']),
                'description': event_data['description'],
                'image_url': event_data['image_url'],
                'multiple_dates': len(event_data['datetimes']) > 1
            })
            
            if len(event_data['datetimes']) > 1:
                logging.info(f"Grouped event '{event_data['title']}' occurs on: {', '.join(event_data['datetimes'])}")
        
        return grouped_events

    async def scrape(self):
        """Scrape California Theatre events"""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()
                logging.info("Navigating to California Theatre site...")
                
                # Add timeout and wait until network is idle
                await page.goto('https://www.caltheatre.com/', 
                              wait_until='networkidle',
                              timeout=30000)  # 30 second timeout
                
                logging.info("Page loaded, looking for events...")
                
                # Wait for events to load with timeout
                try:
                    await page.wait_for_selector('[data-hook="event-list-item"]', 
                                              timeout=10000)  # 10 second timeout
                except Exception as e:
                    logging.error(f"Timeout waiting for events: {e}")
                    # Save page content for debugging
                    html = await page.content()
                    with open('cal_theatre_error.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    return []
                
                logging.info("Found event elements, extracting data...")
                events = []
                event_elements = await page.query_selector_all('[data-hook="event-list-item"]')
                logging.info(f"Found {len(event_elements)} event elements")
                
                for element in event_elements:
                    try:
                        # Extract title
                        title = await element.query_selector('[data-hook="ev-list-item-title"]')
                        title_text = await title.inner_text() if title else None
                        
                        if title_text:
                            logging.info(f"Processing event: {title_text}")
                        
                        # Extract date and time
                        date_element = await element.query_selector('[data-hook="ev-full-date-location"] [data-hook="date"]')
                        date_text = await date_element.inner_text() if date_element else None
                        
                        # Extract description
                        desc = await element.query_selector('[data-hook="ev-list-item-description"]')
                        desc_text = await desc.inner_text() if desc else None
                        
                        # Extract image URL
                        img = await element.query_selector('img')
                        img_url = await img.get_attribute('src') if img else None
                        
                        # Extract ticket URL
                        ticket_link = await element.query_selector('[data-hook="ev-rsvp-button"]')
                        ticket_url = await ticket_link.get_attribute('href') if ticket_link else None
                        
                        # Parse datetime
                        datetime_obj = None
                        if date_text:
                            try:
                                # Example format: "Dec 06, 2024, 4:00 PM – 6:00 PM"
                                date_parts = date_text.split(',')
                                date_str = f"{date_parts[0]}, {date_parts[1]}"
                                time_str = date_parts[2].split('–')[0].strip()
                                datetime_str = f"{date_str} {time_str}"
                                datetime_obj = datetime.strptime(datetime_str, '%b %d, %Y %I:%M %p')
                            except Exception as e:
                                logging.error(f"Date parsing error: {e}")
                        
                        if title_text and datetime_obj:
                            events.append({
                                'title': title_text,
                                'datetime': datetime_obj,
                                'description': desc_text,
                                'image_url': img_url,
                                'ticket_url': ticket_url,
                                'venue': 'California Theatre'
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
                        await page.wait_for_timeout(1000)  # Wait for new events to load
                    except Exception:
                        break
                    
                return events
                
            except Exception as e:
                logging.error(f"Failed to scrape California Theatre events: {e}")
                logging.error(f"Error type: {type(e).__name__}")
                return []
                
            finally:
                await browser.close()