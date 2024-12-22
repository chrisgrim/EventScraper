from datetime import datetime, timedelta
from .base import BaseAnalyzer
import logging
from anthropic import Anthropic
import json

class ClaudeAnalyzer(BaseAnalyzer):
    def __init__(self, api_key, config=None):
        super().__init__(config)
        self.client = Anthropic(api_key=api_key)
        
    def _parse_datetime(self, datetime_str):
        """Parse different datetime formats"""
        try:
            # Add debug logging
            logging.debug(f"Parsing datetime: {datetime_str}")
            
            # Split multiple dates and take the first one
            dates = datetime_str.split(' and ')
            first_date = dates[0].strip()
            
            # If it's a range, take the start date
            if ' - ' in first_date:
                first_date = first_date.split(' - ')[0].strip()
            
            # Try ISO format first (YYYY-MM-DD HH:MM:SS)
            try:
                if '-' in first_date:
                    # Handle both full datetime and date-only formats
                    if ' ' in first_date:
                        parsed_date = datetime.strptime(first_date, '%Y-%m-%d %H:%M:%S')
                    else:
                        parsed_date = datetime.strptime(first_date, '%Y-%m-%d')
                    logging.debug(f"Successfully parsed ISO date: {parsed_date}")
                    return parsed_date
            except ValueError:
                logging.debug("Failed to parse ISO format, trying text format")
            
            # Extract just the month, day, and year for text format
            parts = first_date.split()
            month = None
            day = None
            year = None
            time_str = None
            
            for i, part in enumerate(parts):
                # Find month (case insensitive)
                if part.capitalize() in ['January', 'February', 'March', 'April', 'May', 'June', 
                           'July', 'August', 'September', 'October', 'November', 'December']:
                    month = part.capitalize()
                # Find day (number, possibly with suffix)
                elif part.rstrip('thsnrd').isdigit() and int(part.rstrip('thsnrd')) <= 31:
                    day = int(part.rstrip('thsnrd'))
                # Find year
                elif part.isdigit() and len(part) == 4:
                    year = int(part)
                # Look for time (e.g., "3:00pm")
                elif ':' in part.lower() and ('am' in part.lower() or 'pm' in part.lower()):
                    time_str = part
                # Handle separate am/pm
                elif i > 0 and ':' in parts[i-1] and part.lower() in ['am', 'pm']:
                    time_str = parts[i-1] + part
            
            # Add default year if missing
            if not year:
                current_year = datetime.now().year
                if month == 'December':
                    year = current_year
                else:
                    year = current_year + 1
                
            if month and day and year:
                try:
                    base_date = datetime(year, 
                                  ['January', 'February', 'March', 'April', 'May', 'June', 
                                   'July', 'August', 'September', 'October', 'November', 'December'].index(month) + 1, 
                                  day)
                    
                    # Add time if available
                    if time_str:
                        try:
                            time = datetime.strptime(time_str.lower(), '%I:%M%p').time()
                            base_date = datetime.combine(base_date.date(), time)
                        except ValueError:
                            try:
                                time = datetime.strptime(time_str.lower(), '%I:%M %p').time()
                                base_date = datetime.combine(base_date.date(), time)
                            except ValueError:
                                pass
                    
                    logging.debug(f"Successfully parsed text date: {base_date}")
                    return base_date
                except ValueError as e:
                    logging.error(f"Error creating datetime: {e}")
                    return None
            
            logging.error(f"Could not parse date components from: {datetime_str}")
            return None
            
        except Exception as e:
            logging.error(f"Date parsing error for '{datetime_str}': {str(e)}")
            return None

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
                
                event_key = self._get_event_key(title, description)
                event_date = self._parse_datetime(datetime_str)
                
                if event_date and title:
                    event_data = {
                        'title': title,
                        'url': url,
                        'datetime': datetime_str,
                        'description': description,
                        'image': image_html,
                        'first_date': event_date
                    }
                    
                    if event_key in event_groups:
                        if datetime_str not in event_groups[event_key]['datetimes']:
                            event_groups[event_key]['datetimes'].append(datetime_str)
                    else:
                        event_groups[event_key] = {
                            'title': title,
                            'url': url,
                            'datetimes': [datetime_str],
                            'description': description,
                            'image': image_html,
                            'first_date': event_date
                        }
                        
                        # Sort into appropriate time period
                        if event_date <= this_week_end:
                            this_week_events.append(event_data)
                        elif event_date <= next_week_end:
                            next_week_events.append(event_data)
                        else:
                            future_events.append(event_data)
                
            except Exception as e:
                logging.error(f"Error parsing event HTML: {e}")
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

        return '\n'.join(html)
    
    def _format_event_card(self, event):
        """Format a single event card with email-safe styles"""
        # Format the datetime string to be more readable
        formatted_dates = []
        for dt_str in event['datetimes']:
            try:
                # Handle date ranges
                if ' - ' in dt_str:
                    start_date, end_date = dt_str.split(' - ')
                    try:
                        # Parse and format start date
                        start_dt = datetime.strptime(start_date.strip(), '%Y-%m-%d %H:%M:%S')
                        start_formatted = start_dt.strftime('%A %I:%M %p, %b %d %Y').replace(' 0', ' ')
                        
                        # Parse and format end date
                        end_dt = datetime.strptime(end_date.strip(), '%Y-%m-%d %H:%M:%S')
                        end_formatted = end_dt.strftime('%A %I:%M %p, %b %d %Y').replace(' 0', ' ')
                        
                        formatted_dates.append(f"{start_formatted} - {end_formatted}")
                    except ValueError:
                        # If parsing fails, use original string
                        formatted_dates.append(dt_str)
                else:
                    dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                    formatted_date = dt.strftime('%A %I:%M %p, %b %d %Y').replace(' 0', ' ')
                    formatted_dates.append(formatted_date)
            except ValueError:
                # If parsing fails, use the original string
                formatted_dates.append(dt_str)
        
        formatted_datetime = ' and '.join(formatted_dates)
        
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

    async def analyze(self, events):
        if not events:
            logging.error("No events to analyze")
            return None
            
        # Process events in batches of 30
        BATCH_SIZE = 30
        all_results = []
        
        for i in range(0, len(events), BATCH_SIZE):
            batch = events[i:i + BATCH_SIZE]
            logging.info(f"Processing batch {i//BATCH_SIZE + 1} of {(len(events) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} events)")
            
            prompt = f"""Format these events in HTML. Include ALL event details exactly as provided.
            
            Given these events from the calendar:
            {json.dumps(batch, indent=2)}
            
            Format your response in HTML. Each event MUST be wrapped in a div with data-type="event" and MUST follow this EXACT structure:
            
            <div data-type="event">
                <div data-type="title"><a href="[EXACT url from JSON]">[EXACT event title from JSON]</a></div>
                <div data-type="datetime">[EXACT datetime from JSON]</div>
                <div data-type="image-container"><img src="[EXACT image_url from JSON]" alt="[EXACT event title]" style="width:100%; height:100%; object-fit:cover;"></div>
                <div data-type="description">[EXACT description from JSON if it exists]</div>
            </div>
            
            Do not add any extra elements or modify the structure. Each event must have these exact data-type attributes.
            """
            
            try:
                message = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                content = message.content[0].text
                
                if isinstance(content, str):
                    if '<div data-type="event">' in content:
                        content = content[content.index('<div data-type="event">'):]
                    content = content.replace('\\n', ' ').replace('\n', ' ')
                    all_results.append(content)
                    
            except Exception as e:
                logging.error(f"Batch processing failed: {e}")
                continue
        
        # Combine and organize all results
        if all_results:
            combined_content = '\n'.join(all_results)
            return self._organize_events_by_time(combined_content)
        
        return None
