from .base import NotificationHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

class EmailNotifier(NotificationHandler):
    def __init__(self, smtp_server, smtp_port, username, password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient
        
    def send(self, message):
        """Send email notification"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Event Updates'
            msg['From'] = self.username
            msg['To'] = self.recipient
            
            logging.info("Preparing to send message...")
            
            # Add both plain text and HTML versions
            text_part = MIMEText(message, 'plain')
            html_part = MIMEText(message, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            logging.info("Message parts attached successfully")
            
            # More robust SMTP connection handling
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)  # Increased timeout
            try:
                logging.info("Connecting to SMTP server...")
                server.ehlo()
                server.starttls()
                server.ehlo()
                logging.info("Starting TLS...")
                server.login(self.username, self.password)
                logging.info("Logged in successfully...")
                server.send_message(msg)
                logging.info("Message sent successfully")
            finally:
                server.quit()
                
        except smtplib.SMTPServerDisconnected as e:
            logging.error(f"SMTP Server disconnected: {e}")
            logging.error("Try checking your network connection or SMTP server settings")
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP Authentication failed: {e}")
            logging.error("Check your username and password")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            logging.error(f"Error type: {type(e).__name__}")