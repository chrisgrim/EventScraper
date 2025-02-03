from datetime import datetime, timedelta
from .base import BaseAnalyzer
import logging
from anthropic import Anthropic
import json
from .date_parser import DateParser
import time  # Add this import at the top

# Set up module-level logger
logger = logging.getLogger(__name__)

class ClaudeAnalyzer(BaseAnalyzer):
    def __init__(self, api_key, config=None):
        super().__init__(config)
        self.client = Anthropic(api_key=api_key)
        self.date_parser = DateParser()
        # Add configuration for retries
        self.max_retries = 3
        self.batch_size = 5  # Reduced from 15
        self.retry_delay = 1  # Base delay in seconds
        
    def _parse_datetime(self, datetime_str):
        return self.date_parser.parse(datetime_str)

    def _get_event_key(self, title, description=''):
        """Generate a unique key for an event based on title and description"""
        return f"{title.lower()}_{description.lower()}"

    def _organize_events_by_time(self, events_html):
        """Organize events into time-based sections"""
        now = datetime.now()
        
        # Get start of current week (Monday)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get end of current week (Sunday)
        this_week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # Get end of next week
        next_week_end = this_week_end + timedelta(days=7)
        
        # Format date ranges for headers
        this_week_range = f"{week_start.strftime('%b %d')} - {this_week_end.strftime('%b %d')}"
        next_week_range = f"{(this_week_end + timedelta(days=1)).strftime('%b %d')} - {next_week_end.strftime('%b %d')}"
        
        logger.info(f"Date ranges:")
        logger.info(f"This week: {this_week_range}")
        logger.info(f"Next week: {next_week_range}")
        
        # Create date-based dictionaries for each section
        this_week_events = []
        next_week_events = []
        future_events = []
        
        event_groups = {}  # Track unique events
        
        # Split into individual events - try both with and without data-type attribute
        events = []
        if '<div data-type="event">' in events_html:
            events = events_html.split('<div data-type="event">')
        else:
            # Fallback to simpler div structure
            temp_events = events_html.split('<div>')
            events = [e for e in temp_events if '<div data-type="title">' in e or '<div data-type="datetime">' in e]
        
        events = [e.strip() for e in events if e.strip()]
        
        for event_html in events:
            try:
                # Extract title and URL
                title_start = event_html.find('<div data-type="title">') + len('<div data-type="title">')
                title_end = event_html.find('</div>', title_start)
                title_html = event_html[title_start:title_end].strip()
                
                # Parse URL from title HTML if it exists
                url = ''
                if 'href="' in title_html:
                    url_start = title_html.find('href="') + 6
                    url_end = title_html.find('"', url_start)
                    url = title_html[url_start:url_end]
                    title = title_html[title_html.find('>')+1:title_html.find('</a>')]
                else:
                    title = title_html
                
                # Extract datetime
                datetime_start = event_html.find('<div data-type="datetime">') + len('<div data-type="datetime">')
                datetime_end = event_html.find('</div>', datetime_start)
                datetime_str = event_html[datetime_start:datetime_end].strip()
                
                # Extract description
                description = ''
                if '<div data-type="description">' in event_html:
                    desc_start = event_html.find('<div data-type="description">') + len('<div data-type="description">')
                    desc_end = event_html.find('</div>', desc_start)
                    description = event_html[desc_start:desc_end].strip()
                
                # Extract image
                img_start = event_html.find('<div data-type="image-container">') + len('<div data-type="image-container">')
                img_end = event_html.find('</div>', img_start)
                image_html = event_html[img_start:img_end].strip() if '<div data-type="image-container">' in event_html else ''
                
                logger.debug(f"Processing event '{title}' with date: {datetime_str}")
                
                # Handle multiple dates in datetime_str
                dates = []
                if ' and ' in datetime_str:
                    date_strings = datetime_str.split(' and ')
                    for date_str in date_strings:
                        parsed_date = self._parse_datetime(date_str.strip())
                        if parsed_date:
                            dates.append(parsed_date)
                            logger.debug(f"Parsed multiple date: {parsed_date} from {date_str}")
                    
                    if dates:
                        # Use earliest date for sorting
                        event_date = min(dates)
                        logger.debug(f"Using earliest date for sorting: {event_date}")
                    else:
                        # Try parsing the whole string as a single date
                        event_date = self._parse_datetime(datetime_str)
                        logger.debug(f"Falling back to single date parse: {event_date}")
                else:
                    event_date = self._parse_datetime(datetime_str)
                    logger.debug(f"Parsed single date: {event_date}")
                
                if event_date and title:
                    event_data = {
                        'title': title,
                        'url': url,
                        'datetime': datetime_str,  # Keep original datetime string
                        'description': description,
                        'image': image_html,
                        'first_date': event_date
                    }
                    
                    event_key = self._get_event_key(title, description)
                    event_groups[event_key] = event_data  # Store the event in groups
                    
                    # Add debug logging for categorization
                    if event_date <= this_week_end:
                        logger.debug(f"Adding '{title}' to this week's events")
                        this_week_events.append(event_data)
                    elif event_date <= next_week_end:
                        logger.debug(f"Adding '{title}' to next week's events")
                        next_week_events.append(event_data)
                    else:
                        logger.debug(f"Adding '{title}' to future events")
                        future_events.append(event_data)
                else:
                    logger.warning(f"Skipped event '{title}' - Invalid date: {datetime_str}")
                
            except Exception as e:
                logger.error(f"Error parsing event HTML: {e}")
                continue
        
        # Sort each list by date
        this_week_events.sort(key=lambda x: x['first_date'])
        next_week_events.sort(key=lambda x: x['first_date'])
        future_events.sort(key=lambda x: x['first_date'])
        
        # Generate HTML for each section
        html = []
        
        if this_week_events:
            html.append(f'''
                <h2 style="margin-top:40px; 
                           margin-bottom:20px; 
                           color:#2c3e50; 
                           border-bottom:2px solid #3498db; 
                           padding-bottom:10px;">
                    This Week ({this_week_range})
                </h2>
            ''')
            
            html.append('<table cellspacing="20" style="width:100%;"><tr>')
            for i, event in enumerate(this_week_events):
                if i > 0 and i % 4 == 0:
                    html.append('</tr><tr>')
                event_key = self._get_event_key(event['title'], event['description'])
                html.append(f'<td style="width:25%; vertical-align:top;">{self._format_event_card(event_groups[event_key])}</td>')
            
            remaining = 4 - (len(this_week_events) % 4)
            if remaining < 4:
                html.extend(['<td style="width:25%;"></td>'] * remaining)
            
            html.append('</tr></table>')

        if next_week_events:
            html.append(f'''
                <h2 style="margin-top:40px; 
                           margin-bottom:20px; 
                           color:#2c3e50; 
                           border-bottom:2px solid #3498db; 
                           padding-bottom:10px;">
                    Next Week ({next_week_range})
                </h2>
            ''')
            
            html.append('<table cellspacing="20" style="width:100%;"><tr>')
            for i, event in enumerate(next_week_events):
                if i > 0 and i % 4 == 0:
                    html.append('</tr><tr>')
                event_key = self._get_event_key(event['title'], event['description'])
                html.append(f'<td style="width:25%; vertical-align:top;">{self._format_event_card(event_groups[event_key])}</td>')
            
            remaining = 4 - (len(next_week_events) % 4)
            if remaining < 4:
                html.extend(['<td style="width:25%;"></td>'] * remaining)
            
            html.append('</tr></table>')

        if future_events:
            html.append('''
                <h2 style="margin-top:40px; 
                           margin-bottom:20px; 
                           color:#2c3e50; 
                           border-bottom:2px solid #3498db; 
                           padding-bottom:10px;">
                    Future Events
                </h2>
            ''')
            
            html.append('<table cellspacing="20" style="width:100%;"><tr>')
            for i, event in enumerate(future_events):
                if i > 0 and i % 4 == 0:
                    html.append('</tr><tr>')
                event_key = self._get_event_key(event['title'], event['description'])
                html.append(f'<td style="width:25%; vertical-align:top;">{self._format_event_card(event_groups[event_key])}</td>')
            
            remaining = 4 - (len(future_events) % 4)
            if remaining < 4:
                html.extend(['<td style="width:25%;"></td>'] * remaining)
            
            html.append('</tr></table>')

        # After categorizing events, log the results
        logger.info("\nEvent categorization results:")
        logger.info("\nThis week events:")
        for event in this_week_events:
            logger.info(f"- {event['title']}: {event['datetime']}")
        
        logger.info("\nNext week events:")
        for event in next_week_events:
            logger.info(f"- {event['title']}: {event['datetime']}")
        
        logger.info("\nFuture events:")
        for event in future_events:
            logger.info(f"- {event['title']}: {event['datetime']}")

        return '\n'.join(html)
    
    def _format_event_card(self, event):
        """Format a single event card with email-safe styles"""
        try:
            # Parse the datetime string
            formatted_datetime = event['datetime']
            if ' to ' in event['datetime']:
                # Handle date range format
                start_date, end_date = event['datetime'].split(' to ')
                try:
                    start_dt = datetime.strptime(start_date.strip(), '%Y-%m-%d %H:%M:%S')
                    end_dt = datetime.strptime(end_date.strip(), '%Y-%m-%d %H:%M:%S')
                    formatted_datetime = f"{start_dt.strftime('%A %I:%M %p, %b %d %Y')} to {end_dt.strftime('%A %I:%M %p, %b %d %Y')}".replace(' 0', ' ')
                except ValueError:
                    # If parsing fails, use original string
                    formatted_datetime = event['datetime']
            elif ' and ' in event['datetime']:
                # Handle multiple individual dates
                date_strings = event['datetime'].split(' and ')
                formatted_dates = []
                for dt_str in date_strings:
                    try:
                        dt = datetime.strptime(dt_str.strip(), '%Y-%m-%d %H:%M:%S')
                        formatted_date = dt.strftime('%A %I:%M %p, %b %d %Y').replace(' 0', ' ')
                        formatted_dates.append(formatted_date)
                    except ValueError:
                        formatted_dates.append(dt_str)
                formatted_datetime = ' and '.join(formatted_dates)
            else:
                # Handle single date
                try:
                    dt = datetime.strptime(event['datetime'].strip(), '%Y-%m-%d %H:%M:%S')
                    formatted_datetime = dt.strftime('%A %I:%M %p, %b %d %Y').replace(' 0', ' ')
                except ValueError:
                    formatted_datetime = event['datetime']
            
            # Create title with link if URL exists
            title_html = event["title"]
            if event.get("url"):
                title_html = f'<a href="{event["url"]}" style="color:#2c3e50; text-decoration:none;">{event["title"]}</a>'
            
            return f'''
                <div style="background:#fff; border:1px solid #ddd; border-radius:8px; overflow:hidden;">
                    <div style="overflow:hidden;">
                        {event['image'].replace('<img', '<img style="width:100%; height:auto; display:block;"')}
                    </div>
                    <div style="padding:15px;">
                        <div style="font-weight:bold; margin-bottom:8px;">
                            {title_html}
                        </div>
                        <div style="color:#666; font-size:0.9em; margin-bottom:8px;">
                            {formatted_datetime}
                        </div>
                        <div style="font-size:0.9em;">
                            {event["description"] if event["description"] else ""}
                        </div>
                    </div>
                </div>
            '''
        except Exception as e:
            logger.error(f"Error formatting event card: {e}")
            return ""

    def analyze(self, events):
        if not events:
            logger.info("No events provided for analysis")
            return None
            
        logger.info(f"Starting analysis of {len(events)} total events")
        
        # Track events by source for validation
        sources = {}
        for event in events:
            source = event.get('venue', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        logger.debug("Input events by source:")
        for source, count in sources.items():
            logger.debug(f"- {source}: {count} events")
        
        # Use smaller batch size
        total_batches = (len(events) + self.batch_size - 1) // self.batch_size
        all_results = []
        
        for i in range(0, len(events), self.batch_size):
            batch = events[i:i + self.batch_size]
            batch_num = i//self.batch_size + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} events)")
            logger.debug("Events in this batch:")
            for event in batch:
                logger.debug(f"- {event.get('title', 'Unknown Title')}")
            
            # Add retry logic
            for attempt in range(self.max_retries):
                try:
                    # Create the prompt for this batch
                    prompt = f'''Format these events in HTML. Include ALL event details exactly as provided.
                    IMPORTANT: For events with multiple dates, you MUST include ALL dates in the datetime field, separated by " and ".
                    Each date MUST be formatted in ISO format (YYYY-MM-DD HH:MM:SS).

                    For example, if an event occurs on multiple dates:
                    <div data-type="datetime">2024-01-01 19:00:00 and 2024-01-02 19:00:00 and 2024-01-03 19:00:00</div>

                    Given these events from the calendar:
                    {json.dumps(batch, indent=2)}

                    Format your response in HTML. Each event MUST be wrapped in a div with data-type="event" and MUST follow this EXACT structure:

                    <div data-type="event">
                        <div data-type="title"><a href="[EXACT url from JSON]">[EXACT event title from JSON]</a></div>
                        <div data-type="datetime">[ALL dates in YYYY-MM-DD HH:MM:SS format, separated by " and "]</div>
                        <div data-type="image-container"><img src="[EXACT image_url from JSON]" alt="[EXACT event title]" style="width:100%; height:100%; object-fit:cover;"></div>
                        <div data-type="description">[EXACT description from JSON if it exists]</div>
                    </div>

                    Example datetime formats:
                    - Single date: "2024-01-01 19:00:00"
                    - Multiple dates: "2024-01-01 19:00:00 and 2024-01-02 19:00:00"
                    - All-day event: "2024-01-01 00:00:00"

                    Do not add any extra elements or modify the structure. Each event must have these exact data-type attributes.
                    '''
                    
                    logger.debug(f"Making request to Claude API (attempt {attempt + 1}/{self.max_retries})...")
                    completion = self.client.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=4000,
                        temperature=0,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    
                    # If request succeeds, process the response
                    logger.debug(f"Response received, type: {type(completion)}")
                    if completion and hasattr(completion, 'content'):
                        content = completion.content[0].text if completion.content else ""
                        if '<div data-type="event">' in content:
                            content = content[content.index('<div data-type="event">'):]
                            all_results.append(content)
                            logger.info(f"Successfully processed batch {batch_num}/{total_batches}")
                            # Add delay between successful batches
                            if i + self.batch_size < len(events):
                                time.sleep(1)
                            break
                    
                except Exception as e:
                    wait_time = (2 ** attempt) * self.retry_delay
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        logger.info(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All attempts failed for batch {batch_num}: {str(e)}")
                        continue

        # Combine and organize all results
        if all_results:
            combined_content = '\n'.join(all_results)
            logger.debug(f"Combined HTML before processing:\n{combined_content}")
            
            # Validate total events
            total_events = combined_content.count('<div data-type="event">')
            if total_events < len(events):
                logger.warning(f"Some events may have been lost (got {total_events}, expected {len(events)})")
            
            logger.info("Organizing events by time period...")
            result = self._organize_events_by_time(combined_content)
            logger.info("Analysis complete")
            return result
        
        logger.error("Analysis failed - no results generated")
        return None

    def test_analyze(self):
        """Test function with dummy data"""
        logger.info("Running test analysis with dummy data")
        
        # Get dates for next week and the week after
        now = datetime.now()
        next_week = now + timedelta(days=7)
        week_after = now + timedelta(days=14)
        
        # Dummy test events with future dates
        test_events = [
            {
                "title": "Test Event 1",
                "url": "https://example.com/event1",
                "datetime": next_week.strftime("%Y-%m-%d 19:00:00"),
                "description": "This is a test event",
                "image_url": "https://example.com/image1.jpg",
                "venue": "Test Venue"
            },
            {
                "title": "Test Event 2",
                "url": "https://example.com/event2",
                "datetime": week_after.strftime("%Y-%m-%d 20:00:00"),
                "description": "Another test event",
                "image_url": "https://example.com/image2.jpg",
                "venue": "Test Venue"
            }
        ]
        
        try:
            # Test the analyze method
            logger.info("Starting test analysis")
            result = self.analyze(test_events)
            logger.info("Test analysis completed")
            return result
        except Exception as e:
            logger.error(f"Test analysis failed: {e}", exc_info=True)
            return None
