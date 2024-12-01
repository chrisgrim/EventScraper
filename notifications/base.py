from abc import ABC, abstractmethod

class NotificationHandler(ABC):
    @abstractmethod
    def send(self, message):
        pass