from datetime import datetime, timedelta
import logging
import re

class DateParser:
    """Flexible date parsing system with configurable formats and rules"""
    
    def __init__(self):
        # Core date patterns from most specific to least specific
        self.date_patterns = [
            # ISO format
            {
                'pattern': r'(\d{4}-\d{2}-\d{2}(?:\s\d{2}:\d{2}:\d{2})?)',
                'format': ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d'],
                'name': 'iso'
            },
            # Full date with weekday
            {
                'pattern': r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
                'format': ['%B %d, %Y', '%B %d %Y'],
                'name': 'weekday_full'
            },
            # Month Day-Day, Year range
            {
                'pattern': r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2})[-–](?:\w+\s+)?(\d{1,2}),?\s*(\d{4})',
                'format': None,  # Custom handling
                'name': 'month_range'
            },
            # Month Day, Year
            {
                'pattern': r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
                'format': ['%B %d, %Y', '%B %d %Y'],
                'name': 'full_text'
            },
            # Abbreviated month (Jan, Feb, etc)
            {
                'pattern': r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
                'format': ['%b %d, %Y', '%b %d %Y'],
                'name': 'abbrev_month'
            },
            # MM/DD/YYYY or MM-DD-YYYY
            {
                'pattern': r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                'format': ['%m/%d/%Y', '%m-%d-%Y'],
                'name': 'numeric_date'
            },
            # Month Day (current/next year implied)
            {
                'pattern': r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?)',
                'format': ['%B %d'],
                'name': 'month_day'
            },
            # Abbreviated month day (no year)
            {
                'pattern': r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?)',
                'format': ['%b %d'],
                'name': 'abbrev_month_day'
            }
        ]
        
        self.time_patterns = [
            # 12-hour time with optional space (3:00pm, 3:00 pm)
            {
                'pattern': r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))',
                'format': ['%I:%M%p', '%I:%M %p'],
                'name': '12hour'
            },
            # 12-hour time with period (3:00 p.m.)
            {
                'pattern': r'(\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|A\.M\.|P\.M\.))',
                'format': ['%I:%M %p'],
                'name': '12hour_period'
            },
            # 24-hour time
            {
                'pattern': r'(\d{2}:\d{2})',
                'format': ['%H:%M'],
                'name': '24hour'
            }
        ]
        
        self.range_separators = [
            ' - ', '–', ' to ', ' through ', ' until ', '−'
        ]

    def parse(self, date_string):
        """Parse a date string using all available patterns"""
        try:
            logging.debug(f"Attempting to parse date: {date_string}")
            
            if not date_string:
                logging.error("Empty date string provided")
                return None
                
            # Clean the input
            date_string = self._clean_input(date_string)
            
            # Handle location prefixes
            date_string = self._remove_location_prefix(date_string)
            
            # Try parsing as a range first
            start_date, end_date = self._parse_date_range(date_string)
            if start_date:
                logging.debug(f"Successfully parsed date range: {start_date} to {end_date}")
                return start_date  # Return start date for sorting purposes
            
            # Handle multiple dates
            dates = self._split_multiple_dates(date_string)
            if dates:
                parsed_dates = [self._parse_single_date(d) for d in dates]
                valid_dates = [d for d in parsed_dates if d is not None]
                if valid_dates:
                    earliest_date = min(valid_dates)
                    logging.debug(f"Found multiple dates, using earliest: {earliest_date}")
                    return earliest_date
            
            # Try parsing as single date
            parsed_date = self._parse_single_date(date_string)
            if parsed_date and self._validate_date(parsed_date):
                return parsed_date
                
            logging.error(f"Failed to parse date string: {date_string}")
            return None
            
        except Exception as e:
            logging.error(f"Date parsing failed for '{date_string}': {str(e)}")
            return None

    def _clean_input(self, date_string):
        """Clean and normalize input string"""
        if not date_string:
            return date_string
        
        # Convert to string if needed
        date_string = str(date_string).strip()
        
        # Normalize whitespace
        date_string = ' '.join(date_string.split())
        
        # Normalize separators
        date_string = date_string.replace('/', '-')
        
        # Remove ordinal indicators
        date_string = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_string)
        
        # Normalize AM/PM
        date_string = re.sub(r'([ap])\.m\.', r'\1m', date_string, flags=re.IGNORECASE)
        
        return date_string

    def _remove_location_prefix(self, date_string):
        """Remove location prefixes like 'Napa *'"""
        if '*' in date_string:
            return date_string.split('*')[1].strip()
        return date_string

    def _split_multiple_dates(self, date_string):
        """Split multiple dates (e.g., 'January 1 and January 2')"""
        for separator in ['and', '&', ',']:
            if separator in date_string.lower():
                return [d.strip() for d in date_string.split(separator)]
        return None

    def _parse_date_range(self, date_string):
        """Parse a date range and return (start_date, end_date)"""
        for separator in self.range_separators:
            if separator in date_string:
                parts = date_string.split(separator, 1)
                if len(parts) == 2:
                    start, end = parts
                    
                    # Extract year from end date if present
                    year_match = re.search(r'\d{4}', end)
                    year = year_match.group(0) if year_match else None
                    
                    # If year found in end date, append it to start date if needed
                    if year and not re.search(r'\d{4}', start):
                        start = f"{start.strip()} {year}"
                    
                    # Regular range parsing
                    start_date = self._parse_single_date(start)
                    end_date = self._parse_single_date(end)
                    
                    if start_date and end_date:
                        return start_date, end_date
                    
        return None, None

    def _parse_single_date(self, date_string):
        """Parse a single date string"""
        logging.debug(f"Attempting to parse single date: {date_string}")
        
        # Try each date pattern
        for pattern in self.date_patterns:
            logging.debug(f"Trying pattern: {pattern['name']}")
            match = re.search(pattern['pattern'], date_string, re.IGNORECASE)
            
            if match:
                logging.debug(f"Pattern {pattern['name']} matched: {match.group(1)}")
                
                # Special handling for month ranges
                if pattern['name'] == 'month_range':
                    return self._handle_month_range(match)
                
                date_part = match.group(1)
                
                # Try each format for this pattern
                if pattern['format']:
                    for fmt in pattern['format']:
                        try:
                            parsed_date = datetime.strptime(date_part, fmt)
                            
                            # Handle implied year
                            if pattern['name'] in ['month_day', 'abbrev_month_day']:
                                parsed_date = self._add_implied_year(parsed_date)
                            
                            # Look for time
                            time_part = self._extract_time(date_string)
                            if time_part:
                                parsed_date = self._combine_date_and_time(parsed_date, time_part)
                                
                            logging.debug(f"Successfully parsed date '{date_string}' using {pattern['name']} format")
                            return parsed_date
                            
                        except ValueError:
                            continue
                            
        logging.error(f"Failed to parse date: {date_string}")
        return None

    def _handle_month_range(self, match):
        """Handle special case of month ranges"""
        try:
            start_month_day = match.group(1)
            year = match.group(3)
            return self._parse_single_date(f"{start_month_day}, {year}")
        except Exception as e:
            logging.error(f"Error handling month range: {e}")
            return None

    def _add_implied_year(self, parsed_date):
        """Add implied year based on current date"""
        current_date = datetime.now()
        year = current_date.year
        
        # If the date is in the past, assume next year
        if parsed_date.replace(year=year) < current_date:
            year += 1
            
        return parsed_date.replace(year=year)

    def _extract_time(self, date_string):
        """Extract time from date string"""
        for pattern in self.time_patterns:
            match = re.search(pattern['pattern'], date_string, re.IGNORECASE)
            if match:
                time_str = match.group(1)
                # Normalize periods in AM/PM
                time_str = re.sub(r'([ap])\.m\.', r'\1m', time_str, flags=re.IGNORECASE)
                # Remove any spaces before am/pm
                time_str = re.sub(r'\s*(am|pm)', r'\1', time_str, flags=re.IGNORECASE)
                
                for fmt in pattern['format']:
                    try:
                        return datetime.strptime(time_str.upper(), fmt)
                    except ValueError:
                        continue
        return None

    def _combine_date_and_time(self, date, time):
        """Combine date and time parts"""
        if time:
            return date.replace(hour=time.hour, minute=time.minute)
        return date

    def _validate_date(self, parsed_date):
        """Validate that parsed date is reasonable"""
        now = datetime.now()
        five_years = timedelta(days=365*5)
        
        if parsed_date < now - five_years or parsed_date > now + five_years:
            logging.warning(f"Date {parsed_date} is outside reasonable range")
            return False
        return True

    def debug_parse(self, date_string):
        """Debug method to show all parsing attempts"""
        results = []
        
        cleaned = self._clean_input(date_string)
        results.append(f"Cleaned input: {cleaned}")
        
        for pattern in self.date_patterns:
            match = re.search(pattern['pattern'], cleaned, re.IGNORECASE)
            if match:
                results.append(f"Pattern '{pattern['name']}' matched: {match.group(1)}")
                
        time_match = self._extract_time(cleaned)
        if time_match:
            results.append(f"Found time: {time_match.strftime('%I:%M %p')}")
            
        return "\n".join(results)