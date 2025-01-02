
# Agency Swarm Framework

I developed my own framework called Agency Swarm.

In this framework, there isn't a single hard-coded prompt.

It's easily customizable with uniform communication flows, and it is extremely reliable in production because it provides automatic type checking and validation for all tools with the instructor library.

It is the thi

## Assistants API for AI Agent Development

nnest possible wrapper around OpenAI's Assistance API, meaning that you have full control over all your agents.

So whether you add a manager agent, define goals, processes, or not, whether you create a sequential or hierarchical flow or even combine both with a communication tree that is 50 levels in depth, I don't care, it is still going to work.

Your agents will determine who to communicate with next, based on their own descriptions and nothing else.

But, you are probably wondering, why assistants api for ai agent d

## Understanding Core Entities: Agents, Tools, and Agencies

evelopment? Well, that's a good question because if you look at all the previous OpenAI endpoints, you'll find the Assistants API isn't significantly different.

However, it was a game-changer for me as agent developer.

And the reason for this is state management.

You see, with the Assistants' API, you can attach instructions, knowledge, and actions directly to each new agent.

This not only allows you to separate various responsibilities, but also to scale your system seamlessly without having to worrying about any underlying data management or about your agents confusing each others tools like in other frameworks.

Agent state management is the primary reason why Agency Swarm is fully based on the OpenAI Assistants API.

To get started creating your agent swarms using my framework you need to understand 3 essential entities which are Agents, Tools and Agencies.

Agents, are essential

## Tools and Validation with Instructor

ly wrappers around assistants in Assistants API.

They include numerous methods that simplify the agent creation process.

For instance, instead of manually uploading all your files and adding their IDs when creating an assistant, you can just specify the folder path.

The system will automatically attach all files from that folder to your assistant.

It also stores all your agent settings in a settings.json file.

Therefore, if your agent's configuration changes, the system will automatically update your existing assistant on OpenAI the next time you run it, rather than creating a new one.

The most commonly used parameters when creating an agent are name, description, instructions, model, and tools.

These are all self-explanatory.

There are no preset templates for goals, processes, backstories, etc., so you simply include them all in the instructions.

Additional parame

## Creating Communication Flows in Agencies

ters include files_folder, schemas_folder, and tools_folder.

As I said, all files from your files folder will be automatically indexed and uploaded to OpenAI.

All tools from your tools folder will be attached to an assistant as well, and all openapi schemas from your schemas folder will automatically be converted into tools, allowing your agents to easily call third party apis.

Additional properties api_params and api_headers are also available if your API requires authentication.

However, I do recommend creating all your tools from scratch using Instructor, as it gives you more control.

I previously posted a detailed tutorial on Instructor, which includes a brief conversation with its creator, Jason Liu.

Check it out if you're interested.

In essence, Instructor allows you to integrate a data validation library, Pydantic, with function calls.

This ensures that all agent inputs ma

## Running Your Agency

ke sense before any actions are executed, minimizing production errors.

For instance, if you have a number division tool, you can verify that the divisor is not zero.

If it is, the agent will see the error and automatically correct itself before executing any logic.

To begin creating tools in Agency Swarm with Instructor, create a class that extends a base tool, add your class properties, and implement the run method.

Remember, the agent uses the docstring and all field descriptions to understand when and how to use your tool.

For our number division tool, the docstring should state that this tool divides two numbers and describe the pa

## Example: Creating a Social Media Marketing Agency

rameters accordingly.

Next, define your execution logic within the run method.

You can access all defined fields through the self object.

To make some fields optional, use the Optional type from Pydantic.

To define available values for your agent, use a literal or enumerator type.

There are also many tricks you can use.

For instance, you can add a chain_of_thought parameter inside the tool to save on token costs and latency, instead of using a chain of thought prompt globally.

To add your validation logic, use field or model validators from Pydantic.

In this division tool example, it makes sense to add a field validator that checks if the divisor is not zero, returning an error if it is.

Because tools are arguably the most important part of any AI Agent based system, I created this custom GPT to help you get started faster.

For example, if I need a tool that searches the web with Serp API, it instantly generates a BaseTool with parameters like query as a string and num_results as an integer, including all relevant descriptions.

You can find the link to this tool on our Discord.

The final component of the Agency Swarm framework is the Agenc

## Adjusting Communication Flows

y itself, which is essentially a collection of agents that can communicate with one another.

When initializing your agency, you add an Agency chart that establishes communication flows between your agents.

In contrast to other frameworks, communication flows in Agency Swarm are uniform, meaning they can be defined in any way you want.

If you place any agents in the top-level list inside the agency chart, these agents can communicate with the user.

If you add agents together inside a second-level list, these agents can communicate with one another.

To create a basic sequential flow, add a CEO agent to the top-level list, then create a second-level list with a CEO, developer, and virtual assistant.

In this flow, the user communicates with the CEO, who then communicates with the developer and the virtual assistant.

If you prefer a hierarchical flow, place the agents in two separate second-level lists with the CEO.

Remember, communication flows are directional.

In the previous example, the CEO can initiate communication with the developer, who can respond, but the developer cannot initiate communication with the CEO, much like in real organizations.

If you still want the developer to assign tasks to the CEO, simply add another list with the developer first and the CEO second.

I always recommend starting with as few agents as possible and adding more only once they are working as expected.

Advanced parameters inside the Agency class like async mode, threads_callbacks, and settings_callbacks are useful when deploying your swarms on various backends.

Be sure to check our documentation for more information.

When it comes to running your agency, you have 3 options: the Gradio interface with the demo_gradio command, the terminal version with the run_demo method, or get_completion, which is similar to previous chat completions APIs.

Now, let's create our own social media marketing agency together to demonstrate the entire process from start to finish.

