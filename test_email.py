#!/usr/bin/env python3
"""
Email Test Utility for Events Scraper

This script provides a simple way to test the email notification functionality
without running the full application. It's useful for:

1. Verifying SMTP server connection
2. Testing email credentials
3. Confirming email delivery to the recipient
4. Troubleshooting email configuration issues

Usage:
    python test_email.py

Environment Variables Required:
    SMTP_SERVER - SMTP server address
    SMTP_PORT - SMTP server port
    SMTP_USERNAME - SMTP username
    SMTP_PASSWORD - SMTP password
    EMAIL_RECIPIENT - Email recipient address
"""

import os
import datetime
from notifications.email import EmailNotifier
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_email():
    """
    Send a test email using the configured SMTP settings.
    
    This function uses the same EmailNotifier class as the main application,
    ensuring that successful tests will translate to successful operation
    in the main application.
    """
    # Verify environment variables
    required_vars = ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME', 
                     'SMTP_PASSWORD', 'EMAIL_RECIPIENT']
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file or environment")
        return
    
    try:
        # Create email notifier
        notifier = EmailNotifier(
            smtp_server=os.getenv('SMTP_SERVER'),
            smtp_port=int(os.getenv('SMTP_PORT')),
            username=os.getenv('SMTP_USERNAME'),
            password=os.getenv('SMTP_PASSWORD'),
            recipient=os.getenv('EMAIL_RECIPIENT')
        )
        
        # Set a recognizable from address
        notifier.from_address = "events-scraper@test.com"
        
        # Create test message
        test_message = f"""
        <html>
        <body>
            <h2>Events Scraper - Email Test</h2>
            <p>If you receive this, the email configuration is working correctly!</p>
            <p><strong>Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>This is a test message from the Events Scraper application.</p>
        </body>
        </html>
        """
        
        # Send test email
        logger.info(f"Sending test email to {os.getenv('EMAIL_RECIPIENT')}...")
        notifier.send(test_message)
        logger.info("✅ Test email sent successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to send test email: {e}")
        logger.error("Please check your SMTP configuration")

if __name__ == "__main__":
    test_email()
