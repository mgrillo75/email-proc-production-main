import os
import time
import win32com.client
from datetime import datetime
import pytz
import re
from agency_swarm.tools import BaseTool
from pydantic import Field
import pythoncom
import logging

class OutlookFolderMonitor(BaseTool):
    """
    This tool monitors specified Outlook folders for new emails using the Outlook client.
    It continuously checks for new unread emails and handles any exceptions to ensure uninterrupted monitoring.
    """
    check_interval: int = Field(
        60, description="The interval in seconds between checks for new emails."
    )

    def clean_body(self, body):
        """ Clean the email body content and extract only the latest message. """
        # Split by common email separator patterns
        separators = [
            "\r\n\r\nFrom:",
            "\n\nFrom:",
            "________________________________",
            "From:",
            "Sent:",
            ">",  # Quote marker in replies
        ]
        
        # Get the first part (latest message) before any of these separators
        cleaned_body = body
        for separator in separators:
            parts = cleaned_body.split(separator, 1)
            cleaned_body = parts[0]
        
        # Clean up the extracted message
        cleaned_body = re.sub(r'\n+', '\n', cleaned_body)
        cleaned_body = '\n'.join(line.strip() for line in cleaned_body.split('\n'))
        cleaned_body = cleaned_body.strip()
        
        return cleaned_body

    def monitor_outlook_folders(self):
        """ Monitor specified Outlook folders for new unread emails. """
        print("Initializing COM library...")
        pythoncom.CoInitialize()
        outlook = None
        try:
            print("Connecting to Outlook...")
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            print("Accessing account folder: miguel.grillo@awc-inc.com")
            account_folder = outlook.Folders("miguel.grillo@awc-inc.com")
            print("Accessing 'Customers' folder...")
            customers_folder = account_folder.Folders("Customers")
            print("Accessing default Inbox folder...")
            inbox = outlook.GetDefaultFolder(6)
            print("Accessing 'AWC' folder...")
            AWC = account_folder.Folders("AWC")

            customer_folders = (
                "Test",
            )
            folders = {}
            print("Setting up folders to monitor:")
            for folder_name in customer_folders:
                if folder_name == "Inbox" or folder_name == "AWC":
                    print(f" - Adding primary folder: {folder_name}")
                    folders[folder_name] = inbox.Items if folder_name == "Inbox" else AWC.Items
                else:
                    print(f" - Adding customer folder: {folder_name}")
                    folders[folder_name] = customers_folder.Folders[folder_name].Items

            print("Setting timezone to CST (America/Chicago)...")
            cst_tz = pytz.timezone('America/Chicago')
            now = datetime.now(cst_tz).replace(tzinfo=None)
            filtered_messages = []

            print("Fetching new unread emails from all monitored folders...")
            for folder_name, messages in folders.items():
                print(f"Checking folder: {folder_name}")
                message = messages.GetFirst()
                if not message:
                    print(f" - No messages found in folder: {folder_name}")
                while message:
                    try:
                        if message.Class == 43 and message.UnRead:
                            print(f" - Processing new email with Subject: '{message.Subject}' in folder: {folder_name}")
                            
                            # Extract the body content
                            email_body = message.Body if hasattr(message, 'Body') else 'No Body Content'
                            # Clean and get only the latest message
                            cleaned_body = self.clean_body(email_body)
                            
                            email_data = {
                                "subject": message.Subject if hasattr(message, 'Subject') else 'No Subject',
                                "body": cleaned_body,  # Use the cleaned body with only latest message
                                "date": message.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S") if hasattr(message, 'ReceivedTime') else 'No Date',
                                "from": message.SenderEmailAddress if hasattr(message, 'SenderEmailAddress') else 'No Sender',
                                "to": message.To if hasattr(message, 'To') else 'No Recipient',
                                "conversation_id": message.ConversationID if hasattr(message, 'ConversationID') else None
                            }
                            filtered_messages.append(email_data)
                            
                            print(f"   - Marking email as read.")
                            message.UnRead = False
                    except Exception as e:
                        print(f"   Error processing message in folder '{folder_name}': {e}")
                    message = messages.GetNext()
            print(f"Total new unread emails found: {len(filtered_messages)}")
            return filtered_messages
        except Exception as e:
            print(f"Error in monitor_outlook_folders: {e}")

    def run(self):
        """ Run once to check the specified Outlook folders for new emails. """
        print("Checking all specified folders for new unread emails...")
        
        try:
            print("Checking for new unread emails...")
            emails = self.monitor_outlook_folders()
            processed_results = []
            
            if emails:
                print(f"Found {len(emails)} new unread email(s).")
                for i, email in enumerate(emails, 1):
                    print(f"Processing email {i}...")
                    try:
                        email_content = {
                            "subject": email['subject'],
                            "body": email['body'],
                            "from": email['from'],
                            "to": email['to'],
                            "date": email['date'],
                            "conversation_id": email['conversation_id']
                        }
                        
                        # Add to processed results
                        processed_results.append(email_content)
                        print(f" - Email {i} processed successfully.")
                    except Exception as e:
                        print(f"   Error processing email {i}: {e}")
                
                return processed_results
            else:
                print("No new unread emails found.")
                return []
                
        except Exception as e:
            print(f"An error occurred during monitoring: {e}")
            return []
