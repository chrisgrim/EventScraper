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
                        * {{
                            box-sizing: border-box;
                            margin: 0;
                            padding: 0;
                        }}

                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 1200px;
                            margin: 0 auto;
                            padding: 20px;
                        }}

                        h1 {{
                            text-align: center;
                            margin-bottom: 30px;
                            color: #2c3e50;
                        }}

                        h2 {{
                            margin-top: 40px;
                            margin-bottom: 20px;
                            color: #2c3e50;
                            border-bottom: 2px solid #3498db;
                            padding-bottom: 10px;
                        }}

                        [data-type="event-grid"] {{
                            display: grid;
                            grid-template-columns: repeat(4, 1fr);
                            gap: 20px;
                            margin-bottom: 30px;
                        }}

                        [data-type="event-card"] {{
                            display: flex;
                            flex-direction: column;
                            gap: 10px;
                            background: #fff;
                            border-radius: 8px;
                            overflow: hidden;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                        }}

                        [data-type="image-container"] {{
                            aspect-ratio: 3/4;
                            overflow: hidden;
                        }}

                        [data-type="image-container"] img {{
                            width: 100%;
                            height: 100%;
                            object-fit: cover;
                        }}

                        [data-type="title"] {{
                            font-weight: bold;
                            padding: 0 10px;
                        }}

                        [data-type="title"] a {{
                            color: #2c3e50;
                            text-decoration: none;
                        }}

                        [data-type="title"] a:hover {{
                            color: #3498db;
                        }}

                        [data-type="datetime"] {{
                            color: #666;
                            font-size: 0.9em;
                            padding: 0 10px;
                        }}

                        [data-type="description"] {{
                            font-size: 0.9em;
                            padding: 0 10px 10px;
                            overflow: hidden;
                            display: -webkit-box;
                            -webkit-line-clamp: 3;
                            -webkit-box-orient: vertical;
                        }}

                        @media (max-width: 1024px) {{
                            [data-type="event-grid"] {{
                                grid-template-columns: repeat(3, 1fr);
                            }}
                        }}

                        @media (max-width: 768px) {{
                            [data-type="event-grid"] {{
                                grid-template-columns: repeat(2, 1fr);
                            }}
                        }}

                        @media (max-width: 480px) {{
                            [data-type="event-grid"] {{
                                grid-template-columns: 1fr;
                            }}
                        }}
                    </style>
                </head>
                <body>
                    <h1>🎭 Upcoming Events</h1>
                    {message}
                </body>
            </html>
            """
            
            msg = MIMEText(html, 'html')
            msg['Subject'] = '🎪 Upcoming Events'
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