from agency_swarm.tools import BaseTool
from pydantic import Field
from typing import Dict
import email
from email import policy
from email.parser import Parser

class EmailParser(BaseTool):
    """
    Tool for parsing raw email data into structured format
    """
    raw_email: str = Field(
        ..., 
        description="Raw email data to be parsed"
    )

    def run(self) -> Dict:
        """
        Parse the raw email data into a structured format
        """
        try:
            # Split the raw email into components
            lines = self.raw_email.split('\n')
            parsed_data = {
                "sender": "",
                "subject": "",
                "date": "",
                "body": "",
                "attachments": []
            }
            
            # Parse header information
            for line in lines:
                if line.startswith("From: "):
                    parsed_data["sender"] = line.replace("From: ", "").strip()
                elif line.startswith("Subject: "):
                    parsed_data["subject"] = line.replace("Subject: ", "").strip()
                elif line.startswith("Date: ") or line.startswith("Sent: "):
                    parsed_data["date"] = line.replace("Date: ", "").replace("Sent: ", "").strip()
                    
            # Get the body (everything after the headers)
            body_start = self.raw_email.find("\n\n")
            if body_start != -1:
                parsed_data["body"] = self.raw_email[body_start:].strip()
            
            return parsed_data
            
        except Exception as e:
            return {"error": f"Error parsing email: {str(e)}"}

if __name__ == "__main__":
    pass # # Test the parser
    # test_email = """From: Paula Moreau
    # Sent: Friday, September 13, 2024 3:00 PM
    # To: Miguel Grillo; Anthony Ubaka
    # Cc: Tracy Spafford; Alan Ivanyisky; Tomeka Thompson; Emma Mulcrone
    # Subject: RE: Reference : Invoice # 3167098 for $747,485.83
    #
    # Miquel
    # Thank you for the update. Dynamis has definitely been holding to their commitments once we get them the correct
    # information for invoicing.
    # Our understanding is that this latest payment round was held up because the invoices did not have the POs.
    # What Anthony is asking is that we set up a meeting to outline the processes you have defined for this customer.
    # Review through the issues that have occurred and determine if the process is complete or needs to be amended to
    # make sure we get invoicing right on the first issuance.
    # We all recognize the amount of e$ort and time you have put into to this and greatly appreciate it. Our concern is
    # that you are having to revisit invoices multiple times and our hope are that if we review through your processes and
    # ultimately understand the customer requirements we can make this easier for you and your team in the future.
    # Anthony will be reaching out to you to schedule a meeting to review through the process documentation and to
    # hopefully provide some meaningful feedback to update and make the process smoother.
    # Thanks
    # Paula
    # Paula Moreau
    # Chief Financial Officer
    # office
    # (225) 300-9439"""
    # 
    # parser = EmailParser(raw_email=test_email)
    # result = parser.run()
    # print(result)