Alright, for those who are new here, please install Agency Swarm using the command 'pip install agency swarm.' To get started quickly, I usually run the 'agency swarm genesis' command.

This will activate the Genesis agency, which will create all your agents for you.

It doesn't get everything right just yet, but it does speed up the process significantly.

In my prompt, I'm going to specify that I need a Facebook marketing agency that generates ad copy, creates images with Dalle 3, and posts them on Facebook.

As you can see, we now have our initial agency structure with three agents: the ad copy agent, image creator agent, and Facebook manager agent.

I really like how the genesis agency has divided these responsibilities among three different agent roles.

However, I'd like to adjust the communication flows a bit and adopt a sequential flow, so I will instruct the genesis CEO accordingly.

Now we have a sequential agency structure with three communication levels.

We can tell it to proceed with the creation of the agents.

This process takes some time, so I'll skip this part and return when we're ready to fine-tune our agents.

After all our agents have been created, you can see that the CEO tells me that I can run this agency with the python agency.py command.

All the folders for my agents and tools are displayed on the left.

The next step is to test and fine-tune all these tools.

We'll start with the image generator agent.

The Genesis Agency has created one tool for this agent called ImageGenerator.

It's impressive how close this tool is to what I planned to implement myself.

It uses OpenAI to generate an image with a simple prompt, taking ad_copy, theme, and specific requirements and inserting them into a prompt template.

Yes, AI has learned to prompt itself.

However, there's an issue: it uses an outdated OpenAI package version with the Da Vinci Codex model, which is designed for code generation.

Let's fix this now together.

First, I'll load a new OpenAI client with a convenience method from Agency Swarm Util.

I'll also increase the timeout because image generation can take some time.

After that, I'll adjust the API call to use the new Dalle 3 model, and then set the timeout back to the default.

There's one more thing we have to do - we have to ensure that other agents can use this image when posting the ad.

So, I'm going to create a new 'save image' method that will save this image locally.

But here is the kicker - I don't want my agents to pass this image path to each other because any hallucinations could cause issues.

Instead, I'll save this path to a shared state.

Essentially, shared state allows you to share certain variables across all agents in any tool.

Instead of having the agent manually pass the image path to another agent, you can save it in one tool and access it in another.

You can also use it to perform validation logic across various agents, which I'll show you soon.

Now we are ready to test this tool.

You can do this by adding a simple 'if name equals main' statement at the end, then initializing the tool with some example parameters.

Then you can print the result of the run method.

Don't forget to load the environment with your OpenAI key by adding the 'load_dotenv' method at the top.

As you can see, we have an image generated and saved locally, as expected.

This means we can now proceed with adjusting the next tool, the AdCopyGenerator tool within the ad copy agent.

This tool is also very similar to my personal design.

I'll adjust the prompt a bit and save the results into the shared state.

Moving on to the Facebook Manager agent, Genesis Agency created two tools for us: the Ad Performance Monitor tool and the Ad Scheduler and Poster tool.

While these tools are quite close, creating an ad on Facebook requires a few more steps.

Specifically, we need to first create a campaign and an ad set before we can post the ad.

I will use a tool creator custom gpt to request two additional tools, 'Ad Campaign Starter', and 'Ad Set Creator'.

To run these tools, we first need to install the Facebook Business SDK, which you can do with this PIP command.

Next, we need to create our Facebook app.

Go to the Facebook developer website, click "Create App", select "Other" for the use case, then "Business" for the app type.

Add your app name and click "Create App".

Then click on "Add product" and add "marketing API".

Go to "App settings", copy your App ID, App secret, and insert them into the environment file.

Now we have to get our access token by visiting the Facebook API Explorer website and adding the appropriate permissions.

After that, copy it and put it into the env file.

Working with the Facebook API can be challenging as it's known to be one of the more complex APIs out there.

I won't delve into the details of how I fine-tuned these tools.

The process is the same: adjust, test, and repeat until they work as expected.

As you can see in the AdCreator tool, we're actually utilizing the ad copy, ad headline, and image path from the shared state that we saved earlier.

I have also included a model validator that checks the presence of all these necessary parameters.

If one of the parameters is not defined, the system throws a value error and instructs the agent on which tool needs to be used first.

This approach significantly enhances the reliability of the entire system, as it ensures that the Facebook ad manager agent cannot post any ads until all the required steps like image generation have been completed.

After successfully testing all our tools, the final step is to refine the instructions.

It is a good practice to include how specifically your agents should communicate with each other.

I would also recommend specifying an exact step-by-step process for them to follow.

Lastly, I decided to make a few adjustments in our communication flows.

I'd like to establish a direct line of communication with our Facebook Manager agent, so I'll include it in the top-level list.

Also, I'll allow our CEO agent to communicate directly with both the Facebook Manager and the Image Generator agents.

Now that we've made these adjustments, we're ready to run our agency.

It is as simple as running the python.agency.py command and opening the provided Gradio interface link in your browser.

Let's see how it works.

I'll kindly ask for an advertisement to be created for my AI development agency, Arsen AI.

The CEO then instructs the ad copy agent, which promptly provides a clear headline and ad copy for my agency, stating, "Revolutionize your business with AI." Next, the CEO commands the image generator agent to create an image for the ad copy, resulting in a futuristic visual for our campaign.

Finally, the CEO directs the FacebookManager Agent to commence the campaign using the campaign starter tool.

It then creates an ad set and executes the ad creation function, posting this ad on Facebook.

You can now see this newly generated Facebook ad, complete with ad copy, headline, and image, live on my Facebook account.

Impressive, right? But what if you want to analyze your campaign's performance? You can do this by directly messaging the Facebook Manager agent, as it was included in the top-level list.

It uses the AdPerformanceMonitor tool and informs me that there is currently no data as it takes some time for an ad to reach its audience.


