from agency_swarm.agents import Agent

class EmailProcessingAgent(Agent):
    def __init__(self):
        super().__init__(
            name="EmailProcessingAgent",
            description="The EmailProcessingAgent is responsible for processing incoming emails efficiently from an Outlook account using the win32com.client library to access and process emails. Also responsible for integrating with the LettaMemoryAgent to store processed email content",
            instructions="./instructions.md",
            files_folder="./files",
            schemas_folder="./schemas",
            tools=[],
            tools_folder="./tools",
        )
        
    def response_validator(self, message):
        return message