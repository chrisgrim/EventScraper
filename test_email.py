import os
import datetime
from notifications.email import EmailNotifier
import logging

logging.basicConfig(level=logging.INFO)

def test_email():
    notifier = EmailNotifier(
        smtp_server=os.getenv('SMTP_SERVER'),
        smtp_port=int(os.getenv('SMTP_PORT')),
        username=os.getenv('SMTP_USERNAME'),
        password=os.getenv('SMTP_PASSWORD'),
        recipient=os.getenv('EMAIL_RECIPIENT')
    )
    
    test_message = f"""
    This is a test email from the Event Monitor
    
    If you receive this, the email configuration is working correctly!
    
    Time: {datetime.datetime.now()}
    """
    
    notifier.from_address = "info@eagle.mxlogin.com"
    
    logging.info("Sending test email...")
    notifier.send(test_message)
    logging.info("Test complete!")

if __name__ == "__main__":
    test_email()
