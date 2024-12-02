from .base import BaseAnalyzer
import logging
from anthropic import Anthropic

class ClaudeAnalyzer(BaseAnalyzer):
    def __init__(self, api_key, config=None):
        super().__init__(config)
        self.client = Anthropic(api_key=api_key)
        
    def analyze(self, events):
        if not events:
            logging.error("No events to analyze")
            return None
            
        # Log the original events once with more detail
        logging.info("Events to analyze:")
        for i, event in enumerate(events):
            logging.info(f"  {i+1}. {event.get('title')} ({event.get('datetime')})")
            if event.get('description'):
                logging.debug(f"     Description: {event.get('description')[:100]}...")
        
        prompt = """You are an event analyzer. You will ONLY analyze the ACTUAL events provided.
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
        1. ONLY analyze the events provided in the JSON data
        2. DO NOT create new events or modify existing ones
        3. Give low scores (1-3) to events that don't match preferences
        4. Use the exact titles and dates from the JSON data
        
        Given these ACTUAL events from the calendar:
        {events_json}
        
        Format your response in HTML using this EXACT structure:
        
        <div class="event">
            <div class="score">Score: [X/10]</div>
            <div class="title">[EXACT event title from JSON]</div>
            <div class="datetime">[EXACT datetime from JSON]</div>
            <div class="image"><img src="[EXACT image_url from JSON]" alt="[EXACT event title]"></div>
            <div class="explanation">Why this score: [Brief explanation]</div>
        </div>
        """
        
        try:
            import json
            formatted_prompt = prompt.format(
                events_json=json.dumps(events, indent=2)
            )
            
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2500,
                messages=[
                    {
                        "role": "user", 
                        "content": formatted_prompt
                    }
                ]
            )
            
            # Get the content
            content = message.content
            
            # Handle list response
            if isinstance(content, list):
                content = ' '.join(str(item) for item in content)
            
            # Handle string response
            if isinstance(content, str):
                if "TextBlock(text='" in content:
                    content = content.split("TextBlock(text='", 1)[1].rsplit("'", 1)[0]
                
                # Only keep the HTML part
                if "<div class=\"event\">" in content:
                    content = content[content.index("<div class=\"event\">"):]
                    
                # Clean up newlines and spaces
                content = content.replace('\\n', ' ')
                content = content.replace('\n', ' ')
                content = ' '.join(content.split())
                
                # Split into individual events
                events = content.split('<div class="event">')
                events = [e.strip() for e in events if e.strip()]
                
                # Extract score for each event and sort
                def get_score(event_html):
                    try:
                        score_start = event_html.find('Score: ') + 7
                        score_end = event_html.find('/10', score_start)
                        return int(event_html[score_start:score_end])
                    except:
                        return 0
                
                # Sort events by score in descending order
                events.sort(key=get_score, reverse=True)
                
                # Recombine events
                content = '<div class="event">' + '<div class="event">'.join(events)
                
                # Count events in response
                event_count = content.count('<div class="event">')
                logging.info(f"Events in Claude's response: {event_count} events sorted by score")
            
            return content
            
        except Exception as e:
            logging.error(f"Claude analysis failed: {e}")
            logging.error(f"Error details: {type(e).__name__}")
            logging.error(f"Error value: {str(e)}")
            return None
