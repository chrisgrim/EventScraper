from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
import logging

class CalendarIntegration:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']
        self.creds = self._get_credentials()
        self.service = build('calendar', 'v3', credentials=self.creds) if self.creds else None

    def _get_credentials(self):
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        return creds

    def add_event(self, event_details):
        if not self.service:
            logging.error("Calendar service not initialized")
            return False
            
        try:
            event = self.service.events().insert(
                calendarId='primary',
                body=event_details
            ).execute()
            return True
        except Exception as e:
            logging.error(f"Failed to add calendar event: {e}")
            return False