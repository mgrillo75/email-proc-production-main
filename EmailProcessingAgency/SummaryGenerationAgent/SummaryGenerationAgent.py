from agency_swarm.agents import Agent


class SummaryGenerationAgent(Agent):
    def __init__(self):
        super().__init__(
            name="SummaryGenerationAgent",
            description="Generates comprehensive summaries of processed emails that include actionable insights when applicable, and also continually interacts with the LettaMemoryAgent to provide new, or retrieve summaries of past emails.",
            instructions="./instructions.md",
            files_folder="./files",
            schemas_folder="./schemas",
            tools=[],
            tools_folder="./tools",
        )
        
    def response_validator(self, message):
        return message
