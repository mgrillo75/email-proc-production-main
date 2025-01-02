from agency_swarm.tools import BaseTool
from pydantic import Field
from typing import Dict, Optional
import win32com.client
import os
from datetime import datetime
import pytz

class EmailProcessor(BaseTool):
    """
    Tool for processing emails from Outlook
    """
    folder_name: Optional[str] = Field(
        default="Inbox",
        description="The Outlook folder to process emails from"
    )

    def run(self) -> Dict:
        """
        Process emails from the specified Outlook folder
        """
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            
            # Get the folder
            inbox = namespace.GetDefaultFolder(6)  # 6 is the index for inbox
            if self.folder_name != "Inbox":
                inbox = inbox.Folders[self.folder_name]
            
            # Get unread emails
            messages = inbox.Items
            messages.Sort("[ReceivedTime]", True)
            
            for message in messages:
                if message.UnRead:
                    email_data = {
                        "sender": message.SenderEmailAddress,
                        "subject": message.Subject,
                        "body": message.Body,
                        "received_time": message.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"),
                        "attachments": [att.FileName for att in message.Attachments],
                        "raw_email": f"From: {message.SenderEmailAddress}\nSubject: {message.Subject}\nDate: {message.ReceivedTime}\n\n{message.Body}"
                    }
                    message.UnRead = False
                    return email_data
                    
            return {"message": "No new unread emails found"}
            
        except Exception as e:
            return {"error": f"Error processing email: {str(e)}"}

if __name__ == "__main__":
    processor = EmailProcessor()
    result = processor.run()
    print(result)