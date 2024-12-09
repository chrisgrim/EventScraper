from .base import BaseAnalyzer
import logging
from anthropic import Anthropic
import json

class ClaudeAnalyzer(BaseAnalyzer):
    def __init__(self, api_key, config=None):
        super().__init__(config)
        self.client = Anthropic(api_key=api_key)
        
    def _group_events(self, events_html):
        """Group events with same title but different dates"""
        event_groups = {}
        
        # Split into individual events
        events = events_html.split('<div class="event">')
        events = [e.strip() for e in events if e.strip()]
        
        for event_html in events:
            try:
                # Extract title and URL
                title_start = event_html.find('<div class="title">') + len('<div class="title">')
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
                datetime_start = event_html.find('<div class="datetime">') + len('<div class="datetime">')
                datetime_end = event_html.find('</div>', datetime_start)
                datetime = event_html[datetime_start:datetime_end].strip()
                
                # Extract score - more robust parsing
                score = 0
                if 'Score: ' in event_html:
                    score_text = event_html[event_html.find('Score: '):event_html.find('/10')]
                    score = int(''.join(filter(str.isdigit, score_text)))
                
                # Extract description
                description = ''
                if '<div class="description">' in event_html:
                    desc_start = event_html.find('<div class="description">') + len('<div class="description">')
                    desc_end = event_html.find('</div>', desc_start)
                    description = event_html[desc_start:desc_end].strip()
                
                # Extract explanation
                exp_start = event_html.find('<div class="explanation">') + len('<div class="explanation">')
                exp_end = event_html.find('</div>', exp_start)
                explanation = event_html[exp_start:exp_end].strip()
                
                # Extract image
                img_start = event_html.find('<div class="image">') + len('<div class="image">')
                img_end = event_html.find('</div>', img_start)
                image_html = event_html[img_start:img_end].strip() if '<div class="image">' in event_html else ''
                
                if title and datetime:  # Only process if we have at least title and datetime
                    if title.lower() in event_groups:
                        # Add this datetime to existing event
                        event_groups[title.lower()]['datetimes'].append(datetime)
                    else:
                        # Create new event group
                        event_groups[title.lower()] = {
                            'title': title,
                            'url': url,
                            'datetimes': [datetime],
                            'score': score,
                            'description': description,
                            'explanation': explanation,
                            'image': image_html
                        }
                
            except Exception as e:
                logging.error(f"Error parsing event HTML: {e}")
                continue
        
        # Convert groups back to HTML format
        grouped_html = []
        for event_data in sorted(event_groups.values(), key=lambda x: x['score'], reverse=True):
            title_html = f'<a href="{event_data["url"]}">{event_data["title"]}</a>' if event_data["url"] else event_data["title"]
            description_html = f'<div class="description">{event_data["description"]}</div>' if event_data["description"] else ''
            
            grouped_html.append(f"""
            <div class="event">
                <div class="score">Score: {event_data['score']}/10</div>
                <div class="title">{title_html}</div>
                <div class="datetime">{' and '.join(event_data['datetimes'])}</div>
                <div class="image">{event_data['image']}</div>
                {description_html}
                <div class="explanation">{event_data['explanation']}</div>
            </div>
            """.strip())
        
        return '\n'.join(grouped_html)

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
            
            # Log the batch events
            for j, event in enumerate(batch):
                logging.info(f"  {i+j+1}. {event.get('title')} ({event.get('datetime')})")
                if event.get('description'):
                    logging.debug(f"     Description: {event.get('description')[:100]}...")
            
            system_prompt = f"You must analyze ALL {len(batch)} events in this batch. Do not stop until every event has been scored."
            
            prompt = f"""You are an event analyzer. You will ONLY analyze the ACTUAL events provided.
            DO NOT create or imagine new events. Only work with the events in the JSON data.
            
            Here are my preferences for events:
            
            Strong Interests:
            - Immersive theater
            - Murder mysteries
            - Unique experiences for adults
            
            Moderate Interests:
            - Unique drinking experiences
            - Wine tasting
            - Puzzle hunts
            
            Dislikes:
            - Sports (football, baseball, etc.)
            - Shopping/consumer events
            
            IMPORTANT: 
            1. ONLY analyze the events provided in the JSON data ({len(batch)} events in this batch)
            2. DO NOT create new events or modify existing ones
            3. Give low scores (1-3) to events that don't match preferences
            4. Use the exact titles and dates from the JSON data
            5. YOU MUST ANALYZE ALL {len(batch)} EVENTS - DO NOT STOP EARLY
            
            Given these ACTUAL events from the calendar:
            {json.dumps(batch, indent=2)}
            
            Format your response in HTML using this EXACT structure for ALL {len(batch)} events:
            
            <div class="event">
                <div class="score">Score: [X/10]</div>
                <div class="title"><a href="[EXACT url from JSON]">[EXACT event title from JSON]</a></div>
                <div class="datetime">[EXACT datetime from JSON]</div>
                <div class="image"><img src="[EXACT image_url from JSON]" alt="[EXACT event title]"></div>
                <div class="description">[EXACT description from JSON if it exists]</div>
                <div class="explanation">Why this score: [Brief explanation]</div>
            </div>
            """
            
            try:
                message = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ]
                )
                
                content = message.content[0].text
                
                if isinstance(content, list):
                    content = ' '.join(str(item) for item in content)
                
                if isinstance(content, str):
                    if "TextBlock(text='" in content:
                        content = content.split("TextBlock(text='", 1)[1].rsplit("'", 1)[0]
                    
                    if "<div class=\"event\">" in content:
                        content = content[content.index("<div class=\"event\">"):]
                        
                    content = content.replace('\\n', ' ')
                    content = content.replace('\n', ' ')
                    content = ' '.join(content.split())
                    
                    all_results.append(content)
                    logging.info(f"Successfully processed batch {i//BATCH_SIZE + 1}")
                    
            except Exception as e:
                logging.error(f"Batch processing failed: {e}")
                logging.error(f"Error details: {type(e).__name__}")
                logging.error(f"Error value: {str(e)}")
                continue
        
        # Combine and group all results
        if all_results:
            combined_content = '\n'.join(all_results)
            grouped_content = self._group_events(combined_content)
            
            # Count unique events after grouping
            event_count = grouped_content.count('<div class="event">')
            logging.info(f"Events after grouping: {event_count} unique events")
            
            return grouped_content
        
        return None
