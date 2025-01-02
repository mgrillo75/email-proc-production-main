from agency_swarm import Agency
from SummaryGenerationAgent import SummaryGenerationAgent
from EmailCategorizationAgent import EmailCategorizationAgent
from EmailProcessingAgent import EmailProcessingAgent
from LeadAgent import LeadAgent
from agency_swarm import set_openai_key
import logging

# Set the API key first
set_openai_key("sk-proj-X6rP4ce4qzDkfhkOZGw3T3BlbkFJNWGRQ7XGk7vnykY9WIcz")

# Then create the agents
lead_agent = LeadAgent()
email_processing_agent = EmailProcessingAgent()
email_categorization_agent = EmailCategorizationAgent()
summary_generation_agent = SummaryGenerationAgent()

agency = Agency([lead_agent,
                 [lead_agent, email_processing_agent],
                 [lead_agent, summary_generation_agent],
                 [lead_agent, email_categorization_agent],
                 #[lead_agent, letta_memory_agent],
                 [email_processing_agent, email_categorization_agent],
                 [email_processing_agent, summary_generation_agent]],
                 #[email_processing_agent, letta_memory_agent],
                 #[summary_generation_agent, letta_memory_agent],
                 #[email_categorization_agent, letta_memory_agent]],
                shared_instructions='./agency_manifesto.md',
                max_prompt_tokens=25000,  # default tokens in conversation for all agents
                temperature=0.3,  # default temperature for all agents
                )

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        agency.demo_gradio()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
