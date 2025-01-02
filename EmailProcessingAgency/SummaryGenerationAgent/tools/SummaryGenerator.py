from agency_swarm.tools import BaseTool
from pydantic import Field
import anthropic

class SummaryGenerator(BaseTool):
    """
    Tool for generating a concise and actionable summary of an email.
    It processes email body content, analyzes it for actionable insights, and returns a summary
    to aid in efficient review and decision-making.
    """
    body_content: str = Field(
        ..., description="The main content of the email body, excluding headers or signatures."
    )

    def run(self):
        """
        Generates a summary of the provided email content by interacting with the Anthropic API.
        """
        try:
            # Call the Anthropic API to generate the summary
            client = anthropic.Anthropic(
                api_key="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"
            )
            
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0,
                system="You are an AI agent summarizing email content. Provide a comprehensive yet concise summary based on actionable insights and efficient information for review and decision-making.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this email:\n\n{self.body_content}"
                    }
                ]
            )

            return message.content[0].text

        except Exception as e:
            return f"Error generating summary: {str(e)}"
