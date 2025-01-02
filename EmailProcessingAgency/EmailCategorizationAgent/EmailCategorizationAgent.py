from agency_swarm.agents import Agent


class EmailCategorizationAgent(Agent):
    def __init__(self):
        super().__init__(
            name="EmailCategorizationAgent",
            description="The EmailCategorizationAgent categorizes emails using specified tools and interacts with the LettaMemoryAgent to access historical data for improved categorization.",
            instructions="./instructions.md",
            files_folder="./files",
            schemas_folder="./schemas",
            tools=[],
            tools_folder="./tools",
        )
        
    def response_validator(self, message):
        return message
