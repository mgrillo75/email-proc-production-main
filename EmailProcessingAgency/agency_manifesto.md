# Email Processing Agency Manifesto

## Mission:
To automate the processing of incoming emails from an Outlook account, analyze the content, categorize the message, and generate summaries of the content. The integration of the Letta LLM memory framework will enhance memory management and contextual understanding, ensuring optimal performance and scalability.

## Goals:
- Automate the processing of emails to save time and improve accuracy.
- Categorize emails based on content and context for better organization.
- Generate concise summaries to provide quick insights into email content.
- Utilize a state of the art LLM memory framework to enhance all of the agents reasoning and decision making capabilities.

## Agency Structure:
1. **LeadAgent**: Oversees the entire operation, maintains the workflow among agents, and ensures the agency's goals are met.
2. **EmailProcessingAgent**: Processes all new incoming emails from the specified Outlook folders using win32com.
3. **EmailCategorizationAgent**: Categorize emails based on content and context for better organization using LLMs.
4. **SummaryGenerationAgent**: Creates a summary of the content in the body of a new email.
5. **LettaMemoryAgent**: Utilizes the Letta LLM memory framework to enhance memory management, refine contextual understanding, and improve decision-making.

## Communication Flows:
- The agency operates within the Agency Swarm framework, utilizing a collaborative swarm of AI agents with specific roles.
- Each agent functions autonomously yet collaborates with others to achieve the common goal of efficient email processing.
The framework supports customizable agent roles, efficient communication, and robust state management.
- The agency operates using a combination of specialized agents, each with distinct roles and capabilities.
- Agents collaborate to achieve the common goal of efficient email processing.
- The Letta framework is integrated to provide robust memory management, enabling agents to access and learn from historical data.

## Tools and APIs:
- **EmailProcessingAgent**: win32com.client for Outlook integration, custom monitoring tools
- **EmailCategorizationAgent**: Custom email parsing and categorization tools
- **SummaryGenerationAgent**: Advanced summarization through LLMs via APIs
- **LettaMemoryAgent**: Utilizes a wide range of predefined and custom functions from the Letta framework to provide Agents with human like memory capabilities.
- Memory management is centralized through the LettaMemoryAgent, simplifying architecture and ensuring consistency.
- Agents interact with the LettaMemoryAgent to store and retrieve data, enhancing their capabilities with advanced memory operations.
- The agency framework supports scalability and adaptability, allowing for future enhancements and integrations.


