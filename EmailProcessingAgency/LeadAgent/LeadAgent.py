from agency_swarm.agents import Agent


class LeadAgent(Agent):
    def __init__(self):
        super().__init__(
            name="LeadAgent",
            description="Oversees and coordinates tasks among all agents to ensure cohesive operation.  Reports final output to the user.",
            instructions="./instructions.md",
            files_folder="./files",
            schemas_folder="./schemas",
            tools=[],
            tools_folder="./tools",
        )
        
    def response_validator(self, message):
        return message
