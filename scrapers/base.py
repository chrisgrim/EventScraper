from abc import ABC, abstractmethod
import logging

class BaseScraper(ABC):
    """Base class for all event scrapers"""
    
    def __init__(self, config=None):
        self.config = config or {}
        
    @abstractmethod
    def scrape(self):
        """Scrape events from the source"""
        pass
    
    def validate_event(self, event):
        """Validate required event fields"""
        required_fields = ['title', 'datetime']
        return all(event.get(field) for field in required_fields)
