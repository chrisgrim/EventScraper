from abc import ABC, abstractmethod

class BaseAnalyzer(ABC):
    """Base class for all event analyzers"""
    
    def __init__(self, config=None):
        self.config = config or {}
    
    @abstractmethod
    async def analyze(self, events):
        """Analyze events and return recommendations"""
        pass
