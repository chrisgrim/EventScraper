from .base import NotificationHandler
import smtplib
from email.mime.text import MIMEText
import logging

class EmailNotifier(NotificationHandler):
    def __init__(self, smtp_server, smtp_port, username, password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient
        
    def send(self, message):
        try:
            html = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .event {{ 
                            margin: 20px 0;
                            padding: 15px;
                            border-left: 4px solid #4CAF50;
                            background-color: #f9f9f9;
                        }}
                        .score {{ 
                            font-weight: bold;
                            color: #4CAF50;
                        }}
                        .title {{ 
                            font-size: 18px;
                            color: #2196F3;
                        }}
                        .datetime {{ 
                            color: #666;
                            font-style: italic;
                        }}
                        .image {{
                            margin: 10px 0;
                            max-width: 100%;
                        }}
                        .image img {{
                            max-width: 300px;
                            height: auto;
                            border-radius: 8px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        }}
                        .explanation {{ 
                            margin-top: 10px;
                            color: #555;
                        }}
                    </style>
                </head>
                <body>
                    <h2>🎭 Petaluma Event Recommendations</h2>
                    {message}
                </body>
            </html>
            """
            
            msg = MIMEText(html, 'html')
            msg['Subject'] = '🎪 Petaluma Event Recommendations'
            msg['From'] = self.username
            msg['To'] = self.recipient
            
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                logging.info("Connecting to SMTP server...")
                server.login(self.username, self.password)
                logging.info("Logged in successfully, sending message...")
                server.send_message(msg)
                logging.info("Message sent successfully")
                
        except Exception as e:
            logging.error(f"Email notification failed: {e}")
            logging.error(f"Error type: {type(e).__name__}")
            logging.error(f"Error details: {str(e)}")