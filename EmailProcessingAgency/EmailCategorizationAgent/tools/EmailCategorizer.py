from agency_swarm.tools import BaseTool
from pydantic import Field, BaseModel
import anthropic
import os
import logging
from typing import Dict

class EmailInfo(BaseModel):
     sender: str
     subject: str
     body: str
     attachments: str

class EmailCategorizer(BaseTool):
     """
     This tool assigns priority levels and categories to emails based on sender importance, keywords, and client relevance.
     It analyzes parsed email data to determine the appropriate category and priority for each email.
     """
     email_info: EmailInfo = Field(
         ..., description="The parsed email data containing sender, subject, body, and attachments."
     )

     def run(self) -> str:
         """
         Assign priority and category to the email based on LLM analysis.
         """
         logging.info("=== Starting Email Categorization ===")
         
         try:

             # Call the Anthropic API to generate the summary
             client = anthropic.Anthropic(
                api_key="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"
             )

             classification_prompt = (
                 "Classify the following email based on these criteria:\n"
                 "1. Category: Does Email contain a specific new request/task/action item/etc., provide new information, follow up on a previous task/request/etc., or content is other than the above?\n"
                 "2. Priority: What is the priority level of the email message body Low, Medium, High.?\n\n"
                 f"Email content:\nSender: {self.email_info.sender}\nSubject: {self.email_info.subject}\nBody: {self.email_info.body}\n\n"
                 "Respond with only a JSON object with the following two fields:\n"
                 "For Category: respond with only one of these phrases: 'Action Item', 'New Information', 'Follow Up', or 'Other'.\n"
                 "For Priority: respond with only one of these phrases: 'Low', 'Medium', 'High'.\n"
             )

             # Prepare the message for categorization
             response = client.messages.create(
                 model="claude-3-5-sonnet-20241022",
                 max_tokens=8192,
                 temperature=0,
                 #system="You are an AI agent categorizing email content. Analyze the email and determine its priority (High/Medium/Low) and category (Action Item/Knowledge Sharing/General). Return only a JSON object with priority and category fields.",
                 system="You are an AI agent categorizing email content. Analyze the email and determine its Category and Priority level. Return only a JSON object with Category and Priority fields.",
                 messages=[
                     {
                         "role": "user",
                         #"content": f"Categorize this email:\n\nSender: {self.email_info.sender}\nSubject: {self.email_info.subject}\nBody: {self.email_info.body}"
                         "content": classification_prompt
                     }
                 ]
             )

             # Assuming the response object has a 'content' attribute or similar
             result = response.content[0].text  # Adjust this line based on actual response structure
             logging.info(f"Categorization result: {result}")
             return result

         except Exception as e:
             logging.error(f"Error categorizing email: {str(e)}")
             return f"Error categorizing email: {str(e)}"

if __name__ == "__main__":
    # Example usage
    email_info = EmailInfo(
        sender="kathrin.starschich@siemens.com",
        subject="RE: HMH prioritization",
        body="Please prioritize the HMH project for this quarter.",
        attachments=""
    )
    categorizer = EmailCategorizer(email_info=email_info)
    result = categorizer.run()
    print(result)
