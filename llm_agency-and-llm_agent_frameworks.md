## File Contents

### .cursorrules
```
# AI Agent Creator Instructions for Agency Swarm Framework
```

### .github/workflows/close-issues.yml
```
name: Close inactive issues
```
# ... (rest of the code remains unchanged)

    def demo_gradio(self, height=450, dark_mode=True, **kwargs):
        """
        Launches a Gradio-based demo interface for the agency chatbot.

        Parameters:
            height (int, optional): The height of the chatbot widget in the Gradio interface. Default is 600.
            dark_mode (bool, optional): Flag to determine if the interface should be displayed in dark mode. Default is True.
            **kwargs: Additional keyword arguments to be passed to the Gradio interface.
        This method sets up and runs a Gradio interface, allowing users to interact with the agency's chatbot. It includes a text input for the user's messages and a chatbot interface for displaying the conversation. The method handles user input and chatbot responses, updating the interface dynamically.
        """

        try:
            import gradio as gr
        except ImportError:
            raise Exception("Please install gradio: pip install gradio")

        js = """function () {
          gradioURL = window.location.href
          if (!gradioURL.endsWith('?__theme={theme}')) {
            window.location.replace(gradioURL + '?__theme={theme}');
          }
        }"""

        if dark_mode:
            js = js.replace("{theme}", "dark")
        else:
            js = js.replace("{theme}", "light")

        attachments = []
        images = []
        message_file_names = None
        uploading_files = False
        recipient_agent_names = [agent.name for agent in self.main_recipients]
        recipient_agent = self.main_recipients[0]

        with gr.Blocks(js=js) as demo:
            chatbot_queue = queue.Queue()
            chatbot = gr.Chatbot(height=height)
            with gr.Row():
                with gr.Column(scale=9):
                    dropdown = gr.Dropdown(label="Recipient Agent", choices=recipient_agent_names,
                                           value=recipient_agent.name)
                    msg = gr.Textbox(label="Your Message", lines=4)
                with gr.Column(scale=1):
                    file_upload = gr.Files(label="OpenAI Files", type="filepath")
            button = gr.Button(value="Send", variant="primary")

            def handle_dropdown_change(selected_option):
                nonlocal recipient_agent
                recipient_agent = self._get_agent_by_name(selected_option)

            def handle_file_upload(file_list):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                uploading_files = True
                attachments = []
                message_file_names = []
                if file_list:
                    try:
                        for file_obj in file_list:
                            purpose = get_file_purpose(file_obj.name)

                            with open(file_obj.name, 'rb') as f:
                                # Upload the file to OpenAI
                                file = self.main_thread.client.files.create(
                                    file=f,
                                    purpose=purpose
                                )

                            if purpose == "vision":
                                images.append({
                                    "type": "image_file",
                                    "image_file": {"file_id": file.id}
                                })
                            else:
                                attachments.append({
                                    "file_id": file.id,
                                    "tools": get_tools(file.filename)
                                })

                            message_file_names.append(file.filename)
                            print(f"Uploaded file ID: {file.id}")
                        return attachments
                    except Exception as e:
                        print(f"Error: {e}")
                        return str(e)
                    finally:
                        uploading_files = False

                uploading_files = False
                return "No files uploaded"

            def user(user_message, history):
                if not user_message.strip():
                    return user_message, history
                
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                nonlocal attachments
                nonlocal recipient_agent

                # Check if attachments contain file search or code interpreter types
                def check_and_add_tools_in_attachments(attachments, recipient_agent):
                    for attachment in attachments:
                        for tool in attachment.get("tools", []):
                            if tool["type"] == "file_search":
                                if not any(isinstance(t, FileSearch) for t in recipient_agent.tools):
                                    # Add FileSearch tool if it does not exist
                                    recipient_agent.tools.append(FileSearch)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added FileSearch tool to recipient agent to analyze the file.")
                            elif tool["type"] == "code_interpreter":
                                if not any(isinstance(t, CodeInterpreter) for t in recipient_agent.tools):
                                    # Add CodeInterpreter tool if it does not exist
                                    recipient_agent.tools.append(CodeInterpreter)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added CodeInterpreter tool to recipient agent to analyze the file.")
                    return None

                check_and_add_tools_in_attachments(attachments, recipient_agent)

                if history is None:
                    history = []

                original_user_message = user_message

                # Append the user message with a placeholder for bot response
                if recipient_agent:
                    user_message = f"👤 User 🗣️ @{recipient_agent.name}:\n" + user_message.strip()
                else:
                    user_message = f"👤 User:" + user_message.strip()

                nonlocal message_file_names
                if message_file_names:
                    user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

                return original_user_message, history + [[user_message, None]]

            class GradioEventHandler(AgencyEventHandler):
                message_output = None

                @classmethod
                def change_recipient_agent(cls, recipient_agent_name):
                    nonlocal chatbot_queue
                    chatbot_queue.put("[change_recipient_agent]")
                    chatbot_queue.put(recipient_agent_name)

                @override
                def on_message_created(self, message: Message) -> None:
                    if message.role == "user":
                        full_content = ""
                        for content in message.content:
                            if content.type == "image_file":
                                full_content += f"🖼️ Image File: {content.image_file.file_id}\n"
                                continue

                            if content.type == "image_url":
                                full_content += f"\n{content.image_url.url}\n"
                                continue

                            if content.type == "text":
                                full_content += content.text.value + "\n"


                        self.message_output = MessageOutput("text", self.agent_name, self.recipient_agent_name,
                                                            full_content)

                    else:
                        self.message_output = MessageOutput("text", self.recipient_agent_name, self.agent_name,
                                                            "")

                    chatbot_queue.put("[new_message]")
                    chatbot_queue.put(self.message_output.get_formatted_content())

                @override
                def on_text_delta(self, delta, snapshot):
                    chatbot_queue.put(delta.value)

                @override
                def on_tool_call_created(self, tool_call: ToolCall):
                    if isinstance(tool_call, dict):
                        if "type" not in tool_call:
                            tool_call["type"] = "function"
                        
                        if tool_call["type"] == "function":
                            tool_call = FunctionToolCall(**tool_call)
                        elif tool_call["type"] == "code_interpreter":
                            tool_call = CodeInterpreterToolCall(**tool_call)
                        elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                            tool_call = FileSearchToolCall(**tool_call)
                        else:
                            raise ValueError("Invalid tool call type: " + tool_call["type"])

                    # TODO: add support for code interpreter and retrieval tools
                    if tool_call.type == "function":
                        chatbot_queue.put("[new_message]")
                        self.message_output = MessageOutput("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))
                        chatbot_queue.put(self.message_output.get_formatted_header() + "\n")

                @override
                def on_tool_call_done(self, snapshot: ToolCall):
                    if isinstance(snapshot, dict):
                        if "type" not in snapshot:
                            snapshot["type"] = "function"
                        
                        if snapshot["type"] == "function":
                            snapshot = FunctionToolCall(**snapshot)
                        elif snapshot["type"] == "code_interpreter":
                            snapshot = CodeInterpreterToolCall(**snapshot)
                        elif snapshot["type"] == "file_search":
                            snapshot = FileSearchToolCall(**snapshot)
                        else:
                            raise ValueError("Invalid tool call type: " + snapshot["type"])
                        
                    self.message_output = None

                    # TODO: add support for code interpreter and retrieval tools
                    if snapshot.type != "function":
                        return

                    chatbot_queue.put(str(snapshot.function))

                    if snapshot.function.name == "SendMessage":
                        try:
                            args = eval(snapshot.function.arguments)
                            recipient = args["recipient"]
                            self.message_output = MessageOutput("text", self.recipient_agent_name, recipient,
                                                                args["message"])

                            chatbot_queue.put("[new_message]")
                            chatbot_queue.put(self.message_output.get_formatted_content())
                        except Exception as e:
                            pass

                    self.message_output = None

                @override
                def on_run_step_done(self, run_step: RunStep) -> None:
                    if run_step.type == "tool_calls":
                        for tool_call in run_step.step_details.tool_calls:
                            if tool_call.type != "function":
                                continue

                            if tool_call.function.name == "SendMessage":
                                continue

                            self.message_output = None
                            chatbot_queue.put("[new_message]")

                            self.message_output = MessageOutput("function_output", tool_call.function.name,
                                                                self.recipient_agent_name,
                                                                tool_call.function.output)

                            chatbot_queue.put(self.message_output.get_formatted_header() + "\n")
                            chatbot_queue.put(tool_call.function.output)

                @override
                @classmethod
                def on_all_streams_end(cls):
                    cls.message_output = None
                    chatbot_queue.put("[end]")

            def bot(original_message, history):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal recipient_agent
                nonlocal recipient_agent_names
                nonlocal images
                nonlocal uploading_files

                if not original_message:
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                if uploading_files:
                    history.append([None, "Uploading files... Please wait."])
                    yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                print("Message files: ", attachments)
                print("Images: ", images)
                
                if images and len(images) > 0:
                    original_message = [
                        {
                            "type": "text",
                            "text": original_message,
                        },
                        *images
                    ]


                completion_thread = threading.Thread(target=self.get_completion_stream, args=(
                    original_message, GradioEventHandler, [], recipient_agent, "", attachments, None))
                completion_thread.start()

                attachments = []
                message_file_names = []
                images = []
                uploading_files = False

                new_message = True
                while True:
                    try:
                        bot_message = chatbot_queue.get(block=True)

                        if bot_message == "[end]":
                            completion_thread.join()
                            break

                        if bot_message == "[new_message]":
                            new_message = True
                            continue

                        if bot_message == "[change_recipient_agent]":
                            new_agent_name = chatbot_queue.get(block=True)
                            recipient_agent = self._get_agent_by_name(new_agent_name)
                            yield "", history, gr.update(value=new_agent_name, choices=set([*recipient_agent_names, recipient_agent.name]))
                            continue

                        if new_message:
                            history.append([None, bot_message])
                            new_message = False
                        else:
                            history[-1][1] += bot_message

                        yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    except queue.Empty:
                        break

            button.click(
                user,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot]
            ).then(
                bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
            )
            dropdown.change(handle_dropdown_change, dropdown)
            file_upload.change(handle_file_upload, file_upload)
            msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
                bot, [msg, chatbot], [msg, chatbot, dropdown]
            )

            # Enable queuing for streaming intermediate outputs
            demo.queue(default_concurrency_limit=10)

        # Launch the demo
        demo.launch(**kwargs)
        return demo

    def _recipient_agent_completer(self, text, state):
        """
        Autocomplete completer for recipient agent names.
        """
        options = [agent for agent in self.recipient_agents if agent.lower().startswith(text.lower())]
        if state < len(options):
            return options[state]
        else:
            return None

    def _setup_autocomplete(self):
        """
        Sets up readline with the completer function.
        """
        try:
            import readline
        except ImportError:
            # Attempt to import pyreadline for Windows compatibility
            try:
                import pyreadline as readline
            except ImportError:
                print(
                    "Module 'readline' not found. Autocomplete will not work. If you are using Windows, try installing 'pyreadline3'.")
                return

        if not readline:
            return

        try:
            readline.set_completer(self._recipient_agent_completer)
            readline.parse_and_bind('tab: complete')
        except Exception as e:
            print(f"Error setting up autocomplete for agents in terminal: {e}. Autocomplete will not work.")

    def run_demo(self):
        """
        Executes agency in the terminal with autocomplete for recipient agent names.
        """
        outer_self = self
        from agency_swarm import AgencyEventHandler
        class TermEventHandler(AgencyEventHandler):
            message_output = None

            @override
            def on_message_created(self, message: Message) -> None:
                if message.role == "user":
                    self.message_output = MessageOutputLive("text", self.agent_name, self.recipient_agent_name,
                                                            "")
                    self.message_output.cprint_update(message.content[0].text.value)
                else:
                    self.message_output = MessageOutputLive("text", self.recipient_agent_name, self.agent_name, "")

            @override
            def on_message_done(self, message: Message) -> None:
                self.message_output = None

            @override
            def on_text_delta(self, delta, snapshot):
                self.message_output.cprint_update(snapshot.value)

            @override
            def on_tool_call_created(self, tool_call):
                if isinstance(tool_call, dict):
                    if "type" not in tool_call:
                        tool_call["type"] = "function"
                    
                    if tool_call["type"] == "function":
                        tool_call = FunctionToolCall(**tool_call)
                    elif tool_call["type"] == "code_interpreter":
                        tool_call = CodeInterpreterToolCall(**tool_call)
                    elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                        tool_call = FileSearchToolCall(**tool_call)
                    else:
                        raise ValueError("Invalid tool call type: " + tool_call["type"])

                # TODO: add support for code interpreter and retirieval tools

                if tool_call.type == "function":
                    self.message_output = MessageOutputLive("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))

            @override
            def on_tool_call_delta(self, delta, snapshot):
                if isinstance(snapshot, dict):
                    if "type" not in snapshot:
                        snapshot["type"] = "function"
                    
                    if snapshot["type"] == "function":
                        snapshot = FunctionToolCall(**snapshot)
                    elif snapshot["type"] == "code_interpreter":
                        snapshot = CodeInterpreterToolCall(**snapshot)
                    elif snapshot["type"] == "file_search":
                        snapshot = FileSearchToolCall(**snapshot)
                    else:
                        raise ValueError("Invalid tool call type: " + snapshot["type"])
                    
                self.message_output.cprint_update(str(snapshot.function))

            @override
            def on_tool_call_done(self, snapshot):
                self.message_output = None

                # TODO: add support for code interpreter and retrieval tools
                if snapshot.type != "function":
                    return

                if snapshot.function.name == "SendMessage" and not (hasattr(outer_self.send_message_tool_class.ToolConfig, 'output_as_result') and outer_self.send_message_tool_class.ToolConfig.output_as_result):
                    try:
                        args = eval(snapshot.function.arguments)
                        recipient = args["recipient"]
                        self.message_output = MessageOutputLive("text", self.recipient_agent_name, recipient,
                                                                "")

                        self.message_output.cprint_update(args["message"])
                    except Exception as e:
                        pass

                self.message_output = None

            @override
            def on_run_step_done(self, run_step: RunStep) -> None:
                if run_step.type == "tool_calls":
                    for tool_call in run_step.step_details.tool_calls:
                        if tool_call.type != "function":
                            continue

                        if tool_call.function.name == "SendMessage":
                            continue

                        self.message_output = None
                        self.message_output = MessageOutputLive("function_output", tool_call.function.name,
                                                                self.recipient_agent_name, tool_call.function.output)
                        self.message_output.cprint_update(tool_call.function.output)

                    self.message_output = None

            @override
            def on_end(self):
                self.message_output = None

        self.recipient_agents = [str(agent.name) for agent in self.main_recipients]

        self._setup_autocomplete()  # Prepare readline for autocomplete

        while True:
            console.rule()
            text = input("👤 USER: ")

            if not text:
                continue

            if text.lower() == "exit":
                break

            recipient_agent = None
            if "@" in text:
                recipient_agent = text.split("@")[1].split(" ")[0]
                text = text.replace(f"@{recipient_agent}", "").strip()
                try:
                    recipient_agent = \
                        [agent for agent in self.recipient_agents if agent.lower() == recipient_agent.lower()][0]
                    recipient_agent = self._get_agent_by_name(recipient_agent)
                except Exception as e:
                    print(f"Recipient agent {recipient_agent} not found.")
                    continue

            self.get_completion_stream(message=text, event_handler=TermEventHandler, recipient_agent=recipient_agent)

    def get_customgpt_schema(self, url: str):
        """Returns the OpenAPI schema for the agency from the CEO agent, that you can use to integrate with custom gpts.

        Parameters:
            url (str): Your server url where the api will be hosted.
        """

        return self.ceo.get_openapi_schema(url)

    def plot_agency_chart(self):
        pass

    def _init_agents(self):
        """
        Initializes all agents in the agency with unique IDs, shared instructions, and OpenAI models.

        This method iterates through each agent in the agency, assigns a unique ID, adds shared instructions, and initializes the OpenAI models for each agent.

        There are no input parameters.

        There are no output parameters as this method is used for internal initialization purposes within the Agency class.
        """
        if self.settings_callbacks:
            loaded_settings = self.settings_callbacks["load"]()
            with open(self.settings_path, 'w') as f:
                json.dump(loaded_settings, f, indent=4)

        for agent in self.agents:
            if "temp_id" in agent.id:
                agent.id = None

            agent.add_shared_instructions(self.shared_instructions)
            agent.settings_path = self.settings_path

            if self.shared_files:
                if isinstance(self.shared_files, str):
                    self.shared_files = [self.shared_files]

                if isinstance(agent.files_folder, str):
                    agent.files_folder = [agent.files_folder]
                    agent.files_folder += self.shared_files
                elif isinstance(agent.files_folder, list):
                    agent.files_folder += self.shared_files

            if self.temperature is not None and agent.temperature is None:
                agent.temperature = self.temperature
            if self.top_p and agent.top_p is None:
                agent.top_p = self.top_p
            if self.max_prompt_tokens is not None and agent.max_prompt_tokens is None:
                agent.max_prompt_tokens = self.max_prompt_tokens
            if self.max_completion_tokens is not None and agent.max_completion_tokens is None:
                agent.max_completion_tokens = self.max_completion_tokens
            if self.truncation_strategy is not None and agent.truncation_strategy is None:
                agent.truncation_strategy = self.truncation_strategy
            
            if not agent.shared_state:
                agent.shared_state = self.shared_state

            agent.init_oai()

        if self.settings_callbacks:
            with open(self.agents[0].get_settings_path(), 'r') as f:
                settings = f.read()
            settings = json.loads(settings)
            self.settings_callbacks["save"](settings)

    def _init_threads(self):
        """
        Initializes threads for communication between agents within the agency.

        This method creates Thread objects for each pair of interacting agents as defined in the agents_and_threads attribute of the Agency. Each thread facilitates communication and task execution between an agent and its designated recipient agent.

        No input parameters.

        Output Parameters:
            This method does not return any value but updates the agents_and_threads attribute with initialized Thread objects.
        """
        self.main_thread = Thread(self.user, self.ceo)

        # load thread ids
        loaded_thread_ids = {}
        if self.threads_callbacks:
            loaded_thread_ids = self.threads_callbacks["load"]()
            if "main_thread" in loaded_thread_ids and loaded_thread_ids["main_thread"]:
                self.main_thread.id = loaded_thread_ids["main_thread"]
            else:
                self.main_thread.init_thread()

        # Save main_thread into agents_and_threads
        self.agents_and_threads["main_thread"] = self.main_thread

        # initialize threads
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            for other_agent, items in threads.items():
                # create thread class
                self.agents_and_threads[agent_name][other_agent] = self._thread_type(
                    self._get_agent_by_name(items["agent"]),
                    self._get_agent_by_name(
                        items["recipient_agent"]))

                # load thread id if available
                if agent_name in loaded_thread_ids and other_agent in loaded_thread_ids[agent_name]:
                    self.agents_and_threads[agent_name][other_agent].id = loaded_thread_ids[agent_name][other_agent]
                # init threads if threre are threads callbacks so the ids are saved for later use
                elif self.threads_callbacks:
                    self.agents_and_threads[agent_name][other_agent].init_thread()

        # save thread ids
        if self.threads_callbacks:
            loaded_thread_ids = {}
            for agent_name, threads in self.agents_and_threads.items():
                if agent_name == "main_thread":
                    continue
                loaded_thread_ids[agent_name] = {}
                for other_agent, thread in threads.items():
                    loaded_thread_ids[agent_name][other_agent] = thread.id

            loaded_thread_ids["main_thread"] = self.main_thread.id

            self.threads_callbacks["save"](loaded_thread_ids)

    def _parse_agency_chart(self, agency_chart):
        """
        Parses the provided agency chart to initialize and organize agents within the agency.
        
        Parameters:
            agency_chart: A structure representing the hierarchical organization of agents within the agency.
                    It can contain Agent objects and lists of Agent objects.

        This method iterates through each node in the agency chart. If a node is an Agent, it is set as the CEO if not already assigned.
        If a node is a list, it iterates through the agents in the list, adding them to the agency and establishing communication
        threads between them. It raises an exception if the agency chart is invalid or if multiple CEOs are defined.
        """
        if not isinstance(agency_chart, list):
            raise Exception("Invalid agency chart.")

        if len(agency_chart) == 0:
            raise Exception("Agency chart cannot be empty.")

        for node in agency_chart:
            if isinstance(node, Agent):
                if not self.ceo:
                    self.ceo = node
                    self._add_agent(self.ceo)
                else:
                    self._add_agent(node)
                self._add_main_recipient(node)

            elif isinstance(node, list):
                for i, agent in enumerate(node):
                    if not isinstance(agent, Agent):
                        raise Exception("Invalid agency chart.")

                    index = self._add_agent(agent)

                    if i == len(node) - 1:
                        continue

                    if agent.name not in self.agents_and_threads.keys():
                        self.agents_and_threads[agent.name] = {}

                    if i < len(node) - 1:
                        other_agent = node[i + 1]
                        if other_agent.name == agent.name:
                            continue
                        if other_agent.name not in self.agents_and_threads[agent.name].keys():
                            self.agents_and_threads[agent.name][other_agent.name] = {
                                "agent": agent.name,
                                "recipient_agent": other_agent.name,
                            }
            else:
                raise Exception("Invalid agency chart.")

    def _add_agent(self, agent):
        """
        Adds an agent to the agency, assigning a temporary ID if necessary.

        Parameters:
            agent (Agent): The agent to be added to the agency.

        Returns:
            int: The index of the added agent within the agency's agents list.

        This method adds an agent to the agency's list of agents. If the agent does not have an ID, it assigns a temporary unique ID. It checks for uniqueness of the agent's name before addition. The method returns the index of the agent in the agency's agents list, which is used for referencing the agent within the agency.
        """
        if not agent.id:
            # assign temp id
            agent.id = "temp_id_" + str(uuid.uuid4())
        if agent.id not in self._get_agent_ids():
            if agent.name in self._get_agent_names():
                raise Exception("Agent names must be unique.")
            self.agents.append(agent)
            return len(self.agents) - 1
        else:
            return self._get_agent_ids().index(agent.id)

    def _add_main_recipient(self, agent):
        """
        Adds an agent to the agency's list of main recipients.

        Parameters:
            agent (Agent): The agent to be added to the agency's list of main recipients.

        This method adds an agent to the agency's list of main recipients. These are agents that can be directly contacted by the user.
        """
        main_recipient_ids = [agent.id for agent in self.main_recipients]

        if agent.id not in main_recipient_ids:
            self.main_recipients.append(agent)

    def _read_instructions(self, path):
        """
        Reads shared instructions from a specified file and stores them in the agency.

        Parameters:
            path (str): The file path from which to read the shared instructions.

        This method opens the file located at the given path, reads its contents, and stores these contents in the 'shared_instructions' attribute of the agency. This is used to provide common guidelines or instructions to all agents within the agency.
        """
        path = path
        with open(path, 'r') as f:
            self.shared_instructions = f.read()

    def _create_special_tools(self):
        """
        Creates and assigns 'SendMessage' tools to each agent based on the agency's structure.

        This method iterates through the agents and threads in the agency, creating SendMessage tools for each agent. These tools enable agents to send messages to other agents as defined in the agency's structure. The SendMessage tools are tailored to the specific recipient agents that each agent can communicate with.

        No input parameters.

        No output parameters; this method modifies the agents' toolset internally.
        """
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            recipient_names = list(threads.keys())
            recipient_agents = self._get_agents_by_names(recipient_names)
            if len(recipient_agents) == 0:
                continue
            agent = self._get_agent_by_name(agent_name)
            agent.add_tool(self._create_send_message_tool(agent, recipient_agents))
            if self._thread_type == ThreadAsync:
                agent.add_tool(self._create_get_response_tool(agent, recipient_agents))

    def _create_send_message_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a SendMessage tool to enable an agent to send messages to specified recipient agents.


        Parameters:
            agent (Agent): The agent who will be sending messages.
            recipient_agents (List[Agent]): A list of recipient agents who can receive messages.

        Returns:
            SendMessage: A SendMessage tool class that is dynamically created and configured for the given agent and its recipient agents. This tool allows the agent to send messages to the specified recipients, facilitating inter-agent communication within the agency.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        agent_descriptions = ""
        for recipient_agent in recipient_agents:
            if not recipient_agent.description:
                continue
            agent_descriptions += recipient_agent.name + ": "
            agent_descriptions += recipient_agent.description + "\n"

        class SendMessage(self.send_message_tool_class):
            recipient: recipients = Field(..., description=agent_descriptions)

            @field_validator('recipient')
            @classmethod
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

        SendMessage._caller_agent = agent
        SendMessage._agents_and_threads = self.agents_and_threads

        return SendMessage

    def _create_get_response_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a CheckStatus tool to enable an agent to check the status of a task with a specified recipient agent.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        outer_self = self

        class GetResponse(BaseTool):
            """This tool allows you to check the status of a task or get a response from a specified recipient agent, if the task has been completed. You must always use 'SendMessage' tool with the designated agent first."""
            recipient: recipients = Field(...,
                                          description=f"Recipient agent that you want to check the status of. Valid recipients are: {recipient_names}")

            @field_validator('recipient')
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

            def run(self):
                thread = outer_self.agents_and_threads[self._caller_agent.name][self.recipient.value]

                return thread.check_status()

        GetResponse._caller_agent = agent

        return GetResponse

    def _get_agent_by_name(self, agent_name):
        """
        Retrieves an agent from the agency based on the agent's name.

        Parameters:
            agent_name (str): The name of the agent to be retrieved.

        Returns:
            Agent: The agent object with the specified name.

        Raises:
            Exception: If no agent with the given name is found in the agency.
        """
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        raise Exception(f"Agent {agent_name} not found.")

    def _get_agents_by_names(self, agent_names):
        """
        Retrieves a list of agent objects based on their names.

        Parameters:
            agent_names: A list of strings representing the names of the agents to be retrieved.

        Returns:
            A list of Agent objects corresponding to the given names.
        """
        return [self._get_agent_by_name(agent_name) for agent_name in agent_names]

    def _get_agent_ids(self):
        """
        Retrieves the IDs of all agents currently in the agency.

        Returns:
            List[str]: A list containing the unique IDs of all agents.
        """
        return [agent.id for agent in self.agents]

    def _get_agent_names(self):
        """
        Retrieves the names of all agents in the agency.

        Returns:
            List[str]: A list of names of all agents currently part of the agency.
        """
        return [agent.name for agent in self.agents]

    def _get_class_folder_path(self):
        """
        Retrieves the absolute path of the directory containing the class file.

        Returns:
            str: The absolute path of the directory where the class file is located.
        """
        return os.path.abspath(os.path.dirname(inspect.getfile(self.__class__)))

    def delete(self):
        """
        This method deletes the agency and all its agents, cleaning up any files and vector stores associated with each agent.
        """
        for agent in self.agents:
            agent.delete()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\AgentCreator.py
================================================
from agency_swarm import Agent
from .tools.ImportAgent import ImportAgent
from .tools.CreateAgentTemplate import CreateAgentTemplate
from .tools.ReadManifesto import ReadManifesto

class AgentCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new agents for the agency.",
            instructions="./instructions.md",
            tools=[ImportAgent, CreateAgentTemplate, ReadManifesto],
            temperature=0.3,
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\instructions.md
================================================
# AgentCreator Agent Instructions

You are an agent that creates other agents as instructed by the user. 

The user will communicate to you each agent that needs to be created. Below are your instructions that needs to be followed for each agent communicated by the user.

**Primary Instructions:**
1. First, read the manifesto using `ReadManifesto` tool if you have not already done so. This file contains the agency manifesto that describes the agency's purpose and goals.
2. If a similar agent to the requested one is accessible through the `ImportAgent` tool, import this agent and inform the user that the agent has been created. Skip the following steps.
3. If not, create a new agent using `CreateAgentTemplate` tool. 
4. Tell the `ToolCreator` agent to create tools or APIs for this agent. Make sure to also communicate the agent description, name and a summary of the processes that it needs to perform. CEO Agents do not need to utilize any tools, so you can skip this and the following steps.
5. If there are no issues and tools have been successfully created, notify the user that the agent has been created. Otherwise, try to resolve any issues with the tool creator before reporting back to the user.
6. Repeat this process for each agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\CreateAgentTemplate.py
================================================
import os
import shutil
from typing import List

from pydantic import Field, model_validator

from agency_swarm import BaseTool
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.util import create_agent_template

allowed_tools: List = ["CodeInterpreter"]

web_developer_example_instructions = """# Web Developer Agent Instructions

You are an agent that builds responsive web applications using Next.js and Material-UI (MUI). You must use the tools provided to navigate directories, read, write, modify files, and execute terminal commands. 

### Primary Instructions:
1. Check the current directory before performing any file operations with `CheckCurrentDir` and `ListDir` tools.
2. Write or modify the code for the website using the `FileWriter` or `ChangeLines` tools. Make sure to use the correct file paths and file names. Read the file first if you need to modify it.
3. Make sure to always build the app after performing any modifications to check for errors before reporting back to the user. Keep in mind that all files must be reflected on the current website
4. Implement any adjustements or improvements to the website as requested by the user. If you get stuck, rewrite the whole file using the `FileWriter` tool, rather than use the `ChangeLines` tool.
"""


class CreateAgentTemplate(BaseTool):
    """
    This tool creates a template folder for a new agent. Always use this tool first, before creating tools or APIs for the agent.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to be created. Cannot include special characters or spaces."
    )
    agent_description: str = Field(
        ..., description="Description of the agent to be created."
    )
    instructions: str = Field(
        ..., description="Instructions for the agent to be created in markdown format. "
                         "Instructions should include a decription of the role and a specific step by step process "
                         "that this agent need to perform in order to execute the tasks. "
                         "The process must also be aligned with all the other agents in the agency. Agents should be "
                         "able to collaborate with each other to achieve the common goal of the agency.",
        examples=[
            web_developer_example_instructions,
        ]
    )
    default_tools: List[str] = Field(
        [], description=f"List of default tools to be included in the agent. Possible values are {allowed_tools}."
                        f"CodeInterpreter allows the agent to execute python code in a remote python environment.",
        example=["CodeInterpreter"],
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("manifesto_read"):
            raise ValueError("Please read the manifesto first with the ReadManifesto tool.")

        self._shared_state.set("agent_name", self.agent_name)

        os.chdir(self._shared_state.get("agency_path"))

        # remove folder if it already exists
        if os.path.exists(self.agent_name):
            shutil.rmtree(self.agent_name)

        create_agent_template(self.agent_name,
                              self.agent_description,
                              instructions=self.instructions,
                              code_interpreter=True if "CodeInterpreter" in self.default_tools else None,
                              include_example_tool=False)

        # # create or append to init file
        path = self._shared_state.get("agency_path")
        class_name = self.agent_name.replace(" ", "").strip()
        if not os.path.isfile("__init__.py"):
            with open("__init__.py", "w") as f:
                f.write(f"from .{class_name} import {class_name}")
        else:
            with open("__init__.py", "a") as f:
                f.write(f"\nfrom .{class_name} import {class_name}")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {class_name} import {class_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        if "ceo" in self.agent_name.lower():
            return f"You can tell the user that the process of creating {self.agent_name} has been completed, because CEO agent does not need to utilizie any tools or APIs."

        return f"Agent template has been created for {self.agent_name}. Please now tell ToolCreator to create tools for this agent or OpenAPICreator to create API schemas, if this agent needs to utilize any tools or APIs. If this is unclear, please ask the user for more information."

    @model_validator(mode="after")
    def validate_tools(self):
        check_agency_path(self)

        for tool in self.default_tools:
            if tool not in allowed_tools:
                raise ValueError(f"Tool {tool} is not allowed. Allowed tools are: {allowed_tools}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ImportAgent.py
================================================
import os

from pydantic import Field, field_validator

from agency_swarm import BaseTool
from agency_swarm.util.cli import import_agent
from agency_swarm.util.helpers import get_available_agent_descriptions, list_available_agents


class ImportAgent(BaseTool):
    """
    This tool imports an existing agent from agency swarm framework. Please make sure to first use the GetAvailableAgents tool to get the list of available agents.
    """
    agent_name: str = Field(...,
                            description=get_available_agent_descriptions())
    agency_path: str = Field(
        None, description="Path to the agency where the agent will be imported. Default is the current agency.")

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set("default_folder", os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_path:
            return "Error: You must set the agency_path."

        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
        else:
            os.chdir(self.agency_path)

        import_agent(self.agent_name, "./")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {self.agent_name} import {self.agent_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        return (f"Success. {self.agent_name} has been imported. "
                f"You can now tell the user to user proceed with next agents.")

    @field_validator("agent_name", mode='after')
    @classmethod
    def agent_name_exists(cls, v):
        available_agents = list_available_agents()
        if v not in available_agents:
            raise ValueError(
                f"Agent with name {v} does not exist. Available agents are: {available_agents}")
        return v

if __name__ == "__main__":
    tool = ImportAgent(agent_name="Devid")
    tool._shared_state.set("agency_path", "./")
    tool.run()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ReadManifesto.py
================================================
import os

from pydantic import Field

from agency_swarm import BaseTool


class ReadManifesto(BaseTool):
    """
    This tool reads a manifesto for the agency being created from a markdown file.
    """
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_name:
            raise ValueError("Please specify the agency name. Ask user for clarification if needed.")

        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))

        with open("agency_manifesto.md", "r") as f:
            manifesto = f.read()

        os.chdir(self._shared_state.get("default_folder"))

        self._shared_state.set("manifesto_read", True)

        return manifesto


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\get_modules.py
================================================
import importlib.resources
import pathlib


def get_modules(module_name):
    """
    Get all submodule names from a given module based on file names, without importing them,
    excluding those containing '.agent' or '.genesis' in their paths.

    Args:
    - module_name: The name of the module to search through.

    Returns:
    - A list of submodule names found within the given module.
    """
    submodule_names = []

    try:
        # Using importlib.resources to access the package contents
        with importlib.resources.path(module_name, '') as package_path:
            # Walk through the package directory using pathlib
            for path in pathlib.Path(package_path).rglob('*.py'):
                if path.name != '__init__.py':
                    # Construct the module name from the file path
                    relative_path = path.relative_to(package_path)
                    module_path = '.'.join(relative_path.with_suffix('').parts)

                    submodule_names.append(f"{module_name}.{module_path}")

    except ImportError:
        print(f"Module {module_name} not found.")
        return submodule_names

    submodule_names = [name for name in submodule_names if not name.endswith(".agent") and
                       '.genesis' not in name and
                       'util' not in name and
                       'oai' not in name and
                       'ToolFactory' not in name and
                       'BaseTool' not in name]

    # remove repetition at the end of the path like 'agency_swarm.agents.coding.CodingAgent.CodingAgent'
    for i in range(len(submodule_names)):
        splitted = submodule_names[i].split(".")
        if splitted[-1] == splitted[-2]:
            submodule_names[i] = ".".join(splitted[:-1])

    return submodule_names


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\__init__.py
================================================
from .get_modules import get_modules

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\__init__.py
================================================
from .AgentCreator import AgentCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisAgency.py
================================================
from agency_swarm import Agency
from .AgentCreator import AgentCreator

from .GenesisCEO import GenesisCEO
from .OpenAPICreator import OpenAPICreator
from .ToolCreator import ToolCreator
from agency_swarm.util.helpers import get_available_agent_descriptions

class GenesisAgency(Agency):
    def __init__(self, with_browsing=True, **kwargs):
        if "max_prompt_tokens" not in kwargs:
            kwargs["max_prompt_tokens"] = 25000

        if 'agency_chart' not in kwargs:
            agent_creator = AgentCreator()
            genesis_ceo = GenesisCEO()
            tool_creator = ToolCreator()
            openapi_creator = OpenAPICreator()
            kwargs['agency_chart'] = [
                genesis_ceo, tool_creator, agent_creator,
                [genesis_ceo, agent_creator],
                [agent_creator, tool_creator],
            ]

            if with_browsing:
                from agency_swarm.agents.BrowsingAgent import BrowsingAgent
                browsing_agent = BrowsingAgent()

                browsing_agent.instructions += ("""\n
# BrowsingAgent's Primary instructions
1. Browse the web to find the API documentation requested by the user. Prefer searching google directly for this API documentation page.
2. Navigate to the API documentation page and ensure that it contains the necessary API endpoints descriptions. You can use the AnalyzeContent tool to check if the page contains the necessary API descriptions. If not, try perform another search in google and keep browsing until you find the right page.
3. If you have confirmed that the page contains the necessary API documentation, export the page with ExportFile tool. Then, send the file_id back to the user along with a brief description of the API.
4. Repeat these steps for each new agent, as requested by the user.
                """)
                kwargs['agency_chart'].append(openapi_creator)
                kwargs['agency_chart'].append([openapi_creator, browsing_agent])

        if 'shared_instructions' not in kwargs:
            kwargs['shared_instructions'] = "./manifesto.md"

        super().__init__(**kwargs)


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\GenesisCEO.py
================================================
from pathlib import Path

from agency_swarm import Agent
from .tools.CreateAgencyFolder import CreateAgencyFolder
from .tools.FinalizeAgency import FinalizeAgency
from .tools.ReadRequirements import ReadRequirements


class GenesisCEO(Agent):
    def __init__(self):
        super().__init__(
            description="Acts as the overseer and communicator across the agency, ensuring alignment with the "
                        "agency's goals.",
            instructions="./instructions.md",
            tools=[CreateAgencyFolder, FinalizeAgency, ReadRequirements],
            temperature=0.4,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\instructions.md
================================================
# GenesisCEO Agent Instructions

As a Genesis CEO Agent within the Agency Swarm framework, your mission is to help users define the structure of their agency and create the initial agents.

1. Pick a name for the agency, determine its goals and mission. Ask the user for any clarification if needed.
2. Propose an initial structure for the agency, including the roles of the agents, their communication flows and what APIs or Tools each agent can use, if specified by the user. Focus on creating at most 2 agents, plus CEO, unless instructed otherwise by the user. Do not name the CEO agent GenesisCEO. It's name must be tailored for the purpose of the agency. Output the code snippet like below. Adjust it accordingly, based on user's input.
3. Upon confirmation of the agency structure, use `CreateAgencyFolder` tool to create a folder for the agency. If any modifications are required please use this tool again with the same agency name and it will overwrite the existing folder.
4. Tell AgentCreator to create these agents one by one, starting with the CEO. Each agent should be sent in a separate message using the `SendMessage` tool. Please make sure to include the agent description, summary of the processes it needs to perform and the APIs or Tools that it can use via the message parameter.
5. Once all agents are created, please use the `FinalizeAgency` tool, and tell the user that he can now navigate to the agency folder and start it with `python agency.py` command.


### Example of communication flows

Here is an example of how communication flows are defined in agency swarm. Essentially, agents that are inside a double array can initiate communication with each other. Agents that are in the top level array can communicate with the user. 

```python
agency = Agency([
    ceo, dev,  # CEO and Developer will be the entry point for communication with the user
    [ceo, dev],  # CEO can initiate communication with Developer
    [ceo, va],   # CEO can initiate communication with Virtual Assistant
    [dev, va]    # Developer can initiate communication with Virtual Assistant
], shared_instructions='agency_manifesto.md') # shared instructions for all agents
```
Keep in mind that this is just an example and you should replace it with the actual agents you are creating. Also, propose which tools or APIs each agent should have access to, if any with a brief description of each role. Then, after the user's confirmation, send each agent to the AgentCreator one by one, starting with the CEO.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\CreateAgencyFolder.py
================================================
import shutil
from pathlib import Path

from pydantic import Field, field_validator, model_validator

import agency_swarm.agency.genesis.GenesisAgency
from agency_swarm import BaseTool

import os


class CreateAgencyFolder(BaseTool):
    """
    This tool creates or modifies an agency folder. You can use it again with the same agency_name to modify a previously created agency, if the user wants to change the agency chart or the manifesto.
    """
    agency_name: str = Field(
        ..., description="Name of the agency to be created. Must not contain spaces or special characters.",
        examples=["AgencyName", "MyAgency", "ExampleAgency"]
    )
    agency_chart: str = Field(
        ..., description="Agency chart to be passed into the Agency class.",
        examples=["[ceo, [ceo, dev], [ceo, va], [dev, va]]"]
    )
    manifesto: str = Field(
        ..., description="Manifesto for the agency, describing its goals and additional context shared by all agents "
                         "in markdown format. It must include information about the working environment, the mission "
                         "and the goals of the agency. Do not add descriptions of the agents themselves or the agency structure.",
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', Path.cwd())

        if self._shared_state.get("agency_name") is None:
            os.mkdir(self.agency_name)
            os.chdir("./" + self.agency_name)
            self._shared_state.set("agency_name", self.agency_name)
            self._shared_state.set("agency_path", Path("./").resolve())
        elif self._shared_state.get("agency_name") == self.agency_name and os.path.exists(self._shared_state.get("agency_path")):
            os.chdir(self._shared_state.get("agency_path"))
            for file in os.listdir():
                if file != "__init__.py" and os.path.isfile(file):
                    os.remove(file)
        else:
            os.mkdir(self._shared_state.get("agency_path"))
            os.chdir("./" + self.agency_name)

        # check that agency chart is valid
        if not self.agency_chart.startswith("[") or not self.agency_chart.endswith("]"):
            raise ValueError("Agency chart must be a list of lists, except for the first agents.")

        # add new lines after every comma, except for those inside second brackets
        # must transform from "[ceo, [ceo, dev], [ceo, va], [dev, va] ]"
        # to "[ceo, [ceo, dev],\n [ceo, va],\n [dev, va] ]"
        agency_chart = self.agency_chart.replace("],", "],\n")

        # create init file
        with open("__init__.py", "w") as f:
            f.write("")

        # create agency.py
        with open("agency.py", "w") as f:
            f.write(agency_py.format(agency_chart=agency_chart))

        # write manifesto
        path = os.path.join("agency_manifesto.md")
        with open(path, "w") as f:
            f.write(self.manifesto)

        os.chdir(self._shared_state.get('default_folder'))

        return f"Agency folder has been created. You can now tell AgentCreator to create agents for {self.agency_name}.\n"


agency_py = """from agency_swarm import Agency


agency = Agency({agency_chart},
                shared_instructions='./agency_manifesto.md', # shared instructions for all agents
                max_prompt_tokens=25000, # default tokens in conversation for all agents
                temperature=0.3, # default temperature for all agents
                )
                
if __name__ == '__main__':
    agency.demo_gradio()
"""

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\FinalizeAgency.py
================================================
import os
from typing import List

from pydantic import Field, model_validator, field_validator

from agency_swarm import BaseTool, get_openai_client
from agency_swarm.util import create_agent_template


class FinalizeAgency(BaseTool):
    """
    This tool finalizes the agency structure and it's imports. Please make sure to use at only at the very end, after all agents have been created.
    """
    agency_path: str = Field(
        None, description="Path to the agency folder. Defaults to the agency currently being created."
    )

    def run(self):
        agency_path = None
        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
            agency_path = self._shared_state.get("agency_path")
        else:
            os.chdir(self.agency_path)
            agency_path = self.agency_path

        client = get_openai_client()

        # read agency.py
        with open("./agency.py", "r") as f:
            agency_py = f.read()
            f.close()

        res = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=examples + [
                {'role': "user", 'content': agency_py},
            ],
            temperature=0.0,
        )

        message = res.choices[0].message.content

        # write agency.py
        with open("./agency.py", "w") as f:
            f.write(message)
            f.close()

        return f"Successfully finalized {agency_path} structure. You can now instruct the user to run the agency.py file."

    @model_validator(mode="after")
    def validate_agency_path(self):
        if not self._shared_state.get("agency_path") and not self.agency_path:
            raise ValueError("Agency path not found. Please specify the agency_path. Ask user for clarification if needed.")


SYSTEM_PROMPT = """"Please read the file provided by the user and fix all the imports and indentation accordingly. 

Only output the full valid python code and nothing else."""

example_input = """
from agency_swarm import Agency

from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent


agency = Agency([ceo, [ceo, news_analysis],
 [ceo, price_tracking],
 [news_analysis, price_tracking]],
shared_instructions='./agency_manifesto.md')

if __name__ == '__main__':
    agency.demo_gradio()
"""

example_output = """from agency_swarm import Agency
from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent

ceo = CEO()
news_analysis = NewsAnalysisAgent()
price_tracking = PriceTrackingAgent()

agency = Agency([ceo, [ceo, market_analyst],
                 [ceo, news_curator],
                 [market_analyst, news_curator]],
                shared_instructions='./agency_manifesto.md')
    
if __name__ == '__main__':
    agency.demo_gradio()"""

examples = [
    {'role': "system", 'content': SYSTEM_PROMPT},
    {'role': "user", 'content': example_input},
    {'role': "assistant", 'content': example_output}
]


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\ReadRequirements.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field
import os


class ReadRequirements(BaseTool):
    """
    Use this tool to read the agency requirements if user provides them as a file.
    """

    file_path: str = Field(
        ..., description="The path to the file that needs to be read."
    )

    def run(self):
        """
        Checks if the file exists, and if so, opens the specified file, reads its contents, and returns them.
        If the file does not exist, raises a ValueError.
        """
        if not os.path.exists(self.file_path):
            raise ValueError(f"File path does not exist: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except Exception as e:
            return f"An error occurred while reading the file: {str(e)}"


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\__init__.py
================================================
from .GenesisCEO import GenesisCEO

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\manifesto.md
================================================
# Genesis Agency Manifesto

You are a part of a Genesis Agency for a framework called Agency Swarm. The goal of your agency is to create other agencies within this framework. Below is a brief description of the framework.

**Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the AI agent creation process and enable anyone to create a collaborative swarms of agents (Agencies), each with distinct roles and capabilities. These agents must function autonomously, yet collaborate with other agents to achieve a common goal.**

Keep in mind that communication with the other agents within your agency via the `SendMessage` tool is synchronous. Other agents will not be executing any tasks post response. Please instruct the recipient agent to continue its execution, if needed. Do not report to the user before the recipient agent has completed its task. If the agent proposes the next steps, for example, you must instruct the recipient agent to execute them.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\instructions.md
================================================
# OpenAPICreator Instructions

You are an agent that creates tools from OpenAPI schemas. User will provide you with a description of the agent's role. If the provided description does not require any API calls, please notify the user.

**Here are your primary instructions:**
1. Think which API is needed for this agent's role, as communicated by the user. Then, tell the BrowsingAgent to find this API documentation page.
2. Explore the provided file from the BrowsingAgent with the `myfiles_broswer` tool to determine which endpoints are needed for this agent's role.
3. If the file does not contain the actual API documentation page, please notify the BrowsingAgent. Keep in mind that you do not need the full API documentation. You can make an educated guess if some information is not available.
4. Use `CreateToolsFromOpenAPISpec` to create the tools by defining the OpenAPI schema accordingly. Make sure to include all the relevant API endpoints that are needed for this agent to execute its role from the provided file. Do not truncate the schema.
5. Repeat these steps for each new agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\OpenAPICreator.py
================================================
from agency_swarm import Agent
from .tools.CreateToolsFromOpenAPISpec import CreateToolsFromOpenAPISpec


class OpenAPICreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools from an OpenAPI specifications.",
            instructions="./instructions.md",
            tools=[CreateToolsFromOpenAPISpec]
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\tools\CreateToolsFromOpenAPISpec.py
================================================
import os

from pydantic import Field, field_validator, model_validator

from agency_swarm import BaseTool

import json

from agency_swarm.agency.genesis.util import check_agency_path, check_agent_path
from agency_swarm.tools import ToolFactory
from agency_swarm.util.openapi import validate_openapi_spec


class CreateToolsFromOpenAPISpec(BaseTool):
    """
    This tool creates a set of tools from an OpenAPI specification. Each method in the specification is converted to a separate tool.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to create the API for. Must be an existing agent."
    )
    openapi_spec: str = Field(
        ..., description="OpenAPI specification for the tool to be created as a valid JSON string. Only the relevant "
                         "endpoints must be included. Responses are not required. Each method should contain "
                         "an operation id and a description. Do not truncate this schema. "
                         "It must be a full valid OpenAPI 3.1.0 specification.",
        examples=[
            '{\n  "openapi": "3.1.0",\n  "info": {\n    "title": "Get weather data",\n    "description": "Retrieves current weather data for a location.",\n    "version": "v1.0.0"\n  },\n  "servers": [\n    {\n      "url": "https://weather.example.com"\n    }\n  ],\n  "paths": {\n    "/location": {\n      "get": {\n        "description": "Get temperature for a specific location",\n        "operationId": "GetCurrentWeather",\n        "parameters": [\n          {\n            "name": "location",\n            "in": "query",\n            "description": "The city and state to retrieve the weather for",\n            "required": true,\n            "schema": {\n              "type": "string"\n            }\n          }\n        ],\n        "deprecated": false\n      }\n    }\n  },\n  "components": {\n    "schemas": {}\n  }\n}'])
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        os.chdir(self._shared_state.get("agency_path"))

        os.chdir(self.agent_name)

        try:
            try:
                tools = ToolFactory.from_openapi_schema(self.openapi_spec)
            except Exception as e:
                raise ValueError(f"Error creating tools from OpenAPI Spec: {e}")

            if len(tools) == 0:
                return "No tools created. Please check the OpenAPI specification."

            tool_names = [tool.__name__ for tool in tools]

            # save openapi spec
            folder_path = "./" + self.agent_name + "/"
            os.chdir(folder_path)

            api_name = json.loads(self.openapi_spec)["info"]["title"]

            api_name = api_name.replace("API", "Api").replace(" ", "")

            api_name = ''.join(['_' + i.lower() if i.isupper() else i for i in api_name]).lstrip('_')

            with open("schemas/" + api_name + ".json", "w") as f:
                f.write(self.openapi_spec)

            return "Successfully added OpenAPI Schema to " + self._shared_state.get("agent_name")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

    @field_validator("openapi_spec", mode='before')
    @classmethod
    def validate_openapi_spec(cls, v):
        try:
            validate_openapi_spec(v)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format:", e)
        except Exception as e:
            raise ValueError("Error validating OpenAPI schema:", e)
        return v

    @model_validator(mode="after")
    def validate_agent_name(self):
        check_agency_path(self)

        check_agent_path(self)



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\__init__.py
================================================
from .OpenAPICreator import OpenAPICreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\instructions.md
================================================
# ToolCreator Agent Instructions

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

**Here are your primary instructions:**
1. Determine which tools the agent must utilize to perform it's role. Make an educated guess if the user has not specified any tools or APIs. Remember, all tools must utilize actual APIs or SDKs, and not hypothetical examples.
2. Create these tools one at a time, using `CreateTool` tool.
3. Test each tool with the `TestTool` function to ensure it is working as expected. Do not ask the user, always test the tool yourself, if it does not require any API keys and all the inputs can be mocked.
4. Only after all the necessary tools are created, notify the user.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\ToolCreator.py
================================================
from agency_swarm import Agent
from .tools.CreateTool import CreateTool
from .tools.TestTool import TestTool


class ToolCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools for the agency using python code.",
            instructions="./instructions.md",
            tools=[CreateTool, TestTool],
            temperature=0,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\tools\CreateTool.py
================================================
import os
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agency_swarm import get_openai_client
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.tools import BaseTool

prompt = """# Agency Swarm Overview

Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the agent creation process and enable anyone to create a collaborative swarm of agents (Agencies), each with distinct roles and capabilities. 

# ToolCreator Agent Instructions for Agency Swarm Framework

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

### Tool Creation Guide

When creating a tool, you are essentially defining a new class that extends `BaseTool`. This process involves several key steps, outlined below.

#### 1. Import Necessary Modules

Start by importing `BaseTool` from `agency_swarm.tools` and `Field` from `pydantic`. These imports will serve as the foundation for your custom tool class. Import any additional packages necessary to implement the tool's logic.

#### 2. Define Your Tool Class

Create a new class that inherits from `BaseTool`. This class will encapsulate the functionality of your tool. `BaseTool` class inherits from the Pydantic's `BaseModel` class.

#### 3. Specify Tool Fields

Define the fields your tool will use, utilizing Pydantic's `Field` for clear descriptions and validation. These fields represent the inputs your tool will work with, including only variables that vary with each use. Define any constant variables like api keys globally.

#### 4. Implement the `run` Method

The `run` method is where your tool's logic is executed. Use the fields defined earlier to perform the tool's intended task. It must contain the actual fully functional correct python code. It can utilize various python packages, previously imported in step 1. Do not include any placeholders or hypothetical examples in the code.

### Example of a Custom Tool

```python
from agency_swarm.tools import BaseTool
from pydantic import Field
import os

account_id = "MY_ACCOUNT_ID"
api_key = os.getenv("MY_API_KEY") # or access_token = os.getenv("MY_ACCESS_TOKEN")

class MyCustomTool(BaseTool):
    \"\"\"
    A brief description of what the custom tool does.
    The docstring should clearly explain the tool's purpose and functionality.
    It will be used by the agent to determine when to use this tool.
    \"\"\"

    # Define the fields with descriptions using Pydantic Field
    example_field: str = Field(
        ..., description="Description of the example field, explaining its purpose and usage for the Agent."
    )

    def run(self):
        \"\"\"
        The implementation of the run method, where the tool's main functionality is executed.
        This method should utilize the fields defined above to perform the task.
        \"\"\"
        # Your custom tool logic goes here
        # Example: 
        # do_something(self.example_field, api_key, account_id)

        # Return the result of the tool's operation as a string
        return "Result of MyCustomTool operation"
```

To share state between 2 or more tools, you can use the `shared_state` attribute of the tool. It is a dictionary that can be used to store and retrieve values across different tools. This can be useful for passing information between tools or agents or to verify the state of the system. Here is an example of how to use the `shared_state`:

```python
class MyCustomTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        # Update the shared state
        self._shared_state.set("key", "value")
        
        return "Result of MyCustomTool operation"
        
# Access shared state in another tool
class AnotherTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        return "Result of AnotherTool operation"
```

This is useful to pass information between tools or agents or to verify the state of the system.  

Remember, you must output the resulting python tool code as a whole in a code block, so the user can just copy and paste it into his program. Each tool code snippet must be ready to use. It must not contain any placeholders or hypothetical examples."""

history = [
            {
                "role": "system",
                "content": prompt
            },
        ]


class CreateTool(BaseTool):
    """This tool creates other custom tools for the agent, based on your requirements and details."""
    agent_name: str = Field(
        ..., description="Name of the agent to create the tool for."
    )
    tool_name: str = Field(..., description="Name of the tool class in camel case.", examples=["ExampleTool"])
    requirements: str = Field(
        ...,
        description="The comprehensive requirements explaning the primary functionality of the tool. It must not contain any code or implementation details."
    )
    details: str = Field(
        None, description="Additional details or error messages, class, function, and variable names."
    )
    mode: Literal["write", "modify"] = Field(
        ..., description="The mode of operation for the tool. 'write' is used to create a new tool or overwrite an existing one. 'modify' is used to modify an existing tool."
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))
        os.chdir(self.agent_name)

        client = get_openai_client()

        if self.mode == "write":
            message = f"Please create a '{self.tool_name}' tool that meets the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."
        else:
            message = f"Please rewrite a '{self.tool_name}' according to the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."

        if self.details:
            message += f"\nAdditional Details: {self.details}"

        if self.mode == "modify":
            message += f"\nThe existing file content is as follows:"

            try:
                with open("./tools/" + self.tool_name + ".py", 'r') as file:
                    prev_content = file.read()
                    message += f"\n\n```{prev_content}```"
            except Exception as e:
                os.chdir(self._shared_state.get("default_folder"))
                return f'Error reading {self.tool_name}: {e}'

        history.append({
                "role": "user",
                "content": message
            })

        messages = history.copy()

        # use the last 6 messages
        messages = messages[-6:]

        # add system message upfront
        messages.insert(0, history[0])

        n = 0
        code = ""
        content = ""
        while n < 3:
            resp = client.chat.completions.create(
                messages=messages,
                model="gpt-4o",
                temperature=0,
            )

            content = resp.choices[0].message.content

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            pattern = r"```(?:[a-zA-Z]+\n)?(.*?)```"
            match = re.findall(pattern, content, re.DOTALL)
            if match:
                code = match[-1].strip()
                history.append(
                    {
                        "role": "assistant",
                        "content": content
                    }
                )
                break
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: Could not find the python code block in the response. Please try again."
                    }
                )

            n += 1

        if n == 3 or not code:
            # remove last message from history
            history.pop()
            os.chdir(self._shared_state.get("default_folder"))
            return "Error: Could not generate a valid file."
        try:
            with open("./tools/" + self.tool_name + ".py", "w") as file:
                file.write(code)

            os.chdir(self._shared_state.get("default_folder"))
            return f'{content}\n\nPlease make sure to now test this tool if possible.'
        except Exception as e:
            os.chdir(self._shared_state.get("default_folder"))
            return f'Error writing to file: {e}'

    @field_validator("requirements", mode="after")
    @classmethod
    def validate_requirements(cls, v):
        if "placeholder" in v:
            raise ValueError("Requirements contain placeholders. "
                             "Please never user placeholders. Instead, implement only the code that you are confident about.")

        # check if code is included in requirements
        pattern = r'(```)((.*\n){5,})(```)'
        if re.search(pattern, v):
            raise ValueError(
                "Requirements contain a code snippet. Please never include code snippets in requirements. "
                "Requirements must be a description of the complete file to be written. You can include specific class, function, and variable names, but not the actual code."
            )

        return v

    @field_validator("details", mode="after")
    @classmethod
    def validate_details(cls, v):
        if len(v) == 0:
            raise ValueError("Details are required. Remember this tool does not have access to other files. Please provide additional details like relevant documentation, error messages, or class, function, and variable names from other files that this file depends on.")
        return v

    @model_validator(mode="after")
    def validate_agency_name(self):
        if not self.agent_name and not self._shared_state.get("agent_name"):
            raise ValueError("Please provide agent name.")

        check_agency_path(self)


if __name__ == "__main__":
    tool = CreateTool(
        requirements="Write a program that takes a list of integers as input and returns the sum of all the integers in the list.",
        mode="write",
        file_path="test.py",
    )
    print(tool.run())


Directory structure:
└── mgrillo75-email-proc-production
    ├── agency-swarm-main
    │   ├── .cursorrules
    │   ├── .github
    │   │   └── workflows
    │   │       ├── close-issues.yml
    │   │       ├── docs.yml
    │   │       ├── publish.yml
    │   │       └── test.yml
    │   ├── agency_swarm
    │   │   ├── agency
    │   │   │   ├── agency.py
    │   │   │   ├── genesis
    │   │   │   │   ├── AgentCreator
    │   │   │   │   │   ├── AgentCreator.py
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   ├── CreateAgentTemplate.py
    │   │   │   │   │   │   ├── ImportAgent.py
    │   │   │   │   │   │   ├── ReadManifesto.py
    │   │   │   │   │   │   └── util
    │   │   │   │   │   │       ├── get_modules.py
    │   │   │   │   │   │       └── __init__.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── GenesisAgency.py
    │   │   │   │   ├── GenesisCEO
    │   │   │   │   │   ├── GenesisCEO.py
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   ├── CreateAgencyFolder.py
    │   │   │   │   │   │   ├── FinalizeAgency.py
    │   │   │   │   │   │   └── ReadRequirements.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── manifesto.md
    │   │   │   │   ├── OpenAPICreator
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── OpenAPICreator.py
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   └── CreateToolsFromOpenAPISpec.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── ToolCreator
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── ToolCreator.py
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   ├── CreateTool.py
    │   │   │   │   │   │   └── TestTool.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── util.py
    │   │   │   │   └── __init__.py
    │   │   │   └── __init__.py
    │   │   ├── agents
    │   │   │   ├── agent.py
    │   │   │   ├── BrowsingAgent
    │   │   │   │   ├── BrowsingAgent.py
    │   │   │   │   ├── instructions.md
    │   │   │   │   ├── requirements.txt
    │   │   │   │   ├── tools
    │   │   │   │   │   ├── ClickElement.py
    │   │   │   │   │   ├── ExportFile.py
    │   │   │   │   │   ├── GoBack.py
    │   │   │   │   │   ├── ReadURL.py
    │   │   │   │   │   ├── Scroll.py
    │   │   │   │   │   ├── SelectDropdown.py
    │   │   │   │   │   ├── SendKeys.py
    │   │   │   │   │   ├── SolveCaptcha.py
    │   │   │   │   │   ├── util
    │   │   │   │   │   │   ├── get_b64_screenshot.py
    │   │   │   │   │   │   ├── highlights.py
    │   │   │   │   │   │   ├── selenium.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   ├── WebPageSummarizer.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── Devid
    │   │   │   │   ├── Devid.py
    │   │   │   │   ├── instructions.md
    │   │   │   │   ├── tools
    │   │   │   │   │   ├── ChangeFile.py
    │   │   │   │   │   ├── CheckCurrentDir.py
    │   │   │   │   │   ├── CommandExecutor.py
    │   │   │   │   │   ├── DirectoryNavigator.py
    │   │   │   │   │   ├── FileMover.py
    │   │   │   │   │   ├── FileReader.py
    │   │   │   │   │   ├── FileWriter.py
    │   │   │   │   │   ├── ListDir.py
    │   │   │   │   │   ├── util
    │   │   │   │   │   │   ├── format_file_deps.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   └── __init__.py
    │   │   │   └── __init__.py
    │   │   ├── cli.py
    │   │   ├── messages
    │   │   │   ├── message_output.py
    │   │   │   └── __init__.py
    │   │   ├── threads
    │   │   │   ├── thread.py
    │   │   │   ├── thread_async.py
    │   │   │   └── __init__.py
    │   │   ├── tools
    │   │   │   ├── BaseTool.py
    │   │   │   ├── oai
    │   │   │   │   ├── CodeInterpreter.py
    │   │   │   │   ├── FileSearch.py
    │   │   │   │   ├── Retrieval.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── send_message
    │   │   │   │   ├── SendMessage.py
    │   │   │   │   ├── SendMessageAsyncThreading.py
    │   │   │   │   ├── SendMessageBase.py
    │   │   │   │   ├── SendMessageQuick.py
    │   │   │   │   ├── SendMessageSwarm.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── ToolFactory.py
    │   │   │   └── __init__.py
    │   │   ├── user
    │   │   │   ├── user.py
    │   │   │   └── __init__.py
    │   │   ├── util
    │   │   │   ├── cli
    │   │   │   │   ├── create_agent_template.py
    │   │   │   │   ├── import_agent.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── errors.py
    │   │   │   ├── files.py
    │   │   │   ├── helpers
    │   │   │   │   ├── get_available_agent_descriptions.py
    │   │   │   │   ├── list_available_agents.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── oai.py
    │   │   │   ├── openapi.py
    │   │   │   ├── schema.py
    │   │   │   ├── shared_state.py
    │   │   │   ├── streaming.py
    │   │   │   ├── validators.py
    │   │   │   └── __init__.py
    │   │   └── __init__.py
    │   ├── docs
    │   │   ├── advanced-usage
    │   │   │   ├── agencies.md
    │   │   │   ├── agents.md
    │   │   │   ├── azure-openai.md
    │   │   │   ├── communication_flows.md
    │   │   │   ├── open-source-models.md
    │   │   │   └── tools.md
    │   │   ├── api.md
    │   │   ├── assets
    │   │   ├── deployment.md
    │   │   ├── examples.md
    │   │   ├── index.md
    │   │   ├── introduction
    │   │   │   └── showcase.md
    │   │   └── quick_start.md
    │   ├── mkdocs.yml
    │   ├── notebooks
    │   │   ├── agency_async.ipynb
    │   │   ├── azure.ipynb
    │   │   ├── genesis_agency.ipynb
    │   │   ├── os_models_with_astra_assistants_api.ipynb
    │   │   └── web_browser_agent.ipynb
    │   ├── pyproject.toml
    │   ├── README.md
    │   ├── requirements.txt
    │   ├── requirements_docs.txt
    │   ├── requirements_test.txt
    │   ├── run_tests.py
    │   ├── setup.py
    │   └── tests
    │       ├── data
    │       │   ├── files
    │       │   │   ├── csv-test.csv
    │       │   │   ├── generated_data.json
    │       │   │   ├── test-docx.docx
    │       │   │   ├── test-html.html
    │       │   │   ├── test-md.md
    │       │   │   ├── test-pdf.pdf
    │       │   │   ├── test-txt.txt
    │       │   │   └── test-xml.xml
    │       │   ├── schemas
    │       │   │   ├── ga4.json
    │       │   │   ├── get-headers-params.json
    │       │   │   ├── get-weather.json
    │       │   │   └── relevance.json
    │       │   └── tools
    │       │       └── ExampleTool1.py
    │       ├── demos
    │       │   ├── demo_gradio.py
    │       │   ├── streaming_demo.py
    │       │   ├── term_demo.py
    │       │   └── __init__.py
    │       ├── test_agency.py
    │       ├── test_communication.py
    │       ├── test_tool_factory.py
    │       └── __init__.py
    ├── EmailProcessingAgency
    │   ├── agency.py
    │   ├── agency_manifesto.md
    │   ├── EmailCategorizationAgent
    │   │   ├── EmailCategorizationAgent.py
    │   │   ├── instructions.md
    │   │   ├── tools
    │   │   │   ├── EmailCategorizer.py
    │   │   │   └── EmailParser.py
    │   │   └── __init__.py
    │   ├── EmailProcessingAgent
    │   │   ├── EmailProcessingAgent.py
    │   │   ├── instructions-old.md
    │   │   ├── instructions.md
    │   │   ├── tools
    │   │   │   ├── EmailProcessor.py
    │   │   │   ├── ErrorHandling.py
    │   │   │   └── OutlookFolderMonitor.py
    │   │   └── __init__.py
    │   ├── error_log.txt
    │   ├── LeadAgent
    │   │   ├── instructions.md
    │   │   ├── LeadAgent.py
    │   │   └── __init__.py
    │   ├── requirements.txt
    │   ├── settings.json
    │   ├── SummaryGenerationAgent
    │   │   ├── instructions.md
    │   │   ├── SummaryGenerationAgent.py
    │   │   ├── tools
    │   │   │   └── SummaryGenerator.py
    │   │   └── __init__.py
    │   └── __init__.py
    ├── letta-main
    │   ├── .dockerignore
    │   ├── .env.example
    │   ├── .gitattributes
    │   ├── .github
    │   │   ├── ISSUE_TEMPLATE
    │   │   │   ├── bug_report.md
    │   │   │   └── feature_request.md
    │   │   ├── pull_request_template.md
    │   │   └── workflows
    │   │       ├── code_style_checks.yml
    │   │       ├── docker-image-nightly.yml
    │   │       ├── docker-image.yml
    │   │       ├── docker-integration-tests.yaml
    │   │       ├── integration_tests.yml
    │   │       ├── letta-web-openapi-saftey.yml
    │   │       ├── letta-web-safety.yml
    │   │       ├── migration-test.yml
    │   │       ├── poetry-publish-nightly.yml
    │   │       ├── poetry-publish.yml
    │   │       ├── test-pip-install.yml
    │   │       ├── tests.yml
    │   │       ├── test_anthropic.yml
    │   │       ├── test_azure.yml
    │   │       ├── test_cli.yml
    │   │       ├── test_examples.yml
    │   │       ├── test_groq.yml
    │   │       ├── test_memgpt_hosted.yml
    │   │       ├── test_ollama.yml
    │   │       ├── test_openai.yml
    │   │       └── test_together.yml
    │   ├── .pre-commit-config.yaml
    │   ├── alembic
    │   │   ├── env.py
    │   │   ├── README
    │   │   ├── script.py.mako
    │   │   └── versions
    │   │       ├── 1c8880d671ee_make_an_blocks_agents_mapping_table.py
    │   │       ├── 9a505cc7eca9_create_a_baseline_migrations.py
    │   │       ├── b6d7ca024aa9_add_agents_tags_table.py
    │   │       ├── c85a3d07c028_move_files_to_orm.py
    │   │       ├── cda66b6cb0d6_move_sources_to_orm.py
    │   │       ├── d14ae606614c_move_organizations_users_tools_to_orm.py
    │   │       ├── f7507eab4bb9_migrate_blocks_to_orm_model.py
    │   │       └── f81ceea2c08d_create_sandbox_config_and_sandbox_env_.py
    │   ├── alembic.ini
    │   ├── assets
    │   ├── CITATION.cff
    │   ├── compose.yaml
    │   ├── configs
    │   │   └── llm_model_configs
    │   │       └── azure-gpt-4o-mini.json
    │   ├── db
    │   │   ├── Dockerfile.simple
    │   │   └── run_postgres.sh
    │   ├── dev-compose.yaml
    │   ├── development.compose.yml
    │   ├── docker-compose-vllm.yaml
    │   ├── Dockerfile
    │   ├── examples
    │   │   ├── Building agents with Letta.ipynb
    │   │   ├── composio_tool_usage.py
    │   │   ├── docs
    │   │   │   ├── agent_advanced.py
    │   │   │   ├── agent_basic.py
    │   │   │   ├── memory.py
    │   │   │   ├── rest_client.py
    │   │   │   └── tools.py
    │   │   ├── helper.py
    │   │   ├── langchain_tool_usage.py
    │   │   ├── notebooks
    │   │   │   ├── Agentic RAG with Letta.ipynb
    │   │   │   ├── Customizing memory management.ipynb
    │   │   │   ├── data
    │   │   │   │   ├── handbook.pdf
    │   │   │   │   ├── shared_memory_system_prompt.txt
    │   │   │   │   └── task_queue_system_prompt.txt
    │   │   │   ├── Introduction to Letta.ipynb
    │   │   │   └── Multi-agent recruiting workflow.ipynb
    │   │   ├── personal_assistant_demo
    │   │   │   ├── charles.txt
    │   │   │   ├── gmail_test_setup.py
    │   │   │   ├── gmail_unread_polling_listener.py
    │   │   │   ├── google_calendar.py
    │   │   │   ├── google_calendar_preset.yaml
    │   │   │   ├── google_calendar_test_setup.py
    │   │   │   ├── personal_assistant.txt
    │   │   │   ├── personal_assistant_preset.yaml
    │   │   │   ├── README.md
    │   │   │   ├── twilio_flask_listener.py
    │   │   │   ├── twilio_messaging.py
    │   │   │   └── twilio_messaging_preset.yaml
    │   │   ├── resend_example
    │   │   │   ├── README.md
    │   │   │   ├── resend_preset.yaml
    │   │   │   └── resend_send_email_env_vars.py
    │   │   ├── swarm
    │   │   │   ├── simple.py
    │   │   │   └── swarm.py
    │   │   ├── tool_rule_usage.py
    │   │   └── tutorials
    │   │       ├── local-python-client.ipynb
    │   │       ├── memgpt-admin-client.ipynb
    │   │       ├── memgpt_paper.pdf
    │   │       ├── memgpt_rag_agent.ipynb
    │   │       └── python-client.ipynb
    │   ├── init.sql
    │   ├── letta
    │   │   ├── agent.py
    │   │   ├── agent_store
    │   │   │   ├── chroma.py
    │   │   │   ├── db.py
    │   │   │   ├── lancedb.py
    │   │   │   ├── milvus.py
    │   │   │   ├── qdrant.py
    │   │   │   └── storage.py
    │   │   ├── benchmark
    │   │   │   ├── benchmark.py
    │   │   │   └── constants.py
    │   │   ├── cli
    │   │   │   ├── cli.py
    │   │   │   ├── cli_config.py
    │   │   │   └── cli_load.py
    │   │   ├── client
    │   │   │   ├── client.py
    │   │   │   ├── streaming.py
    │   │   │   ├── utils.py
    │   │   │   └── __init__.py
    │   │   ├── config.py
    │   │   ├── constants.py
    │   │   ├── credentials.py
    │   │   ├── data_sources
    │   │   │   ├── connectors.py
    │   │   │   └── connectors_helper.py
    │   │   ├── embeddings.py
    │   │   ├── errors.py
    │   │   ├── functions
    │   │   │   ├── functions.py
    │   │   │   ├── function_sets
    │   │   │   │   ├── base.py
    │   │   │   │   └── extras.py
    │   │   │   ├── helpers.py
    │   │   │   ├── schema_generator.py
    │   │   │   └── __init__.py
    │   │   ├── helpers
    │   │   │   ├── tool_rule_solver.py
    │   │   │   └── __init__.py
    │   │   ├── humans
    │   │   │   ├── examples
    │   │   │   │   ├── basic.txt
    │   │   │   │   └── cs_phd.txt
    │   │   │   └── __init__.py
    │   │   ├── interface.py
    │   │   ├── llm_api
    │   │   │   ├── anthropic.py
    │   │   │   ├── azure_openai.py
    │   │   │   ├── azure_openai_constants.py
    │   │   │   ├── cohere.py
    │   │   │   ├── google_ai.py
    │   │   │   ├── helpers.py
    │   │   │   ├── llm_api_tools.py
    │   │   │   ├── mistral.py
    │   │   │   ├── openai.py
    │   │   │   └── __init__.py
    │   │   ├── local_llm
    │   │   │   ├── chat_completion_proxy.py
    │   │   │   ├── constants.py
    │   │   │   ├── function_parser.py
    │   │   │   ├── grammars
    │   │   │   │   ├── gbnf_grammar_generator.py
    │   │   │   │   ├── json.gbnf
    │   │   │   │   ├── json_func_calls_with_inner_thoughts.gbnf
    │   │   │   │   └── __init__.py
    │   │   │   ├── json_parser.py
    │   │   │   ├── koboldcpp
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── llamacpp
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── llm_chat_completion_wrappers
    │   │   │   │   ├── airoboros.py
    │   │   │   │   ├── chatml.py
    │   │   │   │   ├── configurable_wrapper.py
    │   │   │   │   ├── dolphin.py
    │   │   │   │   ├── llama3.py
    │   │   │   │   ├── simple_summary_wrapper.py
    │   │   │   │   ├── wrapper_base.py
    │   │   │   │   ├── zephyr.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── lmstudio
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── ollama
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── README.md
    │   │   │   ├── settings
    │   │   │   │   ├── deterministic_mirostat.py
    │   │   │   │   ├── settings.py
    │   │   │   │   ├── simple.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── utils.py
    │   │   │   ├── vllm
    │   │   │   │   └── api.py
    │   │   │   ├── webui
    │   │   │   │   ├── api.py
    │   │   │   │   ├── legacy_api.py
    │   │   │   │   ├── legacy_settings.py
    │   │   │   │   └── settings.py
    │   │   │   └── __init__.py
    │   │   ├── log.py
    │   │   ├── main.py
    │   │   ├── memory.py
    │   │   ├── metadata.py
    │   │   ├── o1_agent.py
    │   │   ├── openai_backcompat
    │   │   │   ├── openai_object.py
    │   │   │   └── __init__.py
    │   │   ├── orm
    │   │   │   ├── agents_tags.py
    │   │   │   ├── base.py
    │   │   │   ├── block.py
    │   │   │   ├── blocks_agents.py
    │   │   │   ├── enums.py
    │   │   │   ├── errors.py
    │   │   │   ├── file.py
    │   │   │   ├── mixins.py
    │   │   │   ├── organization.py
    │   │   │   ├── sandbox_config.py
    │   │   │   ├── source.py
    │   │   │   ├── sqlalchemy_base.py
    │   │   │   ├── tool.py
    │   │   │   ├── user.py
    │   │   │   ├── __all__.py
    │   │   │   └── __init__.py
    │   │   ├── persistence_manager.py
    │   │   ├── personas
    │   │   │   ├── examples
    │   │   │   │   ├── anna_pa.txt
    │   │   │   │   ├── google_search_persona.txt
    │   │   │   │   ├── memgpt_doc.txt
    │   │   │   │   ├── memgpt_starter.txt
    │   │   │   │   ├── o1_persona.txt
    │   │   │   │   ├── sam.txt
    │   │   │   │   ├── sam_pov.txt
    │   │   │   │   ├── sam_simple_pov_gpt35.txt
    │   │   │   │   └── sqldb
    │   │   │   │       └── test.db
    │   │   │   └── __init__.py
    │   │   ├── prompts
    │   │   │   ├── gpt_summarize.py
    │   │   │   ├── gpt_system.py
    │   │   │   ├── system
    │   │   │   │   ├── memgpt_base.txt
    │   │   │   │   ├── memgpt_chat.txt
    │   │   │   │   ├── memgpt_chat_compressed.txt
    │   │   │   │   ├── memgpt_chat_fstring.txt
    │   │   │   │   ├── memgpt_doc.txt
    │   │   │   │   ├── memgpt_gpt35_extralong.txt
    │   │   │   │   ├── memgpt_intuitive_knowledge.txt
    │   │   │   │   ├── memgpt_modified_chat.txt
    │   │   │   │   └── memgpt_modified_o1.txt
    │   │   │   └── __init__.py
    │   │   ├── providers.py
    │   │   ├── pytest.ini
    │   │   ├── schemas
    │   │   │   ├── agent.py
    │   │   │   ├── agents_tags.py
    │   │   │   ├── api_key.py
    │   │   │   ├── block.py
    │   │   │   ├── blocks_agents.py
    │   │   │   ├── embedding_config.py
    │   │   │   ├── enums.py
    │   │   │   ├── file.py
    │   │   │   ├── health.py
    │   │   │   ├── job.py
    │   │   │   ├── letta_base.py
    │   │   │   ├── letta_message.py
    │   │   │   ├── letta_request.py
    │   │   │   ├── letta_response.py
    │   │   │   ├── llm_config.py
    │   │   │   ├── memory.py
    │   │   │   ├── message.py
    │   │   │   ├── openai
    │   │   │   │   ├── chat_completions.py
    │   │   │   │   ├── chat_completion_request.py
    │   │   │   │   ├── chat_completion_response.py
    │   │   │   │   ├── embedding_response.py
    │   │   │   │   └── openai.py
    │   │   │   ├── organization.py
    │   │   │   ├── passage.py
    │   │   │   ├── sandbox_config.py
    │   │   │   ├── source.py
    │   │   │   ├── tool.py
    │   │   │   ├── tool_rule.py
    │   │   │   ├── usage.py
    │   │   │   └── user.py
    │   │   ├── server
    │   │   │   ├── constants.py
    │   │   │   ├── generate_openapi_schema.sh
    │   │   │   ├── rest_api
    │   │   │   │   ├── app.py
    │   │   │   │   ├── auth
    │   │   │   │   │   ├── index.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── auth_token.py
    │   │   │   │   ├── interface.py
    │   │   │   │   ├── routers
    │   │   │   │   │   ├── openai
    │   │   │   │   │   │   ├── assistants
    │   │   │   │   │   │   │   ├── assistants.py
    │   │   │   │   │   │   │   ├── schemas.py
    │   │   │   │   │   │   │   ├── threads.py
    │   │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   │   ├── chat_completions
    │   │   │   │   │   │   │   ├── chat_completions.py
    │   │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   ├── v1
    │   │   │   │   │   │   ├── agents.py
    │   │   │   │   │   │   ├── blocks.py
    │   │   │   │   │   │   ├── health.py
    │   │   │   │   │   │   ├── jobs.py
    │   │   │   │   │   │   ├── llms.py
    │   │   │   │   │   │   ├── organizations.py
    │   │   │   │   │   │   ├── sandbox_configs.py
    │   │   │   │   │   │   ├── sources.py
    │   │   │   │   │   │   ├── tools.py
    │   │   │   │   │   │   ├── users.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── static_files.py
    │   │   │   │   ├── utils.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── server.py
    │   │   │   ├── startup.sh
    │   │   │   ├── static_files
    │   │   │   │   ├── assets
    │   │   │   │   │   ├── index-3ab03d5b.css
    │   │   │   │   │   └── index-9fa459a2.js
    │   │   │   │   ├── favicon.ico
    │   │   │   │   └── index.html
    │   │   │   ├── utils.py
    │   │   │   ├── ws_api
    │   │   │   │   ├── example_client.py
    │   │   │   │   ├── interface.py
    │   │   │   │   ├── protocol.py
    │   │   │   │   ├── server.py
    │   │   │   │   └── __init__.py
    │   │   │   └── __init__.py
    │   │   ├── services
    │   │   │   ├── agents_tags_manager.py
    │   │   │   ├── blocks_agents_manager.py
    │   │   │   ├── block_manager.py
    │   │   │   ├── organization_manager.py
    │   │   │   ├── sandbox_config_manager.py
    │   │   │   ├── source_manager.py
    │   │   │   ├── tool_execution_sandbox.py
    │   │   │   ├── tool_manager.py
    │   │   │   ├── tool_sandbox_env
    │   │   │   │   └── .gitkeep
    │   │   │   ├── user_manager.py
    │   │   │   └── __init__.py
    │   │   ├── settings.py
    │   │   ├── streaming_interface.py
    │   │   ├── streaming_utils.py
    │   │   ├── system.py
    │   │   ├── utils.py
    │   │   ├── __init__.py
    │   │   └── __main__.py
    │   ├── locust_test.py
    │   ├── main.py
    │   ├── nginx.conf
    │   ├── paper_experiments
    │   │   ├── doc_qa_task
    │   │   │   ├── 0_load_embeddings.sh
    │   │   │   ├── 1_run_docqa.sh
    │   │   │   ├── 2_run_eval.sh
    │   │   │   ├── doc_qa.py
    │   │   │   ├── llm_judge_doc_qa.py
    │   │   │   └── load_wikipedia_embeddings.py
    │   │   ├── nested_kv_task
    │   │   │   ├── data
    │   │   │   │   ├── kv-retrieval-140_keys.jsonl.gz
    │   │   │   │   ├── random_orderings_100_samples_140_indices_1_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_2_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_3_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_4_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_5_levels.jsonl
    │   │   │   │   └── random_orderings_100_samples_140_indices_6_levels.jsonl
    │   │   │   ├── nested_kv.py
    │   │   │   └── run.sh
    │   │   ├── README.md
    │   │   └── utils.py
    │   ├── poetry.lock
    │   ├── PRIVACY.md
    │   ├── pyproject.toml
    │   ├── README.md
    │   ├── scripts
    │   │   ├── migrate_0.3.17.py
    │   │   ├── migrate_0.3.18.py
    │   │   ├── migrate_tools.py
    │   │   ├── pack_docker.sh
    │   │   └── wait_for_service.sh
    │   ├── TERMS.md
    │   └── tests
    │       ├── clear_postgres_db.py
    │       ├── config.py
    │       ├── configs
    │       │   ├── embedding_model_configs
    │       │   │   ├── azure_embed.json
    │       │   │   ├── letta-hosted.json
    │       │   │   ├── local.json
    │       │   │   ├── ollama.json
    │       │   │   └── openai_embed.json
    │       │   ├── letta_hosted.json
    │       │   ├── llm_model_configs
    │       │   │   ├── azure-gpt-4o-mini.json
    │       │   │   ├── claude-3-5-haiku.json
    │       │   │   ├── gemini-pro.json
    │       │   │   ├── groq.json
    │       │   │   ├── letta-hosted.json
    │       │   │   ├── ollama.json
    │       │   │   ├── openai-gpt-4o.json
    │       │   │   ├── together-llama-3-1-405b.json
    │       │   │   └── together-llama-3-70b.json
    │       │   └── openai.json
    │       ├── conftest.py
    │       ├── constants.py
    │       ├── data
    │       │   ├── functions
    │       │   │   └── dump_json.py
    │       │   ├── memgpt-0.2.11
    │       │   │   ├── agents
    │       │   │   │   ├── agent_test
    │       │   │   │   │   ├── agent_state
    │       │   │   │   │   │   ├── 2024-01-11_12_43_57_PM.json
    │       │   │   │   │   │   └── 2024-01-11_12_43_59_PM.json
    │       │   │   │   │   ├── config.json
    │       │   │   │   │   └── persistence_manager
    │       │   │   │   │       ├── 2024-01-11_12_43_57_PM.persistence.pickle
    │       │   │   │   │       ├── 2024-01-11_12_43_59_PM.persistence.pickle
    │       │   │   │   │       └── index
    │       │   │   │   │           └── nodes.pkl
    │       │   │   │   ├── agent_test_attach
    │       │   │   │   │   ├── agent_state
    │       │   │   │   │   │   ├── 2024-01-11_12_42_17_PM.json
    │       │   │   │   │   │   └── 2024-01-11_12_42_19_PM.json
    │       │   │   │   │   ├── config.json
    │       │   │   │   │   └── persistence_manager
    │       │   │   │   │       ├── 2024-01-11_12_42_17_PM.persistence.pickle
    │       │   │   │   │       ├── 2024-01-11_12_42_19_PM.persistence.pickle
    │       │   │   │   │       └── index
    │       │   │   │   │           └── nodes.pkl
    │       │   │   │   └── agent_test_empty_archival
    │       │   │   │       ├── agent_state
    │       │   │   │       │   ├── 2024-01-11_12_44_32_PM.json
    │       │   │   │       │   └── 2024-01-11_12_44_33_PM.json
    │       │   │   │       ├── config.json
    │       │   │   │       └── persistence_manager
    │       │   │   │           ├── 2024-01-11_12_44_32_PM.persistence.pickle
    │       │   │   │           ├── 2024-01-11_12_44_33_PM.persistence.pickle
    │       │   │   │           └── index
    │       │   │   │               └── nodes.pkl
    │       │   │   ├── archival
    │       │   │   │   └── test
    │       │   │   │       └── nodes.pkl
    │       │   │   └── config
    │       │   ├── memgpt-0.3.17
    │       │   │   └── sqlite.db
    │       │   ├── memgpt_paper.pdf
    │       │   └── test.txt
    │       ├── helpers
    │       │   ├── client_helper.py
    │       │   ├── endpoints_helper.py
    │       │   └── utils.py
    │       ├── integration_test_summarizer.py
    │       ├── pytest.ini
    │       ├── test_agent_tool_graph.py
    │       ├── test_autogen_integration.py
    │       ├── test_base_functions.py
    │       ├── test_cli.py
    │       ├── test_client.py
    │       ├── test_client_legacy.py
    │       ├── test_concurrent_connections.py
    │       ├── test_different_embedding_size.py
    │       ├── test_function_parser.py
    │       ├── test_json_parsers.py
    │       ├── test_local_client.py
    │       ├── test_managers.py
    │       ├── test_memory.py
    │       ├── test_model_letta_perfomance.py
    │       ├── test_new_cli.py
    │       ├── test_o1_agent.py
    │       ├── test_openai_client.py
    │       ├── test_persistence.py
    │       ├── test_providers.py
    │       ├── test_schema_generator.py
    │       ├── test_server.py
    │       ├── test_storage.py
    │       ├── test_stream_buffer_readers.py
    │       ├── test_summarize.py
    │       ├── test_tool_execution_sandbox.py
    │       ├── test_tool_rule_solver.py
    │       ├── test_tool_sandbox
    │       │   └── .gitkeep
    │       ├── test_utils.py
    │       ├── test_websocket_server.py
    │       ├── utils.py
    │       └── __init__.py
    └── settings.json


class Agency:
    def __init__(self,
                 agency_chart: List,
                 shared_instructions: str = "",
                 shared_files: Union[str, List[str]] = None,
                 async_mode: Literal['threading', "tools_threading"] = None,
                 send_message_tool_class: Type[SendMessageBase] = SendMessage,
                 settings_path: str = "./settings.json",
                 settings_callbacks: SettingsCallbacks = None,
                 threads_callbacks: ThreadsCallbacks = None,
                 temperature: float = 0.3,
                 top_p: float = 1.0,
                 max_prompt_tokens: int = None,
                 max_completion_tokens: int = None,
                 truncation_strategy: dict = None,
                 ):
        """
        Initializes the Agency object, setting up agents, threads, and core functionalities.
        
        Parameters:
            agency_chart: The structure defining the hierarchy and interaction of agents within the agency.
            shared_instructions (str, optional): A path to a file containing shared instructions for all agents. Defaults to an empty string.
            shared_files (Union[str, List[str]], optional): A path to a folder or a list of folders containing shared files for all agents. Defaults to None.
            async_mode (str, optional): Specifies the mode for asynchronous processing. In "threading" mode, all sub-agents run in separate threads. In "tools_threading" mode, all tools run in separate threads, but agents do not. Defaults to None.
            send_message_tool_class (Type[SendMessageBase], optional): The class to use for the send_message tool. For async communication, use `SendMessageAsyncThreading`. Defaults to SendMessage.
            settings_path (str, optional): The path to the settings file for the agency. Must be json. If file does not exist, it will be created. Defaults to None.
            settings_callbacks (SettingsCallbacks, optional): A dictionary containing functions to load and save settings for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            threads_callbacks (ThreadsCallbacks, optional): A dictionary containing functions to load and save threads for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            temperature (float, optional): The temperature value to use for the agents. Agent-specific values will override this. Defaults to 0.3.
            top_p (float, optional): The top_p value to use for the agents. Agent-specific values will override this. Defaults to None.
            max_prompt_tokens (int, optional): The maximum number of tokens allowed in the prompt for each agent. Agent-specific values will override this. Defaults to None.
            max_completion_tokens (int, optional): The maximum number of tokens allowed in the completion for each agent. Agent-specific values will override this. Defaults to None.
            truncation_strategy (dict, optional): The truncation strategy to use for the completion for each agent. Agent-specific values will override this. Defaults to None.
        """
        self.ceo = None
        self.user = User()
        self.agents = []
        self.agents_and_threads = {}
        self.main_recipients = []
        self.main_thread = None
        self.recipient_agents = None  # for autocomplete
        self.shared_files = shared_files if shared_files else []
        self.async_mode = async_mode
        self.send_message_tool_class = send_message_tool_class
        self.settings_path = settings_path
        self.settings_callbacks = settings_callbacks
        self.threads_callbacks = threads_callbacks
        self.temperature = temperature
        self.top_p = top_p
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.truncation_strategy = truncation_strategy

        # set thread type based send_message_tool_class async mode
        if hasattr(send_message_tool_class.ToolConfig, "async_mode") and send_message_tool_class.ToolConfig.async_mode:
            self._thread_type = ThreadAsync
        else:
            self._thread_type = Thread  

        if self.async_mode == "threading":
            from agency_swarm.tools.send_message import SendMessageAsyncThreading
            print("Warning: 'threading' mode is deprecated. Please use send_message_tool_class = SendMessageAsyncThreading to use async communication.")
            self.send_message_tool_class = SendMessageAsyncThreading
        elif self.async_mode == "tools_threading":
            Thread.async_mode = "tools_threading"
            print("Warning: 'tools_threading' mode is deprecated. Use tool.ToolConfig.async_mode = 'threading' instead.")
        elif self.async_mode is None:
            pass
        else:
            raise Exception("Please select async_mode = 'threading' or 'tools_threading'.")

        if os.path.isfile(os.path.join(self._get_class_folder_path(), shared_instructions)):
            self._read_instructions(os.path.join(self._get_class_folder_path(), shared_instructions))
        elif os.path.isfile(shared_instructions):
            self._read_instructions(shared_instructions)
        else:
            self.shared_instructions = shared_instructions

        self.shared_state = SharedState()

        self._parse_agency_chart(agency_chart)
        self._init_threads()
        self._create_special_tools()
        self._init_agents()

    def get_completion(self, message: str,
                       message_files: List[str] = None,
                       yield_messages: bool = False,
                       recipient_agent: Agent = None,
                       additional_instructions: str = None,
                       attachments: List[dict] = None,
                       tool_choice: dict = None,
                       verbose: bool = False,
                       response_format: dict = None):
        """
        Retrieves the completion for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            yield_messages (bool, optional): Flag to determine if intermediate messages should be yielded. Defaults to True.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
            response_format (dict, optional): The response format to use for the completion.

        Returns:
            Generator or final response: Depending on the 'yield_messages' flag, this method returns either a generator yielding intermediate messages or the final response from the main thread.
        """
        if verbose and yield_messages:
            raise Exception("Verbose mode is not compatible with yield_messages=True")
        
        res = self.main_thread.get_completion(message=message,
                                               message_files=message_files,
                                               attachments=attachments,
                                               recipient_agent=recipient_agent,
                                               additional_instructions=additional_instructions,
                                               tool_choice=tool_choice,
                                               yield_messages=yield_messages or verbose,
                                               response_format=response_format)
        
        if not yield_messages or verbose:
            while True:
                try:
                    message = next(res)
                    if verbose:
                        message.cprint()
                except StopIteration as e:
                    return e.value

        return res


    def get_completion_stream(self,
                              message: str,
                              event_handler: type(AgencyEventHandler),
                              message_files: List[str] = None,
                              recipient_agent: Agent = None,
                              additional_instructions: str = None,
                              attachments: List[dict] = None,
                              tool_choice: dict = None,
                              response_format: dict = None):
        """
        Generates a stream of completions for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            event_handler (type(AgencyEventHandler)): The event handler class to handle the completion stream. https://github.com/openai/openai-python/blob/main/helpers.md
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.

        Returns:
            Final response: Final response from the main thread.
        """
        if not inspect.isclass(event_handler):
            raise Exception("Event handler must not be an instance.")

        res = self.main_thread.get_completion_stream(message=message,
                                                      message_files=message_files,
                                                      event_handler=event_handler,
                                                      attachments=attachments,
                                                      recipient_agent=recipient_agent,
                                                      additional_instructions=additional_instructions,
                                                      tool_choice=tool_choice,
                                                      response_format=response_format)

        while True:
            try:
                next(res)
            except StopIteration as e:
                event_handler.on_all_streams_end()

                return e.value
                
    def get_completion_parse(self, message: str,
                             response_format: Type[T],
                             message_files: List[str] = None,
                             recipient_agent: Agent = None,
                             additional_instructions: str = None,
                             attachments: List[dict] = None,
                             tool_choice: dict = None,
                             verbose: bool = False) -> T:
        """
        Retrieves the completion for a given message from the main thread and parses the response using the provided pydantic model.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            response_format (type(BaseModel)): The response format to use for the completion. 
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
        
        Returns:
            Final response: The final response from the main thread, parsed using the provided pydantic model.
        """
        response_model = None
        if isinstance(response_format, type):
            response_model = response_format
            response_format = type_to_response_format_param(response_format)

        res = self.get_completion(message=message,
                            message_files=message_files,
                            recipient_agent=recipient_agent,
                            additional_instructions=additional_instructions,
                            attachments=attachments,
                            tool_choice=tool_choice,
                            response_format=response_format,
                            verbose=verbose)
        
        try:
            return response_model.model_validate_json(res)
        except:
            parsed_res = json.loads(res)
            if 'refusal' in parsed_res:
                raise RefusalError(parsed_res['refusal'])
            else:
                raise Exception("Failed to parse response: " + res)

    def demo_gradio(self, height=450, dark_mode=True, **kwargs):
        """
        Launches a Gradio-based demo interface for the agency chatbot.

        Parameters:
            height (int, optional): The height of the chatbot widget in the Gradio interface. Default is 600.
            dark_mode (bool, optional): Flag to determine if the interface should be displayed in dark mode. Default is True.
            **kwargs: Additional keyword arguments to be passed to the Gradio interface.
        This method sets up and runs a Gradio interface, allowing users to interact with the agency's chatbot. It includes a text input for the user's messages and a chatbot interface for displaying the conversation. The method handles user input and chatbot responses, updating the interface dynamically.
        """

        try:
            import gradio as gr
        except ImportError:
            raise Exception("Please install gradio: pip install gradio")

        js = """function () {
          gradioURL = window.location.href
          if (!gradioURL.endsWith('?__theme={theme}')) {
            window.location.replace(gradioURL + '?__theme={theme}');
          }
        }"""

        if dark_mode:
            js = js.replace("{theme}", "dark")
        else:
            js = js.replace("{theme}", "light")

        attachments = []
        images = []
        message_file_names = None
        uploading_files = False
        recipient_agent_names = [agent.name for agent in self.main_recipients]
        recipient_agent = self.main_recipients[0]

        with gr.Blocks(js=js) as demo:
            chatbot_queue = queue.Queue()
            chatbot = gr.Chatbot(height=height)
            with gr.Row():
                with gr.Column(scale=9):
                    dropdown = gr.Dropdown(label="Recipient Agent", choices=recipient_agent_names,
                                           value=recipient_agent.name)
                    msg = gr.Textbox(label="Your Message", lines=4)
                with gr.Column(scale=1):
                    file_upload = gr.Files(label="OpenAI Files", type="filepath")
            button = gr.Button(value="Send", variant="primary")

            def handle_dropdown_change(selected_option):
                nonlocal recipient_agent
                recipient_agent = self._get_agent_by_name(selected_option)

            def handle_file_upload(file_list):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                uploading_files = True
                attachments = []
                message_file_names = []
                if file_list:
                    try:
                        for file_obj in file_list:
                            purpose = get_file_purpose(file_obj.name)

                            with open(file_obj.name, 'rb') as f:
                                # Upload the file to OpenAI
                                file = self.main_thread.client.files.create(
                                    file=f,
                                    purpose=purpose
                                )

                            if purpose == "vision":
                                images.append({
                                    "type": "image_file",
                                    "image_file": {"file_id": file.id}
                                })
                            else:
                                attachments.append({
                                    "file_id": file.id,
                                    "tools": get_tools(file.filename)
                                })

                            message_file_names.append(file.filename)
                            print(f"Uploaded file ID: {file.id}")
                        return attachments
                    except Exception as e:
                        print(f"Error: {e}")
                        return str(e)
                    finally:
                        uploading_files = False

                uploading_files = False
                return "No files uploaded"

            def user(user_message, history):
                if not user_message.strip():
                    return user_message, history
                
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                nonlocal attachments
                nonlocal recipient_agent

                # Check if attachments contain file search or code interpreter types
                def check_and_add_tools_in_attachments(attachments, recipient_agent):
                    for attachment in attachments:
                        for tool in attachment.get("tools", []):
                            if tool["type"] == "file_search":
                                if not any(isinstance(t, FileSearch) for t in recipient_agent.tools):
                                    # Add FileSearch tool if it does not exist
                                    recipient_agent.tools.append(FileSearch)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added FileSearch tool to recipient agent to analyze the file.")
                            elif tool["type"] == "code_interpreter":
                                if not any(isinstance(t, CodeInterpreter) for t in recipient_agent.tools):
                                    # Add CodeInterpreter tool if it does not exist
                                    recipient_agent.tools.append(CodeInterpreter)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added CodeInterpreter tool to recipient agent to analyze the file.")
                    return None

                check_and_add_tools_in_attachments(attachments, recipient_agent)

                if history is None:
                    history = []

                original_user_message = user_message

                # Append the user message with a placeholder for bot response
                if recipient_agent:
                    user_message = f"👤 User 🗣️ @{recipient_agent.name}:\n" + user_message.strip()
                else:
                    user_message = f"👤 User:" + user_message.strip()

                nonlocal message_file_names
                if message_file_names:
                    user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

                return original_user_message, history + [[user_message, None]]

            class GradioEventHandler(AgencyEventHandler):
                message_output = None

                @classmethod
                def change_recipient_agent(cls, recipient_agent_name):
                    nonlocal chatbot_queue
                    chatbot_queue.put("[change_recipient_agent]")
                    chatbot_queue.put(recipient_agent_name)

                @override
                def on_message_created(self, message: Message) -> None:
                    if message.role == "user":
                        full_content = ""
                        for content in message.content:
                            if content.type == "image_file":
                                full_content += f"🖼️ Image File: {content.image_file.file_id}\n"
                                continue

                            if content.type == "image_url":
                                full_content += f"\n{content.image_url.url}\n"
                                continue

                            if content.type == "text":
                                full_content += content.text.value + "\n"


                        self.message_output = MessageOutput("text", self.agent_name, self.recipient_agent_name,
                                                            full_content)

                    else:
                        self.message_output = MessageOutput("text", self.recipient_agent_name, self.agent_name,
                                                            "")

                    chatbot_queue.put("[new_message]")
                    chatbot_queue.put(self.message_output.get_formatted_content())

                @override
                def on_text_delta(self, delta, snapshot):
                    chatbot_queue.put(delta.value)

                @override
                def on_tool_call_created(self, tool_call: ToolCall):
                    if isinstance(tool_call, dict):
                        if "type" not in tool_call:
                            tool_call["type"] = "function"
                        
                        if tool_call["type"] == "function":
                            tool_call = FunctionToolCall(**tool_call)
                        elif tool_call["type"] == "code_interpreter":
                            tool_call = CodeInterpreterToolCall(**tool_call)
                        elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                            tool_call = FileSearchToolCall(**tool_call)
                        else:
                            raise ValueError("Invalid tool call type: " + tool_call["type"])

                    # TODO: add support for code interpreter and retrieval tools
                    if tool_call.type == "function":
                        chatbot_queue.put("[new_message]")
                        self.message_output = MessageOutput("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))
                        chatbot_queue.put(self.message_output.get_formatted_header() + "\n")

                @override
                def on_tool_call_done(self, snapshot: ToolCall):
                    if isinstance(snapshot, dict):
                        if "type" not in snapshot:
                            snapshot["type"] = "function"
                        
                        if snapshot["type"] == "function":
                            snapshot = FunctionToolCall(**snapshot)
                        elif snapshot["type"] == "code_interpreter":
                            snapshot = CodeInterpreterToolCall(**snapshot)
                        elif snapshot["type"] == "file_search":
                            snapshot = FileSearchToolCall(**snapshot)
                        else:
                            raise ValueError("Invalid tool call type: " + snapshot["type"])
                        
                    self.message_output = None

                    # TODO: add support for code interpreter and retrieval tools
                    if snapshot.type != "function":
                        return

                    chatbot_queue.put(str(snapshot.function))

                    if snapshot.function.name == "SendMessage":
                        try:
                            args = eval(snapshot.function.arguments)
                            recipient = args["recipient"]
                            self.message_output = MessageOutput("text", self.recipient_agent_name, recipient,
                                                                args["message"])

                            chatbot_queue.put("[new_message]")
                            chatbot_queue.put(self.message_output.get_formatted_content())
                        except Exception as e:
                            pass

                    self.message_output = None

                @override
                def on_run_step_done(self, run_step: RunStep) -> None:
                    if run_step.type == "tool_calls":
                        for tool_call in run_step.step_details.tool_calls:
                            if tool_call.type != "function":
                                continue

                            if tool_call.function.name == "SendMessage":
                                continue

                            self.message_output = None
                            chatbot_queue.put("[new_message]")

                            self.message_output = MessageOutput("function_output", tool_call.function.name,
                                                                self.recipient_agent_name,
                                                                tool_call.function.output)

                            chatbot_queue.put(self.message_output.get_formatted_header() + "\n")
                            chatbot_queue.put(tool_call.function.output)

                @override
                @classmethod
                def on_all_streams_end(cls):
                    cls.message_output = None
                    chatbot_queue.put("[end]")

            def bot(original_message, history):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal recipient_agent
                nonlocal recipient_agent_names
                nonlocal images
                nonlocal uploading_files

                if not original_message:
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                if uploading_files:
                    history.append([None, "Uploading files... Please wait."])
                    yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                print("Message files: ", attachments)
                print("Images: ", images)
                
                if images and len(images) > 0:
                    original_message = [
                        {
                            "type": "text",
                            "text": original_message,
                        },
                        *images
                    ]


                completion_thread = threading.Thread(target=self.get_completion_stream, args=(
                    original_message, GradioEventHandler, [], recipient_agent, "", attachments, None))
                completion_thread.start()

                attachments = []
                message_file_names = []
                images = []
                uploading_files = False

                new_message = True
                while True:
                    try:
                        bot_message = chatbot_queue.get(block=True)

                        if bot_message == "[end]":
                            completion_thread.join()
                            break

                        if bot_message == "[new_message]":
                            new_message = True
                            continue

                        if bot_message == "[change_recipient_agent]":
                            new_agent_name = chatbot_queue.get(block=True)
                            recipient_agent = self._get_agent_by_name(new_agent_name)
                            yield "", history, gr.update(value=new_agent_name, choices=set([*recipient_agent_names, recipient_agent.name]))
                            continue

                        if new_message:
                            history.append([None, bot_message])
                            new_message = False
                        else:
                            history[-1][1] += bot_message

                        yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    except queue.Empty:
                        break

            button.click(
                user,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot]
            ).then(
                bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
            )
            dropdown.change(handle_dropdown_change, dropdown)
            file_upload.change(handle_file_upload, file_upload)
            msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
                bot, [msg, chatbot], [msg, chatbot, dropdown]
            )

            # Enable queuing for streaming intermediate outputs
            demo.queue(default_concurrency_limit=10)

        # Launch the demo
        demo.launch(**kwargs)
        return demo

    def _recipient_agent_completer(self, text, state):
        """
        Autocomplete completer for recipient agent names.
        """
        options = [agent for agent in self.recipient_agents if agent.lower().startswith(text.lower())]
        if state < len(options):
            return options[state]
        else:
            return None

    def _setup_autocomplete(self):
        """
        Sets up readline with the completer function.
        """
        try:
            import readline
        except ImportError:
            # Attempt to import pyreadline for Windows compatibility
            try:
                import pyreadline as readline
            except ImportError:
                print(
                    "Module 'readline' not found. Autocomplete will not work. If you are using Windows, try installing 'pyreadline3'.")
                return

        if not readline:
            return

        try:
            readline.set_completer(self._recipient_agent_completer)
            readline.parse_and_bind('tab: complete')
        except Exception as e:
            print(f"Error setting up autocomplete for agents in terminal: {e}. Autocomplete will not work.")

    def run_demo(self):
        """
        Executes agency in the terminal with autocomplete for recipient agent names.
        """
        outer_self = self
        from agency_swarm import AgencyEventHandler
        class TermEventHandler(AgencyEventHandler):
            message_output = None

            @override
            def on_message_created(self, message: Message) -> None:
                if message.role == "user":
                    self.message_output = MessageOutputLive("text", self.agent_name, self.recipient_agent_name,
                                                            "")
                    self.message_output.cprint_update(message.content[0].text.value)
                else:
                    self.message_output = MessageOutputLive("text", self.recipient_agent_name, self.agent_name, "")

            @override
            def on_message_done(self, message: Message) -> None:
                self.message_output = None

            @override
            def on_text_delta(self, delta, snapshot):
                self.message_output.cprint_update(snapshot.value)

            @override
            def on_tool_call_created(self, tool_call):
                if isinstance(tool_call, dict):
                    if "type" not in tool_call:
                        tool_call["type"] = "function"
                    
                    if tool_call["type"] == "function":
                        tool_call = FunctionToolCall(**tool_call)
                    elif tool_call["type"] == "code_interpreter":
                        tool_call = CodeInterpreterToolCall(**tool_call)
                    elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                        tool_call = FileSearchToolCall(**tool_call)
                    else:
                        raise ValueError("Invalid tool call type: " + tool_call["type"])

                # TODO: add support for code interpreter and retirieval tools

                if tool_call.type == "function":
                    self.message_output = MessageOutputLive("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))

            @override
            def on_tool_call_delta(self, delta, snapshot):
                if isinstance(snapshot, dict):
                    if "type" not in snapshot:
                        snapshot["type"] = "function"
                    
                    if snapshot["type"] == "function":
                        snapshot = FunctionToolCall(**snapshot)
                    elif snapshot["type"] == "code_interpreter":
                        snapshot = CodeInterpreterToolCall(**snapshot)
                    elif snapshot["type"] == "file_search":
                        snapshot = FileSearchToolCall(**snapshot)
                    else:
                        raise ValueError("Invalid tool call type: " + snapshot["type"])
                    
                self.message_output.cprint_update(str(snapshot.function))

            @override
            def on_tool_call_done(self, snapshot):
                self.message_output = None

                # TODO: add support for code interpreter and retrieval tools
                if snapshot.type != "function":
                    return

                if snapshot.function.name == "SendMessage" and not (hasattr(outer_self.send_message_tool_class.ToolConfig, 'output_as_result') and outer_self.send_message_tool_class.ToolConfig.output_as_result):
                    try:
                        args = eval(snapshot.function.arguments)
                        recipient = args["recipient"]
                        self.message_output = MessageOutputLive("text", self.recipient_agent_name, recipient,
                                                                "")

                        self.message_output.cprint_update(args["message"])
                    except Exception as e:
                        pass

                self.message_output = None

            @override
            def on_run_step_done(self, run_step: RunStep) -> None:
                if run_step.type == "tool_calls":
                    for tool_call in run_step.step_details.tool_calls:
                        if tool_call.type != "function":
                            continue

                        if tool_call.function.name == "SendMessage":
                            continue

                        self.message_output = None
                        self.message_output = MessageOutputLive("function_output", tool_call.function.name,
                                                                self.recipient_agent_name, tool_call.function.output)
                        self.message_output.cprint_update(tool_call.function.output)

                    self.message_output = None

            @override
            def on_end(self):
                self.message_output = None

        self.recipient_agents = [str(agent.name) for agent in self.main_recipients]

        self._setup_autocomplete()  # Prepare readline for autocomplete

        while True:
            console.rule()
            text = input("👤 USER: ")

            if not text:
                continue

            if text.lower() == "exit":
                break

            recipient_agent = None
            if "@" in text:
                recipient_agent = text.split("@")[1].split(" ")[0]
                text = text.replace(f"@{recipient_agent}", "").strip()
                try:
                    recipient_agent = \
                        [agent for agent in self.recipient_agents if agent.lower() == recipient_agent.lower()][0]
                    recipient_agent = self._get_agent_by_name(recipient_agent)
                except Exception as e:
                    print(f"Recipient agent {recipient_agent} not found.")
                    continue

            self.get_completion_stream(message=text, event_handler=TermEventHandler, recipient_agent=recipient_agent)

    def get_customgpt_schema(self, url: str):
        """Returns the OpenAPI schema for the agency from the CEO agent, that you can use to integrate with custom gpts.

        Parameters:
            url (str): Your server url where the api will be hosted.
        """

        return self.ceo.get_openapi_schema(url)

    def plot_agency_chart(self):
        pass

    def _init_agents(self):
        """
        Initializes all agents in the agency with unique IDs, shared instructions, and OpenAI models.

        This method iterates through each agent in the agency, assigns a unique ID, adds shared instructions, and initializes the OpenAI models for each agent.

        There are no input parameters.

        There are no output parameters as this method is used for internal initialization purposes within the Agency class.
        """
        if self.settings_callbacks:
            loaded_settings = self.settings_callbacks["load"]()
            with open(self.settings_path, 'w') as f:
                json.dump(loaded_settings, f, indent=4)

        for agent in self.agents:
            if "temp_id" in agent.id:
                agent.id = None

            agent.add_shared_instructions(self.shared_instructions)
            agent.settings_path = self.settings_path

            if self.shared_files:
                if isinstance(self.shared_files, str):
                    self.shared_files = [self.shared_files]

                if isinstance(agent.files_folder, str):
                    agent.files_folder = [agent.files_folder]
                    agent.files_folder += self.shared_files
                elif isinstance(agent.files_folder, list):
                    agent.files_folder += self.shared_files

            if self.temperature is not None and agent.temperature is None:
                agent.temperature = self.temperature
            if self.top_p and agent.top_p is None:
                agent.top_p = self.top_p
            if self.max_prompt_tokens is not None and agent.max_prompt_tokens is None:
                agent.max_prompt_tokens = self.max_prompt_tokens
            if self.max_completion_tokens is not None and agent.max_completion_tokens is None:
                agent.max_completion_tokens = self.max_completion_tokens
            if self.truncation_strategy is not None and agent.truncation_strategy is None:
                agent.truncation_strategy = self.truncation_strategy
            
            if not agent.shared_state:
                agent.shared_state = self.shared_state

            agent.init_oai()

        if self.settings_callbacks:
            with open(self.agents[0].get_settings_path(), 'r') as f:
                settings = f.read()
            settings = json.loads(settings)
            self.settings_callbacks["save"](settings)

    def _init_threads(self):
        """
        Initializes threads for communication between agents within the agency.

        This method creates Thread objects for each pair of interacting agents as defined in the agents_and_threads attribute of the Agency. Each thread facilitates communication and task execution between an agent and its designated recipient agent.

        No input parameters.

        Output Parameters:
            This method does not return any value but updates the agents_and_threads attribute with initialized Thread objects.
        """
        self.main_thread = Thread(self.user, self.ceo)

        # load thread ids
        loaded_thread_ids = {}
        if self.threads_callbacks:
            loaded_thread_ids = self.threads_callbacks["load"]()
            if "main_thread" in loaded_thread_ids and loaded_thread_ids["main_thread"]:
                self.main_thread.id = loaded_thread_ids["main_thread"]
            else:
                self.main_thread.init_thread()

        # Save main_thread into agents_and_threads
        self.agents_and_threads["main_thread"] = self.main_thread

        # initialize threads
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            for other_agent, items in threads.items():
                # create thread class
                self.agents_and_threads[agent_name][other_agent] = self._thread_type(
                    self._get_agent_by_name(items["agent"]),
                    self._get_agent_by_name(
                        items["recipient_agent"]))

                # load thread id if available
                if agent_name in loaded_thread_ids and other_agent in loaded_thread_ids[agent_name]:
                    self.agents_and_threads[agent_name][other_agent].id = loaded_thread_ids[agent_name][other_agent]
                # init threads if threre are threads callbacks so the ids are saved for later use
                elif self.threads_callbacks:
                    self.agents_and_threads[agent_name][other_agent].init_thread()

        # save thread ids
        if self.threads_callbacks:
            loaded_thread_ids = {}
            for agent_name, threads in self.agents_and_threads.items():
                if agent_name == "main_thread":
                    continue
                loaded_thread_ids[agent_name] = {}
                for other_agent, thread in threads.items():
                    loaded_thread_ids[agent_name][other_agent] = thread.id

            loaded_thread_ids["main_thread"] = self.main_thread.id

            self.threads_callbacks["save"](loaded_thread_ids)

    def _parse_agency_chart(self, agency_chart):
        """
        Parses the provided agency chart to initialize and organize agents within the agency.
        
        Parameters:
            agency_chart: A structure representing the hierarchical organization of agents within the agency.
                    It can contain Agent objects and lists of Agent objects.
        
        This method iterates through each node in the agency chart. If a node is an Agent, it is set as the CEO if not already assigned.
        If a node is a list, it iterates through the agents in the list, adding them to the agency and establishing communication
        threads between them. It raises an exception if the agency chart is invalid or if multiple CEOs are defined.
        """
        if not isinstance(agency_chart, list):
            raise Exception("Invalid agency chart.")

        if len(agency_chart) == 0:
            raise Exception("Agency chart cannot be empty.")

        for node in agency_chart:
            if isinstance(node, Agent):
                if not self.ceo:
                    self.ceo = node
                    self._add_agent(self.ceo)
                else:
                    self._add_agent(node)
                self._add_main_recipient(node)

            elif isinstance(node, list):
                for i, agent in enumerate(node):
                    if not isinstance(agent, Agent):
                        raise Exception("Invalid agency chart.")

                    index = self._add_agent(agent)

                    if i == len(node) - 1:
                        continue

                    if agent.name not in self.agents_and_threads.keys():
                        self.agents_and_threads[agent.name] = {}

                    if i < len(node) - 1:
                        other_agent = node[i + 1]
                        if other_agent.name == agent.name:
                            continue
                        if other_agent.name not in self.agents_and_threads[agent.name].keys():
                            self.agents_and_threads[agent.name][other_agent.name] = {
                                "agent": agent.name,
                                "recipient_agent": other_agent.name,
                            }
            else:
                raise Exception("Invalid agency chart.")

    def _add_agent(self, agent):
        """
        Adds an agent to the agency, assigning a temporary ID if necessary.

        Parameters:
            agent (Agent): The agent to be added to the agency.

        Returns:
            int: The index of the added agent within the agency's agents list.

        This method adds an agent to the agency's list of agents. If the agent does not have an ID, it assigns a temporary unique ID. It checks for uniqueness of the agent's name before addition. The method returns the index of the agent in the agency's agents list, which is used for referencing the agent within the agency.
        """
        if not agent.id:
            # assign temp id
            agent.id = "temp_id_" + str(uuid.uuid4())
        if agent.id not in self._get_agent_ids():
            if agent.name in self._get_agent_names():
                raise Exception("Agent names must be unique.")
            self.agents.append(agent)
            return len(self.agents) - 1
        else:
            return self._get_agent_ids().index(agent.id)

    def _add_main_recipient(self, agent):
        """
        Adds an agent to the agency's list of main recipients.

        Parameters:
            agent (Agent): The agent to be added to the agency's list of main recipients.

        This method adds an agent to the agency's list of main recipients. These are agents that can be directly contacted by the user.
        """
        main_recipient_ids = [agent.id for agent in self.main_recipients]

        if agent.id not in main_recipient_ids:
            self.main_recipients.append(agent)

    def _read_instructions(self, path):
        """
        Reads shared instructions from a specified file and stores them in the agency.

        Parameters:
            path (str): The file path from which to read the shared instructions.

        This method opens the file located at the given path, reads its contents, and stores these contents in the 'shared_instructions' attribute of the agency. This is used to provide common guidelines or instructions to all agents within the agency.
        """
        path = path
        with open(path, 'r') as f:
            self.shared_instructions = f.read()

    def _create_special_tools(self):
        """
        Creates and assigns 'SendMessage' tools to each agent based on the agency's structure.

        This method iterates through the agents and threads in the agency, creating SendMessage tools for each agent. These tools enable agents to send messages to other agents as defined in the agency's structure. The SendMessage tools are tailored to the specific recipient agents that each agent can communicate with.

        No input parameters.

        No output parameters; this method modifies the agents' toolset internally.
        """
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            recipient_names = list(threads.keys())
            recipient_agents = self._get_agents_by_names(recipient_names)
            if len(recipient_agents) == 0:
                continue
            agent = self._get_agent_by_name(agent_name)
            agent.add_tool(self._create_send_message_tool(agent, recipient_agents))
            if self._thread_type == ThreadAsync:
                agent.add_tool(self._create_get_response_tool(agent, recipient_agents))

    def _create_send_message_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a SendMessage tool to enable an agent to send messages to specified recipient agents.


        Parameters:
            agent (Agent): The agent who will be sending messages.
            recipient_agents (List[Agent]): A list of recipient agents who can receive messages.

        Returns:
            SendMessage: A SendMessage tool class that is dynamically created and configured for the given agent and its recipient agents. This tool allows the agent to send messages to the specified recipients, facilitating inter-agent communication within the agency.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        agent_descriptions = ""
        for recipient_agent in recipient_agents:
            if not recipient_agent.description:
                continue
            agent_descriptions += recipient_agent.name + ": "
            agent_descriptions += recipient_agent.description + "\n"

        class SendMessage(self.send_message_tool_class):
            recipient: recipients = Field(..., description=agent_descriptions)

            @field_validator('recipient')
            @classmethod
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

        SendMessage._caller_agent = agent
        SendMessage._agents_and_threads = self.agents_and_threads

        return SendMessage

    def _create_get_response_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a CheckStatus tool to enable an agent to check the status of a task with a specified recipient agent.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        outer_self = self

        class GetResponse(BaseTool):
            """This tool allows you to check the status of a task or get a response from a specified recipient agent, if the task has been completed. You must always use 'SendMessage' tool with the designated agent first."""
            recipient: recipients = Field(...,
                                          description=f"Recipient agent that you want to check the status of. Valid recipients are: {recipient_names}")

            @field_validator('recipient')
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

            def run(self):
                thread = outer_self.agents_and_threads[self._caller_agent.name][self.recipient.value]

                return thread.check_status()

        GetResponse._caller_agent = agent

        return GetResponse

    def _get_agent_by_name(self, agent_name):
        """
        Retrieves an agent from the agency based on the agent's name.

        Parameters:
            agent_name (str): The name of the agent to be retrieved.

        Returns:
            Agent: The agent object with the specified name.

        Raises:
            Exception: If no agent with the given name is found in the agency.
        """
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        raise Exception(f"Agent {agent_name} not found.")

    def _get_agents_by_names(self, agent_names):
        """
        Retrieves a list of agent objects based on their names.

        Parameters:
            agent_names: A list of strings representing the names of the agents to be retrieved.

        Returns:
            A list of Agent objects corresponding to the given names.
        """
        return [self._get_agent_by_name(agent_name) for agent_name in agent_names]

    def _get_agent_ids(self):
        """
        Retrieves the IDs of all agents currently in the agency.

        Returns:
            List[str]: A list containing the unique IDs of all agents.
        """
        return [agent.id for agent in self.agents]

    def _get_agent_names(self):
        """
        Retrieves the names of all agents in the agency.

        Returns:
            List[str]: A list of names of all agents currently part of the agency.
        """
        return [agent.name for agent in self.agents]

    def _get_class_folder_path(self):
        """
        Retrieves the absolute path of the directory containing the class file.

        Returns:
            str: The absolute path of the directory where the class file is located.
        """
        return os.path.abspath(os.path.dirname(inspect.getfile(self.__class__)))

    def delete(self):
        """
        This method deletes the agency and all its agents, cleaning up any files and vector stores associated with each agent.
        """
        for agent in self.agents:
            agent.delete()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\AgentCreator.py
================================================
from agency_swarm import Agent
from .tools.ImportAgent import ImportAgent
from .tools.CreateAgentTemplate import CreateAgentTemplate
from .tools.ReadManifesto import ReadManifesto

class AgentCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new agents for the agency.",
            instructions="./instructions.md",
            tools=[ImportAgent, CreateAgentTemplate, ReadManifesto],
            temperature=0.3,
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\instructions.md
================================================
# AgentCreator Agent Instructions

You are an agent that creates other agents as instructed by the user. 

The user will communicate to you each agent that needs to be created. Below are your instructions that needs to be followed for each agent communicated by the user.

**Primary Instructions:**
1. First, read the manifesto using `ReadManifesto` tool if you have not already done so. This file contains the agency manifesto that describes the agency's purpose and goals.
2. If a similar agent to the requested one is accessible through the `ImportAgent` tool, import this agent and inform the user that the agent has been created. Skip the following steps.
3. If not, create a new agent using `CreateAgentTemplate` tool. 
4. Tell the `ToolCreator` agent to create tools or APIs for this agent. Make sure to also communicate the agent description, name and a summary of the processes that it needs to perform. CEO Agents do not need to utilize any tools, so you can skip this and the following steps.
5. If there are no issues and tools have been successfully created, notify the user that the agent has been created. Otherwise, try to resolve any issues with the tool creator before reporting back to the user.
6. Repeat this process for each agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\CreateAgentTemplate.py
================================================
import os
import shutil
from typing import List

from pydantic import Field, model_validator

from agency_swarm import BaseTool
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.util import create_agent_template

allowed_tools: List = ["CodeInterpreter"]

web_developer_example_instructions = """# Web Developer Agent Instructions

You are an agent that builds responsive web applications using Next.js and Material-UI (MUI). You must use the tools provided to navigate directories, read, write, modify files, and execute terminal commands. 

### Primary Instructions:
1. Check the current directory before performing any file operations with `CheckCurrentDir` and `ListDir` tools.
2. Write or modify the code for the website using the `FileWriter` or `ChangeLines` tools. Make sure to use the correct file paths and file names. Read the file first if you need to modify it.
3. Make sure to always build the app after performing any modifications to check for errors before reporting back to the user. Keep in mind that all files must be reflected on the current website
4. Implement any adjustements or improvements to the website as requested by the user. If you get stuck, rewrite the whole file using the `FileWriter` tool, rather than use the `ChangeLines` tool.
"""


class CreateAgentTemplate(BaseTool):
    """
    This tool creates a template folder for a new agent. Always use this tool first, before creating tools or APIs for the agent.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to be created. Cannot include special characters or spaces."
    )
    agent_description: str = Field(
        ..., description="Description of the agent to be created."
    )
    instructions: str = Field(
        ..., description="Instructions for the agent to be created in markdown format. "
                         "Instructions should include a decription of the role and a specific step by step process "
                         "that this agent need to perform in order to execute the tasks. "
                         "The process must also be aligned with all the other agents in the agency. Agents should be "
                         "able to collaborate with each other to achieve the common goal of the agency.",
        examples=[
            web_developer_example_instructions,
        ]
    )
    default_tools: List[str] = Field(
        [], description=f"List of default tools to be included in the agent. Possible values are {allowed_tools}."
                        f"CodeInterpreter allows the agent to execute python code in a remote python environment.",
        example=["CodeInterpreter"],
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("manifesto_read"):
            raise ValueError("Please read the manifesto first with the ReadManifesto tool.")

        self._shared_state.set("agent_name", self.agent_name)

        os.chdir(self._shared_state.get("agency_path"))

        # remove folder if it already exists
        if os.path.exists(self.agent_name):
            shutil.rmtree(self.agent_name)

        create_agent_template(self.agent_name,
                              self.agent_description,
                              instructions=self.instructions,
                              code_interpreter=True if "CodeInterpreter" in self.default_tools else None,
                              include_example_tool=False)

        # # create or append to init file
        path = self._shared_state.get("agency_path")
        class_name = self.agent_name.replace(" ", "").strip()
        if not os.path.isfile("__init__.py"):
            with open("__init__.py", "w") as f:
                f.write(f"from .{class_name} import {class_name}")
        else:
            with open("__init__.py", "a") as f:
                f.write(f"\nfrom .{class_name} import {class_name}")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {class_name} import {class_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        if "ceo" in self.agent_name.lower():
            return f"You can tell the user that the process of creating {self.agent_name} has been completed, because CEO agent does not need to utilizie any tools or APIs."

        return f"Agent template has been created for {self.agent_name}. Please now tell ToolCreator to create tools for this agent or OpenAPICreator to create API schemas, if this agent needs to utilize any tools or APIs. If this is unclear, please ask the user for more information."

    @model_validator(mode="after")
    def validate_tools(self):
        check_agency_path(self)

        for tool in self.default_tools:
            if tool not in allowed_tools:
                raise ValueError(f"Tool {tool} is not allowed. Allowed tools are: {allowed_tools}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ImportAgent.py
================================================
import os

from pydantic import Field, field_validator

from agency_swarm import BaseTool
from agency_swarm.util.cli import import_agent
from agency_swarm.util.helpers import get_available_agent_descriptions, list_available_agents


class ImportAgent(BaseTool):
    """
    This tool imports an existing agent from agency swarm framework. Please make sure to first use the GetAvailableAgents tool to get the list of available agents.
    """
    agent_name: str = Field(...,
                            description=get_available_agent_descriptions())
    agency_path: str = Field(
        None, description="Path to the agency where the agent will be imported. Default is the current agency.")

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set("default_folder", os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_path:
            return "Error: You must set the agency_path."

        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
        else:
            os.chdir(self.agency_path)

        import_agent(self.agent_name, "./")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {self.agent_name} import {self.agent_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        return (f"Success. {self.agent_name} has been imported. "
                f"You can now tell the user to user proceed with next agents.")

    @field_validator("agent_name", mode='after')
    @classmethod
    def agent_name_exists(cls, v):
        available_agents = list_available_agents()
        if v not in available_agents:
            raise ValueError(
                f"Agent with name {v} does not exist. Available agents are: {available_agents}")
        return v

if __name__ == "__main__":
    tool = ImportAgent(agent_name="Devid")
    tool._shared_state.set("agency_path", "./")
    tool.run()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ReadManifesto.py
================================================
import os

from pydantic import Field

from agency_swarm import BaseTool


class ReadManifesto(BaseTool):
    """
    This tool reads a manifesto for the agency being created from a markdown file.
    """
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_name:
            raise ValueError("Please specify the agency name. Ask user for clarification if needed.")

        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))

        with open("agency_manifesto.md", "r") as f:
            manifesto = f.read()

        os.chdir(self._shared_state.get("default_folder"))

        self._shared_state.set("manifesto_read", True)

        return manifesto


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\get_modules.py
================================================
import importlib.resources
import pathlib


def get_modules(module_name):
    """
    Get all submodule names from a given module based on file names, without importing them,
    excluding those containing '.agent' or '.genesis' in their paths.

    Args:
    - module_name: The name of the module to search through.

    Returns:
    - A list of submodule names found within the given module.
    """
    submodule_names = []

    try:
        # Using importlib.resources to access the package contents
        with importlib.resources.path(module_name, '') as package_path:
            # Walk through the package directory using pathlib
            for path in pathlib.Path(package_path).rglob('*.py'):
                if path.name != '__init__.py':
                    # Construct the module name from the file path
                    relative_path = path.relative_to(package_path)
                    module_path = '.'.join(relative_path.with_suffix('').parts)

                    submodule_names.append(f"{module_name}.{module_path}")

    except ImportError:
        print(f"Module {module_name} not found.")
        return submodule_names

    submodule_names = [name for name in submodule_names if not name.endswith(".agent") and
                       '.genesis' not in name and
                       'util' not in name and
                       'oai' not in name and
                       'ToolFactory' not in name and
                       'BaseTool' not in name]

    # remove repetition at the end of the path like 'agency_swarm.agents.coding.CodingAgent.CodingAgent'
    for i in range(len(submodule_names)):
        splitted = submodule_names[i].split(".")
        if splitted[-1] == splitted[-2]:
            submodule_names[i] = ".".join(splitted[:-1])

    return submodule_names


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\__init__.py
================================================
from .get_modules import get_modules

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\__init__.py
================================================
from .AgentCreator import AgentCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisAgency.py
================================================
from agency_swarm import Agency
from .AgentCreator import AgentCreator

from .GenesisCEO import GenesisCEO
from .OpenAPICreator import OpenAPICreator
from .ToolCreator import ToolCreator
from agency_swarm.util.helpers import get_available_agent_descriptions

class GenesisAgency(Agency):
    def __init__(self, with_browsing=True, **kwargs):
        if "max_prompt_tokens" not in kwargs:
            kwargs["max_prompt_tokens"] = 25000

        if 'agency_chart' not in kwargs:
            agent_creator = AgentCreator()
            genesis_ceo = GenesisCEO()
            tool_creator = ToolCreator()
            openapi_creator = OpenAPICreator()
            kwargs['agency_chart'] = [
                genesis_ceo, tool_creator, agent_creator,
                [genesis_ceo, agent_creator],
                [agent_creator, tool_creator],
            ]

            if with_browsing:
                from agency_swarm.agents.BrowsingAgent import BrowsingAgent
                browsing_agent = BrowsingAgent()

                browsing_agent.instructions += ("""\n
# BrowsingAgent's Primary instructions
1. Browse the web to find the API documentation requested by the user. Prefer searching google directly for this API documentation page.
2. Navigate to the API documentation page and ensure that it contains the necessary API endpoints descriptions. You can use the AnalyzeContent tool to check if the page contains the necessary API descriptions. If not, try perform another search in google and keep browsing until you find the right page.
3. If you have confirmed that the page contains the necessary API documentation, export the page with ExportFile tool. Then, send the file_id back to the user along with a brief description of the API.
4. Repeat these steps for each new agent, as requested by the user.
                """)
                kwargs['agency_chart'].append(openapi_creator)
                kwargs['agency_chart'].append([openapi_creator, browsing_agent])

        if 'shared_instructions' not in kwargs:
            kwargs['shared_instructions'] = "./manifesto.md"

        super().__init__(**kwargs)


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\GenesisCEO.py
================================================
from pathlib import Path

from agency_swarm import Agent
from .tools.CreateAgencyFolder import CreateAgencyFolder
from .tools.FinalizeAgency import FinalizeAgency
from .tools.ReadRequirements import ReadRequirements


class GenesisCEO(Agent):
    def __init__(self):
        super().__init__(
            description="Acts as the overseer and communicator across the agency, ensuring alignment with the "
                        "agency's goals.",
            instructions="./instructions.md",
            tools=[CreateAgencyFolder, FinalizeAgency, ReadRequirements],
            temperature=0.4,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\instructions.md
================================================
# GenesisCEO Agent Instructions

As a Genesis CEO Agent within the Agency Swarm framework, your mission is to help users define the structure of their agency and create the initial agents.

1. Pick a name for the agency, determine its goals and mission. Ask the user for any clarification if needed.
2. Propose an initial structure for the agency, including the roles of the agents, their communication flows and what APIs or Tools each agent can use, if specified by the user. Focus on creating at most 2 agents, plus CEO, unless instructed otherwise by the user. Do not name the CEO agent GenesisCEO. It's name must be tailored for the purpose of the agency. Output the code snippet like below. Adjust it accordingly, based on user's input.
3. Upon confirmation of the agency structure, use `CreateAgencyFolder` tool to create a folder for the agency. If any modifications are required please use this tool again with the same agency name and it will overwrite the existing folder.
4. Tell AgentCreator to create these agents one by one, starting with the CEO. Each agent should be sent in a separate message using the `SendMessage` tool. Please make sure to include the agent description, summary of the processes it needs to perform and the APIs or Tools that it can use via the message parameter.
5. Once all agents are created, please use the `FinalizeAgency` tool, and tell the user that he can now navigate to the agency folder and start it with `python agency.py` command.


### Example of communication flows

Here is an example of how communication flows are defined in agency swarm. Essentially, agents that are inside a double array can initiate communication with each other. Agents that are in the top level array can communicate with the user. 

```python
agency = Agency([
    ceo, dev,  # CEO and Developer will be the entry point for communication with the user
    [ceo, dev],  # CEO can initiate communication with Developer
    [ceo, va],   # CEO can initiate communication with Virtual Assistant
    [dev, va]    # Developer can initiate communication with Virtual Assistant
], shared_instructions='agency_manifesto.md') # shared instructions for all agents
```
Keep in mind that this is just an example and you should replace it with the actual agents you are creating. Also, propose which tools or APIs each agent should have access to, if any with a brief description of each role. Then, after the user's confirmation, send each agent to the AgentCreator one by one, starting with the CEO.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\CreateAgencyFolder.py
================================================
import shutil
from pathlib import Path

from pydantic import Field, field_validator

import agency_swarm.agency.genesis.GenesisAgency
from agency_swarm import BaseTool

import os


class CreateAgencyFolder(BaseTool):
    """
    This tool creates or modifies an agency folder. You can use it again with the same agency_name to modify a previously created agency, if the user wants to change the agency chart or the manifesto.
    """
    agency_name: str = Field(
        ..., description="Name of the agency to be created. Must not contain spaces or special characters.",
        examples=["AgencyName", "MyAgency", "ExampleAgency"]
    )
    agency_chart: str = Field(
        ..., description="Agency chart to be passed into the Agency class.",
        examples=["[ceo, [ceo, dev], [ceo, va], [dev, va]]"]
    )
    manifesto: str = Field(
        ..., description="Manifesto for the agency, describing its goals and additional context shared by all agents "
                         "in markdown format. It must include information about the working environment, the mission "
                         "and the goals of the agency. Do not add descriptions of the agents themselves or the agency structure.",
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', Path.cwd())

        if self._shared_state.get("agency_name") is None:
            os.mkdir(self.agency_name)
            os.chdir("./" + self.agency_name)
            self._shared_state.set("agency_name", self.agency_name)
            self._shared_state.set("agency_path", Path("./").resolve())
        elif self._shared_state.get("agency_name") == self.agency_name and os.path.exists(self._shared_state.get("agency_path")):
            os.chdir(self._shared_state.get("agency_path"))
            for file in os.listdir():
                if file != "__init__.py" and os.path.isfile(file):
                    os.remove(file)
        else:
            os.mkdir(self._shared_state.get("agency_path"))
            os.chdir("./" + self.agency_name)

        # check that agency chart is valid
        if not self.agency_chart.startswith("[") or not self.agency_chart.endswith("]"):
            raise ValueError("Agency chart must be a list of lists, except for the first agents.")

        # add new lines after every comma, except for those inside second brackets
        # must transform from "[ceo, [ceo, dev], [ceo, va], [dev, va] ]"
        # to "[ceo, [ceo, dev],\n [ceo, va],\n [dev, va] ]"
        agency_chart = self.agency_chart.replace("],", "],\n")

        # create init file
        with open("__init__.py", "w") as f:
            f.write("")

        # create agency.py
        with open("agency.py", "w") as f:
            f.write(agency_py.format(agency_chart=agency_chart))

        # write manifesto
        path = os.path.join("agency_manifesto.md")
        with open(path, "w") as f:
            f.write(self.manifesto)

        os.chdir(self._shared_state.get('default_folder'))

        return f"Agency folder has been created. You can now tell AgentCreator to create agents for {self.agency_name}.\n"


agency_py = """from agency_swarm import Agency


agency = Agency({agency_chart},
                shared_instructions='./agency_manifesto.md', # shared instructions for all agents
                max_prompt_tokens=25000, # default tokens in conversation for all agents
                temperature=0.3, # default temperature for all agents
                )
                
if __name__ == '__main__':
    agency.demo_gradio()
"""

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\FinalizeAgency.py
================================================
import os
from typing import List

from pydantic import Field, model_validator, field_validator

from agency_swarm import BaseTool, get_openai_client
from agency_swarm.util import create_agent_template


class FinalizeAgency(BaseTool):
    """
    This tool finalizes the agency structure and it's imports. Please make sure to use at only at the very end, after all agents have been created.
    """
    agency_path: str = Field(
        None, description="Path to the agency folder. Defaults to the agency currently being created."
    )

    def run(self):
        agency_path = None
        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
            agency_path = self._shared_state.get("agency_path")
        else:
            os.chdir(self.agency_path)
            agency_path = self.agency_path

        client = get_openai_client()

        # read agency.py
        with open("./agency.py", "r") as f:
            agency_py = f.read()
            f.close()

        res = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=examples + [
                {'role': "user", 'content': agency_py},
            ],
            temperature=0.0,
        )

        message = res.choices[0].message.content

        # write agency.py
        with open("./agency.py", "w") as f:
            f.write(message)
            f.close()

        return f"Successfully finalized {agency_path} structure. You can now instruct the user to run the agency.py file."

    @model_validator(mode="after")
    def validate_agency_path(self):
        if not self._shared_state.get("agency_path") and not self.agency_path:
            raise ValueError("Agency path not found. Please specify the agency_path. Ask user for clarification if needed.")


SYSTEM_PROMPT = """"Please read the file provided by the user and fix all the imports and indentation accordingly. 

Only output the full valid python code and nothing else."""

example_input = """
from agency_swarm import Agency

from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent


agency = Agency([ceo, [ceo, news_analysis],
 [ceo, price_tracking],
 [news_analysis, price_tracking]],
shared_instructions='./agency_manifesto.md')

if __name__ == '__main__':
    agency.demo_gradio()
"""

example_output = """from agency_swarm import Agency
from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent

ceo = CEO()
news_analysis = NewsAnalysisAgent()
price_tracking = PriceTrackingAgent()

agency = Agency([ceo, [ceo, market_analyst],
                 [ceo, news_curator],
                 [market_analyst, news_curator]],
                shared_instructions='./agency_manifesto.md')
    
if __name__ == '__main__':
    agency.demo_gradio()"""

examples = [
    {'role': "system", 'content': SYSTEM_PROMPT},
    {'role': "user", 'content': example_input},
    {'role': "assistant", 'content': example_output}
]


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\ReadRequirements.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field
import os


class ReadRequirements(BaseTool):
    """
    Use this tool to read the agency requirements if user provides them as a file.
    """

    file_path: str = Field(
        ..., description="The path to the file that needs to be read."
    )

    def run(self):
        """
        Checks if the file exists, and if so, opens the specified file, reads its contents, and returns them.
        If the file does not exist, raises a ValueError.
        """
        if not os.path.exists(self.file_path):
            raise ValueError(f"File path does not exist: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except Exception as e:
            return f"An error occurred while reading the file: {str(e)}"


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\__init__.py
================================================
from .GenesisCEO import GenesisCEO

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\manifesto.md
================================================
# Genesis Agency Manifesto

You are a part of a Genesis Agency for a framework called Agency Swarm. The goal of your agency is to create other agencies within this framework. Below is a brief description of the framework.

**Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the AI agent creation process and enable anyone to create a collaborative swarms of agents (Agencies), each with distinct roles and capabilities. These agents must function autonomously, yet collaborate with other agents to achieve a common goal.**

Keep in mind that communication with the other agents within your agency via the `SendMessage` tool is synchronous. Other agents will not be executing any tasks post response. Please instruct the recipient agent to continue its execution, if needed. Do not report to the user before the recipient agent has completed its task. If the agent proposes the next steps, for example, you must instruct the recipient agent to execute them.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\instructions.md
================================================
# OpenAPICreator Instructions

You are an agent that creates tools from OpenAPI schemas. User will provide you with a description of the agent's role. If the provided description does not require any API calls, please notify the user.

**Here are your primary instructions:**
1. Think which API is needed for this agent's role, as communicated by the user. Then, tell the BrowsingAgent to find this API documentation page.
2. Explore the provided file from the BrowsingAgent with the `myfiles_broswer` tool to determine which endpoints are needed for this agent's role.
3. If the file does not contain the actual API documentation page, please notify the BrowsingAgent. Keep in mind that you do not need the full API documentation. You can make an educated guess if some information is not available.
4. Use `CreateToolsFromOpenAPISpec` to create the tools by defining the OpenAPI schema accordingly. Make sure to include all the relevant API endpoints that are needed for this agent to execute its role from the provided file. Do not truncate the schema.
5. Repeat these steps for each new agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\OpenAPICreator.py
================================================
from agency_swarm import Agent
from .tools.CreateToolsFromOpenAPISpec import CreateToolsFromOpenAPISpec


class OpenAPICreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools from an OpenAPI specifications.",
            instructions="./instructions.md",
            tools=[CreateToolsFromOpenAPISpec]
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\tools\CreateToolsFromOpenAPISpec.py
================================================
import os

from pydantic import Field, field_validator, model_validator

from agency_swarm import BaseTool

import json

from agency_swarm.agency.genesis.util import check_agency_path, check_agent_path
from agency_swarm.tools import ToolFactory
from agency_swarm.util.openapi import validate_openapi_spec


class CreateToolsFromOpenAPISpec(BaseTool):
    """
    This tool creates a set of tools from an OpenAPI specification. Each method in the specification is converted to a separate tool.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to create the API for. Must be an existing agent."
    )
    openapi_spec: str = Field(
        ..., description="OpenAPI specification for the tool to be created as a valid JSON string. Only the relevant "
                         "endpoints must be included. Responses are not required. Each method should contain "
                         "an operation id and a description. Do not truncate this schema. "
                         "It must be a full valid OpenAPI 3.1.0 specification.",
        examples=[
            '{\n  "openapi": "3.1.0",\n  "info": {\n    "title": "Get weather data",\n    "description": "Retrieves current weather data for a location.",\n    "version": "v1.0.0"\n  },\n  "servers": [\n    {\n      "url": "https://weather.example.com"\n    }\n  ],\n  "paths": {\n    "/location": {\n      "get": {\n        "description": "Get temperature for a specific location",\n        "operationId": "GetCurrentWeather",\n        "parameters": [\n          {\n            "name": "location",\n            "in": "query",\n            "description": "The city and state to retrieve the weather for",\n            "required": true,\n            "schema": {\n              "type": "string"\n            }\n          }\n        ],\n        "deprecated": false\n      }\n    }\n  },\n  "components": {\n    "schemas": {}\n  }\n}'])
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        os.chdir(self._shared_state.get("agency_path"))

        os.chdir(self.agent_name)

        try:
            try:
                tools = ToolFactory.from_openapi_schema(self.openapi_spec)
            except Exception as e:
                raise ValueError(f"Error creating tools from OpenAPI Spec: {e}")

            if len(tools) == 0:
                return "No tools created. Please check the OpenAPI specification."

            tool_names = [tool.__name__ for tool in tools]

            # save openapi spec
            folder_path = "./" + self.agent_name + "/"
            os.chdir(folder_path)

            api_name = json.loads(self.openapi_spec)["info"]["title"]

            api_name = api_name.replace("API", "Api").replace(" ", "")

            api_name = ''.join(['_' + i.lower() if i.isupper() else i for i in api_name]).lstrip('_')

            with open("schemas/" + api_name + ".json", "w") as f:
                f.write(self.openapi_spec)

            return "Successfully added OpenAPI Schema to " + self._shared_state.get("agent_name")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

    @field_validator("openapi_spec", mode='before')
    @classmethod
    def validate_openapi_spec(cls, v):
        try:
            validate_openapi_spec(v)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format:", e)
        except Exception as e:
            raise ValueError("Error validating OpenAPI schema:", e)
        return v

    @model_validator(mode="after")
    def validate_agent_name(self):
        check_agency_path(self)

        check_agent_path(self)



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\__init__.py
================================================
from .OpenAPICreator import OpenAPICreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\instructions.md
================================================
# ToolCreator Agent Instructions

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

**Here are your primary instructions:**
1. Determine which tools the agent must utilize to perform it's role. Make an educated guess if the user has not specified any tools or APIs. Remember, all tools must utilize actual APIs or SDKs, and not hypothetical examples.
2. Create these tools one at a time, using `CreateTool` tool.
3. Test each tool with the `TestTool` function to ensure it is working as expected. Do not ask the user, always test the tool yourself, if it does not require any API keys and all the inputs can be mocked.
4. Only after all the necessary tools are created, notify the user.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\ToolCreator.py
================================================
from agency_swarm import Agent
from .tools.CreateTool import CreateTool
from .tools.TestTool import TestTool


class ToolCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools for the agency using python code.",
            instructions="./instructions.md",
            tools=[CreateTool, TestTool],
            temperature=0,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\tools\CreateTool.py
================================================
import os
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agency_swarm import get_openai_client
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.tools import BaseTool

prompt = """# Agency Swarm Overview

Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the agent creation process and enable anyone to create a collaborative swarm of agents (Agencies), each with distinct roles and capabilities. 

# ToolCreator Agent Instructions for Agency Swarm Framework

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

### Tool Creation Guide

When creating a tool, you are essentially defining a new class that extends `BaseTool`. This process involves several key steps, outlined below.

#### 1. Import Necessary Modules

Start by importing `BaseTool` from `agency_swarm.tools` and `Field` from `pydantic`. These imports will serve as the foundation for your custom tool class. Import any additional packages necessary to implement the tool's logic.

#### 2. Define Your Tool Class

Create a new class that inherits from `BaseTool`. This class will encapsulate the functionality of your tool. `BaseTool` class inherits from the Pydantic's `BaseModel` class.

#### 3. Specify Tool Fields

Define the fields your tool will use, utilizing Pydantic's `Field` for clear descriptions and validation. These fields represent the inputs your tool will work with, including only variables that vary with each use. Define any constant variables like api keys globally.

#### 4. Implement the `run` Method

The `run` method is where your tool's logic is executed. Use the fields defined earlier to perform the tool's intended task. It must contain the actual fully functional correct python code. It can utilize various python packages, previously imported in step 1. Do not include any placeholders or hypothetical examples in the code.

### Example of a Custom Tool

```python
from agency_swarm.tools import BaseTool
from pydantic import Field
import os

account_id = "MY_ACCOUNT_ID"
api_key = os.getenv("MY_API_KEY") # or access_token = os.getenv("MY_ACCESS_TOKEN")

class MyCustomTool(BaseTool):
    \"\"\"
    A brief description of what the custom tool does.
    The docstring should clearly explain the tool's purpose and functionality.
    It will be used by the agent to determine when to use this tool.
    \"\"\"

    # Define the fields with descriptions using Pydantic Field
    example_field: str = Field(
        ..., description="Description of the example field, explaining its purpose and usage for the Agent."
    )

    def run(self):
        \"\"\"
        The implementation of the run method, where the tool's main functionality is executed.
        This method should utilize the fields defined above to perform the task.
        \"\"\"
        # Your custom tool logic goes here
        # Example: 
        # do_something(self.example_field, api_key, account_id)

        # Return the result of the tool's operation as a string
        return "Result of MyCustomTool operation"
```

To share state between 2 or more tools, you can use the `shared_state` attribute of the tool. It is a dictionary that can be used to store and retrieve values across different tools. This can be useful for passing information between tools or agents or to verify the state of the system. Here is an example of how to use the `shared_state`:

```python
class MyCustomTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        # Update the shared state
        self._shared_state.set("key", "value")
        
        return "Result of MyCustomTool operation"
        
# Access shared state in another tool
class AnotherTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        return "Result of AnotherTool operation"
```

This is useful to pass information between tools or agents or to verify the state of the system.  

Remember, you must output the resulting python tool code as a whole in a code block, so the user can just copy and paste it into his program. Each tool code snippet must be ready to use. It must not contain any placeholders or hypothetical examples."""

history = [
            {
                "role": "system",
                "content": prompt
            },
        ]


class CreateTool(BaseTool):
    """This tool creates other custom tools for the agent, based on your requirements and details."""
    agent_name: str = Field(
        ..., description="Name of the agent to create the tool for."
    )
    tool_name: str = Field(..., description="Name of the tool class in camel case.", examples=["ExampleTool"])
    requirements: str = Field(
        ...,
        description="The comprehensive requirements explaning the primary functionality of the tool. It must not contain any code or implementation details."
    )
    details: str = Field(
        None, description="Additional details or error messages, class, function, and variable names."
    )
    mode: Literal["write", "modify"] = Field(
        ..., description="The mode of operation for the tool. 'write' is used to create a new tool or overwrite an existing one. 'modify' is used to modify an existing tool."
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))
        os.chdir(self.agent_name)

        client = get_openai_client()

        if self.mode == "write":
            message = f"Please create a '{self.tool_name}' tool that meets the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."
        else:
            message = f"Please rewrite a '{self.tool_name}' according to the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."

        if self.details:
            message += f"\nAdditional Details: {self.details}"

        if self.mode == "modify":
            message += f"\nThe existing file content is as follows:"

            try:
                with open("./tools/" + self.tool_name + ".py", 'r') as file:
                    prev_content = file.read()
                    message += f"\n\n```{prev_content}```"
            except Exception as e:
                os.chdir(self._shared_state.get("default_folder"))
                return f'Error reading {self.tool_name}: {e}'

        history.append({
                "role": "user",
                "content": message
            })

        messages = history.copy()

        # use the last 6 messages
        messages = messages[-6:]

        # add system message upfront
        messages.insert(0, history[0])

        n = 0
        code = ""
        content = ""
        while n < 3:
            resp = client.chat.completions.create(
                messages=messages,
                model="gpt-4o",
                temperature=0,
            )

            content = resp.choices[0].message.content

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            pattern = r"```(?:[a-zA-Z]+\n)?(.*?)```"
            match = re.findall(pattern, content, re.DOTALL)
            if match:
                code = match[-1].strip()
                history.append(
                    {
                        "role": "assistant",
                        "content": content
                    }
                )
                break
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: Could not find the python code block in the response. Please try again."
                    }
                )

            n += 1

        if n == 3 or not code:
            # remove last message from history
            history.pop()
            os.chdir(self._shared_state.get("default_folder"))
            return "Error: Could not generate a valid file."
        try:
            with open("./tools/" + self.tool_name + ".py", "w") as file:
                file.write(code)

            os.chdir(self._shared_state.get("default_folder"))
            return f'{content}\n\nPlease make sure to now test this tool if possible.'
        except Exception as e:
            os.chdir(self._shared_state.get("default_folder"))
            return f'Error writing to file: {e}'

    @field_validator("requirements", mode="after")
    @classmethod
    def validate_requirements(cls, v):
        if "placeholder" in v:
            raise ValueError("Requirements contain placeholders. "
                             "Please never user placeholders. Instead, implement only the code that you are confident about.")

        # check if code is included in requirements
        pattern = r'(```)((.*\n){5,})(```)'
        if re.search(pattern, v):
            raise ValueError(
                "Requirements contain a code snippet. Please never include code snippets in requirements. "
                "Requirements must be a description of the complete file to be written. You can include specific class, function, and variable names, but not the actual code."
            )

        return v

    @field_validator("details", mode="after")
    @classmethod
    def validate_details(cls, v):
        if len(v) == 0:
            raise ValueError("Details are required. Remember this tool does not have access to other files. Please provide additional details like relevant documentation, error messages, or class, function, and variable names from other files that this file depends on.")
        return v

    @model_validator(mode="after")
    def validate_agency_name(self):
        if not self.agent_name and not self._shared_state.get("agent_name"):
            raise ValueError("Please provide agent name.")

        check_agency_path(self)


if __name__ == "__main__":
    tool = CreateTool(
        requirements="Write a program that takes a list of integers as input and returns the sum of all the integers in the list.",
        mode="write",
        file_path="test.py",
    )
    print(tool.run())

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\__init__.py
================================================
from .ToolCreator import ToolCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\util.py
================================================
import os
from pathlib import Path


def check_agency_path(self):
    if not self._shared_state.get("default_folder"):
        self._shared_state.set('default_folder', Path.cwd())

    if not self._shared_state.get("agency_path") and not self.agency_name:
        available_agencies = os.listdir("./")
        available_agencies = [agency for agency in available_agencies if os.path.isdir(agency)]
        raise ValueError(f"Please specify an agency. Available agencies are: {available_agencies}")
    elif not self._shared_state.get("agency_path") and self.agency_name:
        if not os.path.exists(os.path.join("./", self.agency_name)):
            available_agencies = os.listdir("./")
            available_agencies = [agency for agency in available_agencies if os.path.isdir(agency)]
            raise ValueError(f"Agency {self.agency_name} not found. Available agencies are: {available_agencies}")
        self._shared_state.set("agency_path", os.path.join("./", self.agency_name))


def check_agent_path(self):
    agent_path = os.path.join(self._shared_state.get("agency_path"), self.agent_name)
    if not os.path.exists(agent_path):
        available_agents = os.listdir(self._shared_state.get("agency_path"))
        available_agents = [agent for agent in available_agents if
                            os.path.isdir(os.path.join(self._shared_state.get("agency_path"), agent))]
        raise ValueError(f"Agent {self.agent_name} not found. Available agents are: {available_agents}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\__init__.py
================================================
from .GenesisAgency import GenesisAgency

================================================
File: /agency-swarm-main\agency_swarm\agency\__init__.py
================================================
from .agency import Agency


================================================
File: /agency-swarm-main\agency_swarm\agents\agent.py
================================================
import copy
import inspect
import json
import os
from typing import Dict, Union, Any, Type, Literal, TypedDict, Optional
from typing import List

from deepdiff import DeepDiff
from openai import NotFoundError
from openai.types.beta.assistant import ToolResources

from agency_swarm.tools import BaseTool, ToolFactory, Retrieval
from agency_swarm.tools import FileSearch, CodeInterpreter
from agency_swarm.tools.oai.FileSearch import FileSearchConfig
from agency_swarm.util.oai import get_openai_client
from agency_swarm.util.openapi import validate_openapi_spec
from agency_swarm.util.shared_state import SharedState
from pydantic import BaseModel
from openai.lib._parsing._completions import type_to_response_format_param


================================================
File: /agency-swarm-main\agency_swarm\agents\__init__.py
================================================
from .agent import Agent

================================================
File: /agency-swarm-main\agency_swarm\messages\message_output.py
================================================
import json
import os
import queue
import threading
import time
from typing import Any, Dict, List, Literal, Optional, Type, TypeVar, TypedDict, Union

from openai.types.beta.threads import Message
from openai.types.beta.threads.runs import RunStep
from openai.types.beta.threads.runs.tool_call import (
    CodeInterpreterToolCall,
    FileSearchToolCall,
    FunctionToolCall,
    ToolCall,
)
from pydantic import BaseModel, Field, field_validator, model_validator
from rich.console import Console
from typing_extensions import override

from agency_swarm.tools import BaseTool, CodeInterpreter, FileSearch
from agency_swarm.tools.send_message import SendMessage, SendMessageBase
from agency_swarm.user import User
from agency_swarm.util.errors import RefusalError
from agency_swarm.util.files import get_tools, get_file_purpose
from agency_swarm.util.shared_state import SharedState
from agency_swarm.util.streaming import AgencyEventHandler

console = Console()

T = TypeVar('T', bound=BaseModel)


class MessageOutput:
    def __init__(self, message: Message, thread_id: str, run_id: str, thread_name: str, agent_name: str,
                 thread_type: Type[BaseModel],
                 thread_type_name: str,
                 thread_type_description: str,
                 thread_type_instructions: str,
                 thread_type_tools: List[Type[BaseTool]],
                 thread_type_temperature: float,
                 thread_type_top_p: float,
                 thread_type_max_prompt_tokens: int,
                 thread_type_max_completion_tokens: int,
                 thread_type_truncation_strategy: dict,
                 thread_type_async_mode: bool,
                 thread_type_async_mode_type: Literal['threading', 'tools_threading'] = None,
                 thread_type_send_message_tool_class: Type[SendMessageBase] = SendMessage,
                 thread_type_settings_path: str = None,
                 thread_type_settings_callbacks: Dict[str, Any] = None,
                 thread_type_threads_callbacks: Dict[str, Any] = None,
                 thread_type_shared_instructions: str = None,
                 thread_type_shared_files: List[str] = None,
                 thread_type_shared_state: SharedState = None,
                 thread_type_user: User = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
                 thread_type_agents_and_threads: Dict[str, Any] = None,
                 thread_type_main_recipients: List[Any] = None,
                 thread_type_main_thread: Any = None,
                 thread_type_recipient_agents: List[Any] = None,
                 thread_type_ceo: Any = None,
                 thread_type_user: Any = None,
                 thread_type_agents: List[Any] = None,
## File Contents

### .cursorrules
```text
# AI Agent Creator Instructions for Agency Swarm Framework
...
```

### .github/workflows/close-issues.yml
```yaml
name: Close inactive issues
...
```

### .github/workflows/docs.yml  
```yaml
name: docs
...
```

### .github/workflows/publish.yml
```yaml
name: Publish to PyPI.org
...
```

### .github/workflows/test.yml
```yaml
name: Python Unittest
...
```

### agency_swarm/agency/agency.py
```python
import inspect
import json
...
```
    │       │   │   ├── letta-hosted.json
    │       │   │   ├── ollama.json
    │       │   │   ├── openai-gpt-4o.json
    │       │   │   ├── together-llama-3-1-405b.json
    │       │   │   └── together-llama-3-70b.json
    │       │   └── openai.json
    │       ├── conftest.py
    │       ├── constants.py
    │       ├── data
    │       │   ├── functions
    │       │   │   └── dump_json.py
    │       │   ├── memgpt-0.2.11
    │       │   │   ├── agents
    │       │   │   │   ├── agent_test
    │       │   │   │   │   ├── agent_state
    │       │   │   │   │   │   ├── 2024-01-11_12_43_57_PM.json
    │       │   │   │   │   │   └── 2024-01-11_12_43_59_PM.json
    │       │   │   │   │   ├── config.json
    │       │   │   │   │   └── persistence_manager
    │       │   │   │   │       ├── 2024-01-11_12_43_57_PM.persistence.pickle
    │       │   │   │   │       ├── 2024-01-11_12_43_59_PM.persistence.pickle
    │       │   │   │   │       └── index
    │       │   │   │   │           └── nodes.pkl
    │       │   │   │   ├── agent_test_attach
    │       │   │   │   │   ├── agent_state
    │       │   │   │   │   │   ├── 2024-01-11_12_42_17_PM.json
    │       │   │   │   │   │   └── 2024-01-11_12_42_19_PM.json
    │       │   │   │   │   ├── config.json
    │       │   │   │   │   └── persistence_manager
    │       │   │   │   │       ├── 2024-01-11_12_42_17_PM.persistence.pickle
    │       │   │   │   │       ├── 2024-01-11_12_42_19_PM.persistence.pickle
    │       │   │   │   │       └── index
    │       │   │   │   │           └── nodes.pkl
    │       │   │   │   └── agent_test_empty_archival
    │       │   │   │       ├── agent_state
    │       │   │   │       │   ├── 2024-01-11_12_44_32_PM.json
    │       │   │   │       │   └── 2024-01-11_12_44_33_PM.json
    │       │   │   │       ├── config.json
    │       │   │   │       └── persistence_manager
    │       │   │   │           ├── 2024-01-11_12_44_32_PM.persistence.pickle
    │       │   │   │           ├── 2024-01-11_12_44_33_PM.persistence.pickle
    │       │   │   │           └── index
    │       │   │   │               └── nodes.pkl
    │       │   │   ├── archival
    │       │   │   │   └── test
    │       │   │   │       └── nodes.pkl
    │       │   │   └── config
    │       │   ├── memgpt-0.3.17
    │       │   │   └── sqlite.db
    │       │   ├── memgpt_paper.pdf
    │       │   └── test.txt
    │       ├── helpers
    │       │   ├── client_helper.py
    │       │   ├── endpoints_helper.py
    │       │   └── utils.py
    │       ├── integration_test_summarizer.py
    │       ├── pytest.ini
    │       ├── test_agent_tool_graph.py
    │       ├── test_autogen_integration.py
    │       ├── test_base_functions.py
    │       ├── test_cli.py
    │       ├── test_client.py
    │       ├── test_client_legacy.py
    │       ├── test_concurrent_connections.py
    │       ├── test_different_embedding_size.py
    │       ├── test_function_parser.py
    │       ├── test_json_parsers.py
    │       ├── test_local_client.py
    │       ├── test_managers.py
    │       ├── test_memory.py
    │       ├── test_model_letta_perfomance.py
    │       ├── test_new_cli.py
    │       ├── test_o1_agent.py
    │       ├── test_openai_client.py
    │       ├── test_persistence.py
    │       ├── test_providers.py
    │       ├── test_schema_generator.py
    │       ├── test_server.py
    │       ├── test_storage.py
    │       ├── test_stream_buffer_readers.py
    │       ├── test_summarize.py
    │       ├── test_tool_execution_sandbox.py
    │       ├── test_tool_rule_solver.py
    │       ├── test_tool_sandbox
    │       │   └── .gitkeep
    │       ├── test_utils.py
    │       ├── test_websocket_server.py
    │       ├── utils.py
    │       └── __init__.py
    └── settings.json


class Agency:
    def __init__(self,
                 agency_chart: List,
                 shared_instructions: str = "",
                 shared_files: Union[str, List[str]] = None,
                 async_mode: Literal['threading', "tools_threading"] = None,
                 send_message_tool_class: Type[SendMessageBase] = SendMessage,
                 settings_path: str = "./settings.json",
                 settings_callbacks: SettingsCallbacks = None,
                 threads_callbacks: ThreadsCallbacks = None,
                 temperature: float = 0.3,
                 top_p: float = 1.0,
                 max_prompt_tokens: int = None,
                 max_completion_tokens: int = None,
                 truncation_strategy: dict = None,
                 ):
        """
        Initializes the Agency object, setting up agents, threads, and core functionalities.

        Parameters:
            agency_chart: The structure defining the hierarchy and interaction of agents within the agency.
            shared_instructions (str, optional): A path to a file containing shared instructions for all agents. Defaults to an empty string.
            shared_files (Union[str, List[str]], optional): A path to a folder or a list of folders containing shared files for all agents. Defaults to None.
            async_mode (str, optional): Specifies the mode for asynchronous processing. In "threading" mode, all sub-agents run in separate threads. In "tools_threading" mode, all tools run in separate threads, but agents do not. Defaults to None.
            send_message_tool_class (Type[SendMessageBase], optional): The class to use for the send_message tool. For async communication, use `SendMessageAsyncThreading`. Defaults to SendMessage.
            settings_path (str, optional): The path to the settings file for the agency. Must be json. If file does not exist, it will be created. Defaults to None.
            settings_callbacks (SettingsCallbacks, optional): A dictionary containing functions to load and save settings for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            threads_callbacks (ThreadsCallbacks, optional): A dictionary containing functions to load and save threads for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            temperature (float, optional): The temperature value to use for the agents. Agent-specific values will override this. Defaults to 0.3.
            top_p (float, optional): The top_p value to use for the agents. Agent-specific values will override this. Defaults to None.
            max_prompt_tokens (int, optional): The maximum number of tokens allowed in the prompt for each agent. Agent-specific values will override this. Defaults to None.
            max_completion_tokens (int, optional): The maximum number of tokens allowed in the completion for each agent. Agent-specific values will override this. Defaults to None.
            truncation_strategy (dict, optional): The truncation strategy to use for the completion for each agent. Agent-specific values will override this. Defaults to None.

        This constructor initializes various components of the Agency, including CEO, agents, threads, and user interactions. It parses the agency chart to set up the organizational structure and initializes the messaging tools, agents, and threads necessary for the operation of the agency. Additionally, it prepares a main thread for user interactions.
        """
        self.ceo = None
        self.user = User()
        self.agents = []
        self.agents_and_threads = {}
        self.main_recipients = []
        self.main_thread = None
        self.recipient_agents = None  # for autocomplete
        self.shared_files = shared_files if shared_files else []
        self.async_mode = async_mode
        self.send_message_tool_class = send_message_tool_class
        self.settings_path = settings_path
        self.settings_callbacks = settings_callbacks
        self.threads_callbacks = threads_callbacks
        self.temperature = temperature
        self.top_p = top_p
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.truncation_strategy = truncation_strategy

        # set thread type based send_message_tool_class async mode
        if hasattr(send_message_tool_class.ToolConfig, "async_mode") and send_message_tool_class.ToolConfig.async_mode:
            self._thread_type = ThreadAsync
        else:
            self._thread_type = Thread  

        if self.async_mode == "threading":
            from agency_swarm.tools.send_message import SendMessageAsyncThreading
            print("Warning: 'threading' mode is deprecated. Please use send_message_tool_class = SendMessageAsyncThreading to use async communication.")
            self.send_message_tool_class = SendMessageAsyncThreading
        elif self.async_mode == "tools_threading":
            Thread.async_mode = "tools_threading"
            print("Warning: 'tools_threading' mode is deprecated. Use tool.ToolConfig.async_mode = 'threading' instead.")
        elif self.async_mode is None:
            pass
        else:
            raise Exception("Please select async_mode = 'threading' or 'tools_threading'.")

        if os.path.isfile(os.path.join(self._get_class_folder_path(), shared_instructions)):
            self._read_instructions(os.path.join(self._get_class_folder_path(), shared_instructions))
        elif os.path.isfile(shared_instructions):
            self._read_instructions(shared_instructions)
        else:
            self.shared_instructions = shared_instructions

        self.shared_state = SharedState()

        self._parse_agency_chart(agency_chart)
        self._init_threads()
        self._create_special_tools()
        self._init_agents()

    def get_completion(self, message: str,
                       message_files: List[str] = None,
                       yield_messages: bool = False,
                       recipient_agent: Agent = None,
                       additional_instructions: str = None,
                       attachments: List[dict] = None,
                       tool_choice: dict = None,
                       verbose: bool = False,
                       response_format: dict = None):
        """
        Retrieves the completion for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            yield_messages (bool, optional): Flag to determine if intermediate messages should be yielded. Defaults to True.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
            response_format (dict, optional): The response format to use for the completion.

        Returns:
            Generator or final response: Depending on the 'yield_messages' flag, this method returns either a generator yielding intermediate messages or the final response from the main thread.
        """
        if verbose and yield_messages:
            raise Exception("Verbose mode is not compatible with yield_messages=True")
        
        res = self.main_thread.get_completion(message=message,
                                               message_files=message_files,
                                               attachments=attachments,
                                               recipient_agent=recipient_agent,
                                               additional_instructions=additional_instructions,
                                               tool_choice=tool_choice,
                                               yield_messages=yield_messages or verbose,
                                               response_format=response_format)
        
        if not yield_messages or verbose:
            while True:
                try:
                    message = next(res)
                    if verbose:
                        message.cprint()
                except StopIteration as e:
                    return e.value

        return res


    def get_completion_stream(self,
                              message: str,
                              event_handler: type(AgencyEventHandler),
                              message_files: List[str] = None,
                              recipient_agent: Agent = None,
                              additional_instructions: str = None,
                              attachments: List[dict] = None,
                              tool_choice: dict = None,
                              response_format: dict = None):
        """
        Generates a stream of completions for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            event_handler (type(AgencyEventHandler)): The event handler class to handle the completion stream. https://github.com/openai/openai-python/blob/main/helpers.md
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.

        Returns:
            Final response: Final response from the main thread.
        """
        if not inspect.isclass(event_handler):
            raise Exception("Event handler must not be an instance.")

        res = self.main_thread.get_completion_stream(message=message,
                                                      message_files=message_files,
                                                      event_handler=event_handler,
                                                      attachments=attachments,
                                                      recipient_agent=recipient_agent,
                                                      additional_instructions=additional_instructions,
                                                      tool_choice=tool_choice,
                                                      response_format=response_format)

        while True:
            try:
                next(res)
            except StopIteration as e:
                event_handler.on_all_streams_end()

                return e.value
                
    def get_completion_parse(self, message: str,
                             response_format: Type[T],
                             message_files: List[str] = None,
                             recipient_agent: Agent = None,
                             additional_instructions: str = None,
                             attachments: List[dict] = None,
                             tool_choice: dict = None,
                             verbose: bool = False) -> T:
        """
        Retrieves the completion for a given message from the main thread and parses the response using the provided pydantic model.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            response_format (type(BaseModel)): The response format to use for the completion. 
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
        
        Returns:
            Final response: The final response from the main thread, parsed using the provided pydantic model.
        """
        response_model = None
        if isinstance(response_format, type):
            response_model = response_format
            response_format = type_to_response_format_param(response_format)

        res = self.get_completion(message=message,
                            message_files=message_files,
                            recipient_agent=recipient_agent,
                            additional_instructions=additional_instructions,
                            attachments=attachments,
                            tool_choice=tool_choice,
                            response_format=response_format,
                            verbose=verbose)
        
        try:
            return response_model.model_validate_json(res)
        except:
            parsed_res = json.loads(res)
            if 'refusal' in parsed_res:
                raise RefusalError(parsed_res['refusal'])
            else:
                raise Exception("Failed to parse response: " + res)

    def demo_gradio(self, height=450, dark_mode=True, **kwargs):
        """
        Launches a Gradio-based demo interface for the agency chatbot.

        Parameters:
            height (int, optional): The height of the chatbot widget in the Gradio interface. Default is 600.
            dark_mode (bool, optional): Flag to determine if the interface should be displayed in dark mode. Default is True.
            **kwargs: Additional keyword arguments to be passed to the Gradio interface.
        This method sets up and runs a Gradio interface, allowing users to interact with the agency's chatbot. It includes a text input for the user's messages and a chatbot interface for displaying the conversation. The method handles user input and chatbot responses, updating the interface dynamically.
        """

        try:
            import gradio as gr
        except ImportError:
            raise Exception("Please install gradio: pip install gradio")

        js = """function () {
          gradioURL = window.location.href
          if (!gradioURL.endsWith('?__theme={theme}')) {
            window.location.replace(gradioURL + '?__theme={theme}');
          }
        }"""

        if dark_mode:
            js = js.replace("{theme}", "dark")
        else:
            js = js.replace("{theme}", "light")

        attachments = []
        images = []
        message_file_names = None
        uploading_files = False
        recipient_agent_names = [agent.name for agent in self.main_recipients]
        recipient_agent = self.main_recipients[0]

        with gr.Blocks(js=js) as demo:
            chatbot_queue = queue.Queue()
            chatbot = gr.Chatbot(height=height)
            with gr.Row():
                with gr.Column(scale=9):
                    dropdown = gr.Dropdown(label="Recipient Agent", choices=recipient_agent_names,
                                           value=recipient_agent.name)
                    msg = gr.Textbox(label="Your Message", lines=4)
                with gr.Column(scale=1):
                    file_upload = gr.Files(label="OpenAI Files", type="filepath")
            button = gr.Button(value="Send", variant="primary")

            def handle_dropdown_change(selected_option):
                nonlocal recipient_agent
                recipient_agent = self._get_agent_by_name(selected_option)

            def handle_file_upload(file_list):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                uploading_files = True
                attachments = []
                message_file_names = []
                if file_list:
                    try:
                        for file_obj in file_list:
                            purpose = get_file_purpose(file_obj.name)

                            with open(file_obj.name, 'rb') as f:
                                # Upload the file to OpenAI
                                file = self.main_thread.client.files.create(
                                    file=f,
                                    purpose=purpose
                                )

                            if purpose == "vision":
                                images.append({
                                    "type": "image_file",
                                    "image_file": {"file_id": file.id}
                                })
                            else:
                                attachments.append({
                                    "file_id": file.id,
                                    "tools": get_tools(file.filename)
                                })

                            message_file_names.append(file.filename)
                            print(f"Uploaded file ID: {file.id}")
                        return attachments
                    except Exception as e:
                        print(f"Error: {e}")
                        return str(e)
                    finally:
                        uploading_files = False

                uploading_files = False
                return "No files uploaded"

            def user(user_message, history):
                if not user_message.strip():
                    return user_message, history
                
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                nonlocal attachments
                nonlocal recipient_agent

                # Check if attachments contain file search or code interpreter types
                def check_and_add_tools_in_attachments(attachments, recipient_agent):
                    for attachment in attachments:
                        for tool in attachment.get("tools", []):
                            if tool["type"] == "file_search":
                                if not any(isinstance(t, FileSearch) for t in recipient_agent.tools):
                                    # Add FileSearch tool if it does not exist
                                    recipient_agent.tools.append(FileSearch)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added FileSearch tool to recipient agent to analyze the file.")
                            elif tool["type"] == "code_interpreter":
                                if not any(isinstance(t, CodeInterpreter) for t in recipient_agent.tools):
                                    # Add CodeInterpreter tool if it does not exist
                                    recipient_agent.tools.append(CodeInterpreter)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added CodeInterpreter tool to recipient agent to analyze the file.")
                    return None

                check_and_add_tools_in_attachments(attachments, recipient_agent)

                if history is None:
                    history = []

                original_user_message = user_message

                # Append the user message with a placeholder for bot response
                if recipient_agent:
                    user_message = f"👤 User 🗣️ @{recipient_agent.name}:\n" + user_message.strip()
                else:
                    user_message = f"👤 User:" + user_message.strip()

                nonlocal message_file_names
                if message_file_names:
                    user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

                return original_user_message, history + [[user_message, None]]

            class GradioEventHandler(AgencyEventHandler):
                message_output = None

                @classmethod
                def change_recipient_agent(cls, recipient_agent_name):
                    nonlocal chatbot_queue
                    chatbot_queue.put("[change_recipient_agent]")
                    chatbot_queue.put(recipient_agent_name)

                @override
                def on_message_created(self, message: Message) -> None:
                    if message.role == "user":
                        full_content = ""
                        for content in message.content:
                            if content.type == "image_file":
                                full_content += f"🖼️ Image File: {content.image_file.file_id}\n"
                                continue

                            if content.type == "image_url":
                                full_content += f"\n{content.image_url.url}\n"
                                continue

                            if content.type == "text":
                                full_content += content.text.value + "\n"


                        self.message_output = MessageOutput("text", self.agent_name, self.recipient_agent_name,
                                                            full_content)

                    else:
                        self.message_output = MessageOutput("text", self.recipient_agent_name, self.agent_name,
                                                            "")

                    chatbot_queue.put("[new_message]")
                    chatbot_queue.put(self.message_output.get_formatted_content())

                @override
                def on_text_delta(self, delta, snapshot):
                    chatbot_queue.put(delta.value)

                @override
                def on_tool_call_created(self, tool_call: ToolCall):
                    if isinstance(tool_call, dict):
                        if "type" not in tool_call:
                            tool_call["type"] = "function"
                        
                        if tool_call["type"] == "function":
                            tool_call = FunctionToolCall(**tool_call)
                        elif tool_call["type"] == "code_interpreter":
                            tool_call = CodeInterpreterToolCall(**tool_call)
                        elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                            tool_call = FileSearchToolCall(**tool_call)
                        else:
                            raise ValueError("Invalid tool call type: " + tool_call["type"])

                    # TODO: add support for code interpreter and retrieval tools
                    if tool_call.type == "function":
                        chatbot_queue.put("[new_message]")
                        self.message_output = MessageOutput("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))
                        chatbot_queue.put(self.message_output.get_formatted_header() + "\n")

                @override
                def on_tool_call_done(self, snapshot: ToolCall):
                    if isinstance(snapshot, dict):
                        if "type" not in snapshot:
                            snapshot["type"] = "function"
                        
                        if snapshot["type"] == "function":
                            snapshot = FunctionToolCall(**snapshot)
                        elif snapshot["type"] == "code_interpreter":
                            snapshot = CodeInterpreterToolCall(**snapshot)
                        elif snapshot["type"] == "file_search":
                            snapshot = FileSearchToolCall(**snapshot)
                        else:
                            raise ValueError("Invalid tool call type: " + snapshot["type"])
                        
                    self.message_output = None

                    # TODO: add support for code interpreter and retrieval tools
                    if snapshot.type != "function":
                        return

                    chatbot_queue.put(str(snapshot.function))

                    if snapshot.function.name == "SendMessage":
                        try:
                            args = eval(snapshot.function.arguments)
                            recipient = args["recipient"]
                            self.message_output = MessageOutput("text", self.recipient_agent_name, recipient,
                                                                args["message"])

                            chatbot_queue.put("[new_message]")
                            chatbot_queue.put(self.message_output.get_formatted_content())
                        except Exception as e:
                            pass

                    self.message_output = None

                @override
                def on_run_step_done(self, run_step: RunStep) -> None:
                    if run_step.type == "tool_calls":
                        for tool_call in run_step.step_details.tool_calls:
                            if tool_call.type != "function":
                                continue

                            if tool_call.function.name == "SendMessage":
                                continue

                            self.message_output = None
                            chatbot_queue.put("[new_message]")

                            self.message_output = MessageOutput("function_output", tool_call.function.name,
                                                                self.recipient_agent_name,
                                                                tool_call.function.output)

                            chatbot_queue.put(self.message_output.get_formatted_header() + "\n")
                            chatbot_queue.put(tool_call.function.output)

                @override
                @classmethod
                def on_all_streams_end(cls):
                    cls.message_output = None
                    chatbot_queue.put("[end]")

            def bot(original_message, history):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal recipient_agent
                nonlocal recipient_agent_names
                nonlocal images
                nonlocal uploading_files

                if not original_message:
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                if uploading_files:
                    history.append([None, "Uploading files... Please wait."])
                    yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                print("Message files: ", attachments)
                print("Images: ", images)
                
                if images and len(images) > 0:
                    original_message = [
                        {
                            "type": "text",
                            "text": original_message,
                        },
                        *images
                    ]


                completion_thread = threading.Thread(target=self.get_completion_stream, args=(
                    original_message, GradioEventHandler, [], recipient_agent, "", attachments, None))
                completion_thread.start()

                attachments = []
                message_file_names = []
                images = []
                uploading_files = False

                new_message = True
                while True:
                    try:
                        bot_message = chatbot_queue.get(block=True)

                        if bot_message == "[end]":
                            completion_thread.join()
                            break

                        if bot_message == "[new_message]":
                            new_message = True
                            continue

                        if bot_message == "[change_recipient_agent]":
                            new_agent_name = chatbot_queue.get(block=True)
                            recipient_agent = self._get_agent_by_name(new_agent_name)
                            yield "", history, gr.update(value=new_agent_name, choices=set([*recipient_agent_names, recipient_agent.name]))
                            continue

                        if new_message:
                            history.append([None, bot_message])
                            new_message = False
                        else:
                            history[-1][1] += bot_message

                        yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    except queue.Empty:
                        break

            button.click(
                user,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot]
            ).then(
                bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
            )
            dropdown.change(handle_dropdown_change, dropdown)
            file_upload.change(handle_file_upload, file_upload)
            msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
                bot, [msg, chatbot], [msg, chatbot, dropdown]
            )

            # Enable queuing for streaming intermediate outputs
            demo.queue(default_concurrency_limit=10)

        # Launch the demo
        demo.launch(**kwargs)
        return demo

    def _recipient_agent_completer(self, text, state):
        """
        Autocomplete completer for recipient agent names.
        """
        options = [agent for agent in self.recipient_agents if agent.lower().startswith(text.lower())]
        if state < len(options):
            return options[state]
        else:
            return None

    def _setup_autocomplete(self):
        """
        Sets up readline with the completer function.
        """
        try:
            import readline
        except ImportError:
            # Attempt to import pyreadline for Windows compatibility
            try:
                import pyreadline as readline
            except ImportError:
                print(
                    "Module 'readline' not found. Autocomplete will not work. If you are using Windows, try installing 'pyreadline3'.")
                return

        if not readline:
            return

        try:
            readline.set_completer(self._recipient_agent_completer)
            readline.parse_and_bind('tab: complete')
        except Exception as e:
            print(f"Error setting up autocomplete for agents in terminal: {e}. Autocomplete will not work.")

    def run_demo(self):
        """
        Executes agency in the terminal with autocomplete for recipient agent names.
        """
        outer_self = self
        from agency_swarm import AgencyEventHandler
        class TermEventHandler(AgencyEventHandler):
            message_output = None

            @override
            def on_message_created(self, message: Message) -> None:
                if message.role == "user":
                    self.message_output = MessageOutputLive("text", self.agent_name, self.recipient_agent_name,
                                                            "")
                    self.message_output.cprint_update(message.content[0].text.value)
                else:
                    self.message_output = MessageOutputLive("text", self.recipient_agent_name, self.agent_name, "")

            @override
            def on_message_done(self, message: Message) -> None:
                self.message_output = None

            @override
            def on_text_delta(self, delta, snapshot):
                self.message_output.cprint_update(snapshot.value)

            @override
            def on_tool_call_created(self, tool_call):
                if isinstance(tool_call, dict):
                    if "type" not in tool_call:
                        tool_call["type"] = "function"
                    
                    if tool_call["type"] == "function":
                        tool_call = FunctionToolCall(**tool_call)
                    elif tool_call["type"] == "code_interpreter":
                        tool_call = CodeInterpreterToolCall(**tool_call)
                    elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                        tool_call = FileSearchToolCall(**tool_call)
                    else:
                        raise ValueError("Invalid tool call type: " + tool_call["type"])

                # TODO: add support for code interpreter and retirieval tools

                if tool_call.type == "function":
                    self.message_output = MessageOutputLive("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))

            @override
            def on_tool_call_delta(self, delta, snapshot):
                if isinstance(snapshot, dict):
                    if "type" not in snapshot:
                        snapshot["type"] = "function"
                    
                    if snapshot["type"] == "function":
                        snapshot = FunctionToolCall(**snapshot)
                    elif snapshot["type"] == "code_interpreter":
                        snapshot = CodeInterpreterToolCall(**snapshot)
                    elif snapshot["type"] == "file_search":
                        snapshot = FileSearchToolCall(**snapshot)
                    else:
                        raise ValueError("Invalid tool call type: " + snapshot["type"])
                    
                self.message_output.cprint_update(str(snapshot.function))

            @override
            def on_tool_call_done(self, snapshot):
                self.message_output = None

                # TODO: add support for code interpreter and retrieval tools
                if snapshot.type != "function":
                    return

                if snapshot.function.name == "SendMessage" and not (hasattr(outer_self.send_message_tool_class.ToolConfig, 'output_as_result') and outer_self.send_message_tool_class.ToolConfig.output_as_result):
                    try:
                        args = eval(snapshot.function.arguments)
                        recipient = args["recipient"]
                        self.message_output = MessageOutputLive("text", self.recipient_agent_name, recipient,
                                                                "")

                        self.message_output.cprint_update(args["message"])
                    except Exception as e:
                        pass

                self.message_output = None

            @override
            def on_run_step_done(self, run_step: RunStep) -> None:
                if run_step.type == "tool_calls":
                    for tool_call in run_step.step_details.tool_calls:
                        if tool_call.type != "function":
                            continue

                        if tool_call.function.name == "SendMessage":
                            continue

                        self.message_output = None
                        self.message_output = MessageOutputLive("function_output", tool_call.function.name,
                                                                self.recipient_agent_name, tool_call.function.output)
                        self.message_output.cprint_update(tool_call.function.output)

                    self.message_output = None

            @override
            def on_end(self):
                self.message_output = None

        self.recipient_agents = [str(agent.name) for agent in self.main_recipients]

        self._setup_autocomplete()  # Prepare readline for autocomplete

        while True:
            console.rule()
            text = input("👤 USER: ")

            if not text:
                continue

            if text.lower() == "exit":
                break

            recipient_agent = None
            if "@" in text:
                recipient_agent = text.split("@")[1].split(" ")[0]
                text = text.replace(f"@{recipient_agent}", "").strip()
                try:
                    recipient_agent = \
                        [agent for agent in self.recipient_agents if agent.lower() == recipient_agent.lower()][0]
                    recipient_agent = self._get_agent_by_name(recipient_agent)
                except Exception as e:
                    print(f"Recipient agent {recipient_agent} not found.")
                    continue

            self.get_completion_stream(message=text, event_handler=TermEventHandler, recipient_agent=recipient_agent)

    def get_customgpt_schema(self, url: str):
        """Returns the OpenAPI schema for the agency from the CEO agent, that you can use to integrate with custom gpts.

        Parameters:
            url (str): Your server url where the api will be hosted.
        """

        return self.ceo.get_openapi_schema(url)

    def plot_agency_chart(self):
        pass

    def _init_agents(self):
        """
        Initializes all agents in the agency with unique IDs, shared instructions, and OpenAI models.

        This method iterates through each agent in the agency, assigns a unique ID, adds shared instructions, and initializes the OpenAI models for each agent.

        There are no input parameters.

        There are no output parameters as this method is used for internal initialization purposes within the Agency class.
        """
        if self.settings_callbacks:
            loaded_settings = self.settings_callbacks["load"]()
            with open(self.settings_path, 'w') as f:
                json.dump(loaded_settings, f, indent=4)

        for agent in self.agents:
            if "temp_id" in agent.id:
                agent.id = None

            agent.add_shared_instructions(self.shared_instructions)
            agent.settings_path = self.settings_path

            if self.shared_files:
                if isinstance(self.shared_files, str):
                    self.shared_files = [self.shared_files]

                if isinstance(agent.files_folder, str):
                    agent.files_folder = [agent.files_folder]
                    agent.files_folder += self.shared_files
                elif isinstance(agent.files_folder, list):
                    agent.files_folder += self.shared_files

            if self.temperature is not None and agent.temperature is None:
                agent.temperature = self.temperature
            if self.top_p and agent.top_p is None:
                agent.top_p = self.top_p
            if self.max_prompt_tokens is not None and agent.max_prompt_tokens is None:
                agent.max_prompt_tokens = self.max_prompt_tokens
            if self.max_completion_tokens is not None and agent.max_completion_tokens is None:
                agent.max_completion_tokens = self.max_completion_tokens
            if self.truncation_strategy is not None and agent.truncation_strategy is None:
                agent.truncation_strategy = self.truncation_strategy
            
            if not agent.shared_state:
                agent.shared_state = self.shared_state

            agent.init_oai()

        if self.settings_callbacks:
            with open(self.agents[0].get_settings_path(), 'r') as f:
                settings = f.read()
            settings = json.loads(settings)
            self.settings_callbacks["save"](settings)

    def _init_threads(self):
        """
        Initializes threads for communication between agents within the agency.

        This method creates Thread objects for each pair of interacting agents as defined in the agents_and_threads attribute of the Agency. Each thread facilitates communication and task execution between an agent and its designated recipient agent.

        No input parameters.

        Output Parameters:
            This method does not return any value but updates the agents_and_threads attribute with initialized Thread objects.
        """
        self.main_thread = Thread(self.user, self.ceo)

        # load thread ids
        loaded_thread_ids = {}
        if self.threads_callbacks:
            loaded_thread_ids = self.threads_callbacks["load"]()
            if "main_thread" in loaded_thread_ids and loaded_thread_ids["main_thread"]:
                self.main_thread.id = loaded_thread_ids["main_thread"]
            else:
                self.main_thread.init_thread()

        # Save main_thread into agents_and_threads
        self.agents_and_threads["main_thread"] = self.main_thread

        # initialize threads
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            for other_agent, items in threads.items():
                # create thread class
                self.agents_and_threads[agent_name][other_agent] = self._thread_type(
                    self._get_agent_by_name(items["agent"]),
                    self._get_agent_by_name(
                        items["recipient_agent"]))

                # load thread id if available
                if agent_name in loaded_thread_ids and other_agent in loaded_thread_ids[agent_name]:
                    self.agents_and_threads[agent_name][other_agent].id = loaded_thread_ids[agent_name][other_agent]
                # init threads if threre are threads callbacks so the ids are saved for later use
                elif self.threads_callbacks:
                    self.agents_and_threads[agent_name][other_agent].init_thread()

        # save thread ids
        if self.threads_callbacks:
            loaded_thread_ids = {}
            for agent_name, threads in self.agents_and_threads.items():
                if agent_name == "main_thread":
                    continue
                loaded_thread_ids[agent_name] = {}
                for other_agent, thread in threads.items():
                    loaded_thread_ids[agent_name][other_agent] = thread.id

            loaded_thread_ids["main_thread"] = self.main_thread.id

            self.threads_callbacks["save"](loaded_thread_ids)

    def _parse_agency_chart(self, agency_chart):
        """
        Parses the provided agency chart to initialize and organize agents within the agency.

        Parameters:
            agency_chart: A structure representing the hierarchical organization of agents within the agency.
                    It can contain Agent objects and lists of Agent objects.

        This method iterates through each node in the agency chart. If a node is an Agent, it is set as the CEO if not already assigned.
        If a node is a list, it iterates through the agents in the list, adding them to the agency and establishing communication
        threads between them. It raises an exception if the agency chart is invalid or if multiple CEOs are defined.
        """
        if not isinstance(agency_chart, list):
            raise Exception("Invalid agency chart.")

        if len(agency_chart) == 0:
            raise Exception("Agency chart cannot be empty.")

        for node in agency_chart:
            if isinstance(node, Agent):
                if not self.ceo:
                    self.ceo = node
                    self._add_agent(self.ceo)
                else:
                    self._add_agent(node)
                self._add_main_recipient(node)

            elif isinstance(node, list):
                for i, agent in enumerate(node):
                    if not isinstance(agent, Agent):
                        raise Exception("Invalid agency chart.")

                    index = self._add_agent(agent)

                    if i == len(node) - 1:
                        continue

                    if agent.name not in self.agents_and_threads.keys():
                        self.agents_and_threads[agent.name] = {}

                    if i < len(node) - 1:
                        other_agent = node[i + 1]
                        if other_agent.name == agent.name:
                            continue
                        if other_agent.name not in self.agents_and_threads[agent.name].keys():
                            self.agents_and_threads[agent.name][other_agent.name] = {
                                "agent": agent.name,
                                "recipient_agent": other_agent.name,
                            }
            else:
                raise Exception("Invalid agency chart.")

    def _add_agent(self, agent):
        """
        Adds an agent to the agency, assigning a temporary ID if necessary.

        Parameters:
            agent (Agent): The agent to be added to the agency.

        Returns:
            int: The index of the added agent within the agency's agents list.

        This method adds an agent to the agency's list of agents. If the agent does not have an ID, it assigns a temporary unique ID. It checks for uniqueness of the agent's name before addition. The method returns the index of the agent in the agency's agents list, which is used for referencing the agent within the agency.
        """
        if not agent.id:
            # assign temp id
            agent.id = "temp_id_" + str(uuid.uuid4())
        if agent.id not in self._get_agent_ids():
            if agent.name in self._get_agent_names():
                raise Exception("Agent names must be unique.")
            self.agents.append(agent)
            return len(self.agents) - 1
        else:
            return self._get_agent_ids().index(agent.id)

    def _add_main_recipient(self, agent):
        """
        Adds an agent to the agency's list of main recipients.

        Parameters:
            agent (Agent): The agent to be added to the agency's list of main recipients.

        This method adds an agent to the agency's list of main recipients. These are agents that can be directly contacted by the user.
        """
        main_recipient_ids = [agent.id for agent in self.main_recipients]

        if agent.id not in main_recipient_ids:
            self.main_recipients.append(agent)

    def _read_instructions(self, path):
        """
        Reads shared instructions from a specified file and stores them in the agency.

        Parameters:
            path (str): The file path from which to read the shared instructions.

        This method opens the file located at the given path, reads its contents, and stores these contents in the 'shared_instructions' attribute of the agency. This is used to provide common guidelines or instructions to all agents within the agency.
        """
        path = path
        with open(path, 'r') as f:
            self.shared_instructions = f.read()

    def _create_special_tools(self):
        """
        Creates and assigns 'SendMessage' tools to each agent based on the agency's structure.

        This method iterates through the agents and threads in the agency, creating SendMessage tools for each agent. These tools enable agents to send messages to other agents as defined in the agency's structure. The SendMessage tools are tailored to the specific recipient agents that each agent can communicate with.

        No input parameters.

        No output parameters; this method modifies the agents' toolset internally.
        """
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            recipient_names = list(threads.keys())
            recipient_agents = self._get_agents_by_names(recipient_names)
            if len(recipient_agents) == 0:
                continue
            agent = self._get_agent_by_name(agent_name)
            agent.add_tool(self._create_send_message_tool(agent, recipient_agents))
            if self._thread_type == ThreadAsync:
                agent.add_tool(self._create_get_response_tool(agent, recipient_agents))

    def _create_send_message_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a SendMessage tool to enable an agent to send messages to specified recipient agents.


        Parameters:
            agent (Agent): The agent who will be sending messages.
            recipient_agents (List[Agent]): A list of recipient agents who can receive messages.

        Returns:
            SendMessage: A SendMessage tool class that is dynamically created and configured for the given agent and its recipient agents. This tool allows the agent to send messages to the specified recipients, facilitating inter-agent communication within the agency.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        agent_descriptions = ""
        for recipient_agent in recipient_agents:
            if not recipient_agent.description:
                continue
            agent_descriptions += recipient_agent.name + ": "
            agent_descriptions += recipient_agent.description + "\n"

        class SendMessage(self.send_message_tool_class):
            recipient: recipients = Field(..., description=agent_descriptions)

            @field_validator('recipient')
            @classmethod
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

        SendMessage._caller_agent = agent
        SendMessage._agents_and_threads = self.agents_and_threads

        return SendMessage

    def _create_get_response_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a CheckStatus tool to enable an agent to check the status of a task with a specified recipient agent.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        outer_self = self

        class GetResponse(BaseTool):
            """This tool allows you to check the status of a task or get a response from a specified recipient agent, if the task has been completed. You must always use 'SendMessage' tool with the designated agent first."""
            recipient: recipients = Field(...,
                                          description=f"Recipient agent that you want to check the status of. Valid recipients are: {recipient_names}")

            @field_validator('recipient')
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

            def run(self):
                thread = outer_self.agents_and_threads[self._caller_agent.name][self.recipient.value]

                return thread.check_status()

        GetResponse._caller_agent = agent

        return GetResponse

    def _get_agent_by_name(self, agent_name):
        """
        Retrieves an agent from the agency based on the agent's name.

        Parameters:
            agent_name (str): The name of the agent to be retrieved.

        Returns:
            Agent: The agent object with the specified name.

        Raises:
            Exception: If no agent with the given name is found in the agency.
        """
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        raise Exception(f"Agent {agent_name} not found.")

    def _get_agents_by_names(self, agent_names):
        """
        Retrieves a list of agent objects based on their names.

        Parameters:
            agent_names: A list of strings representing the names of the agents to be retrieved.

        Returns:
            A list of Agent objects corresponding to the given names.
        """
        return [self._get_agent_by_name(agent_name) for agent_name in agent_names]

    def _get_agent_ids(self):
        """
        Retrieves the IDs of all agents currently in the agency.

        Returns:
            List[str]: A list containing the unique IDs of all agents.
        """
        return [agent.id for agent in self.agents]

    def _get_agent_names(self):
        """
        Retrieves the names of all agents in the agency.

        Returns:
            List[str]: A list of names of all agents currently part of the agency.
        """
        return [agent.name for agent in self.agents]

    def _get_class_folder_path(self):
        """
        Retrieves the absolute path of the directory containing the class file.

        Returns:
            str: The absolute path of the directory where the class file is located.
        """
        return os.path.abspath(os.path.dirname(inspect.getfile(self.__class__)))

    def delete(self):
        """
        This method deletes the agency and all its agents, cleaning up any files and vector stores associated with each agent.
        """
        for agent in self.agents:
            agent.delete()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\AgentCreator.py
================================================
from agency_swarm import Agent
from .tools.ImportAgent import ImportAgent
from .tools.CreateAgentTemplate import CreateAgentTemplate
from .tools.ReadManifesto import ReadManifesto

class AgentCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new agents for the agency.",
            instructions="./instructions.md",
            tools=[ImportAgent, CreateAgentTemplate, ReadManifesto],
            temperature=0.3,
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\instructions.md
================================================
# AgentCreator Agent Instructions

You are an agent that creates other agents as instructed by the user. 

The user will communicate to you each agent that needs to be created. Below are your instructions that needs to be followed for each agent communicated by the user.

**Primary Instructions:**
1. First, read the manifesto using `ReadManifesto` tool if you have not already done so. This file contains the agency manifesto that describes the agency's purpose and goals.
2. If a similar agent to the requested one is accessible through the `ImportAgent` tool, import this agent and inform the user that the agent has been created. Skip the following steps.
3. If not, create a new agent using `CreateAgentTemplate` tool. 
4. Tell the `ToolCreator` agent to create tools or APIs for this agent. Make sure to also communicate the agent description, name and a summary of the processes that it needs to perform. CEO Agents do not need to utilize any tools, so you can skip this and the following steps.
5. If there are no issues and tools have been successfully created, notify the user that the agent has been created. Otherwise, try to resolve any issues with the tool creator before reporting back to the user.
6. Repeat this process for each agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\CreateAgentTemplate.py
================================================
import os
import shutil
from typing import List

from pydantic import Field, model_validator

from agency_swarm import BaseTool
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.util import create_agent_template

allowed_tools: List = ["CodeInterpreter"]

web_developer_example_instructions = """# Web Developer Agent Instructions

You are an agent that builds responsive web applications using Next.js and Material-UI (MUI). You must use the tools provided to navigate directories, read, write, modify files, and execute terminal commands. 

### Primary Instructions:
1. Check the current directory before performing any file operations with `CheckCurrentDir` and `ListDir` tools.
2. Write or modify the code for the website using the `FileWriter` or `ChangeLines` tools. Make sure to use the correct file paths and file names. Read the file first if you need to modify it.
3. Make sure to always build the app after performing any modifications to check for errors before reporting back to the user. Keep in mind that all files must be reflected on the current website
4. Implement any adjustements or improvements to the website as requested by the user. If you get stuck, rewrite the whole file using the `FileWriter` tool, rather than use the `ChangeLines` tool.
"""


class CreateAgentTemplate(BaseTool):
    """
    This tool creates a template folder for a new agent. Always use this tool first, before creating tools or APIs for the agent.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to be created. Cannot include special characters or spaces."
    )
    agent_description: str = Field(
        ..., description="Description of the agent to be created."
    )
    instructions: str = Field(
        ..., description="Instructions for the agent to be created in markdown format. "
                         "Instructions should include a decription of the role and a specific step by step process "
                         "that this agent need to perform in order to execute the tasks. "
                         "The process must also be aligned with all the other agents in the agency. Agents should be "
                         "able to collaborate with each other to achieve the common goal of the agency.",
        examples=[
            web_developer_example_instructions,
        ]
    )
    default_tools: List[str] = Field(
        [], description=f"List of default tools to be included in the agent. Possible values are {allowed_tools}."
                        f"CodeInterpreter allows the agent to execute python code in a remote python environment.",
        example=["CodeInterpreter"],
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("manifesto_read"):
            raise ValueError("Please read the manifesto first with the ReadManifesto tool.")

        self._shared_state.set("agent_name", self.agent_name)

        os.chdir(self._shared_state.get("agency_path"))

        # remove folder if it already exists
        if os.path.exists(self.agent_name):
            shutil.rmtree(self.agent_name)

        create_agent_template(self.agent_name,
                              self.agent_description,
                              instructions=self.instructions,
                              code_interpreter=True if "CodeInterpreter" in self.default_tools else None,
                              include_example_tool=False)

        # # create or append to init file
        path = self._shared_state.get("agency_path")
        class_name = self.agent_name.replace(" ", "").strip()
        if not os.path.isfile("__init__.py"):
            with open("__init__.py", "w") as f:
                f.write(f"from .{class_name} import {class_name}")
        else:
            with open("__init__.py", "a") as f:
                f.write(f"\nfrom .{class_name} import {class_name}")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {class_name} import {class_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        if "ceo" in self.agent_name.lower():
            return f"You can tell the user that the process of creating {self.agent_name} has been completed, because CEO agent does not need to utilizie any tools or APIs."

        return f"Agent template has been created for {self.agent_name}. Please now tell ToolCreator to create tools for this agent or OpenAPICreator to create API schemas, if this agent needs to utilize any tools or APIs. If this is unclear, please ask the user for more information."

    @model_validator(mode="after")
    def validate_tools(self):
        check_agency_path(self)

        for tool in self.default_tools:
            if tool not in allowed_tools:
                raise ValueError(f"Tool {tool} is not allowed. Allowed tools are: {allowed_tools}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ImportAgent.py
================================================
import os

from pydantic import Field, field_validator

from agency_swarm import BaseTool
from agency_swarm.util.cli import import_agent
from agency_swarm.util.helpers import get_available_agent_descriptions, list_available_agents


class ImportAgent(BaseTool):
    """
    This tool imports an existing agent from agency swarm framework. Please make sure to first use the GetAvailableAgents tool to get the list of available agents.
    """
    agent_name: str = Field(...,
                            description=get_available_agent_descriptions())
    agency_path: str = Field(
        None, description="Path to the agency where the agent will be imported. Default is the current agency.")

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set("default_folder", os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_path:
            return "Error: You must set the agency_path."

        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
        else:
            os.chdir(self.agency_path)

        import_agent(self.agent_name, "./")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {self.agent_name} import {self.agent_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        return (f"Success. {self.agent_name} has been imported. "
                f"You can now tell the user to user proceed with next agents.")

    @field_validator("agent_name", mode='after')
    @classmethod
    def agent_name_exists(cls, v):
        available_agents = list_available_agents()
        if v not in available_agents:
            raise ValueError(
                f"Agent with name {v} does not exist. Available agents are: {available_agents}")
        return v

if __name__ == "__main__":
    tool = ImportAgent(agent_name="Devid")
    tool._shared_state.set("agency_path", "./")
    tool.run()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ReadManifesto.py
================================================
import os

from pydantic import Field

from agency_swarm import BaseTool


class ReadManifesto(BaseTool):
    """
    This tool reads a manifesto for the agency being created from a markdown file.
    """
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_name:
            raise ValueError("Please specify the agency name. Ask user for clarification if needed.")

        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))

        with open("agency_manifesto.md", "r") as f:
            manifesto = f.read()

        os.chdir(self._shared_state.get("default_folder"))

        self._shared_state.set("manifesto_read", True)

        return manifesto


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\get_modules.py
================================================
import importlib.resources
import pathlib


def get_modules(module_name):
    """
    Get all submodule names from a given module based on file names, without importing them,
    excluding those containing '.agent' or '.genesis' in their paths.

    Args:
    - module_name: The name of the module to search through.

    Returns:
    - A list of submodule names found within the given module.
    """
    submodule_names = []

    try:
        # Using importlib.resources to access the package contents
        with importlib.resources.path(module_name, '') as package_path:
            # Walk through the package directory using pathlib
            for path in pathlib.Path(package_path).rglob('*.py'):
                if path.name != '__init__.py':
                    # Construct the module name from the file path
                    relative_path = path.relative_to(package_path)
                    module_path = '.'.join(relative_path.with_suffix('').parts)

                    submodule_names.append(f"{module_name}.{module_path}")

    except ImportError:
        print(f"Module {module_name} not found.")
        return submodule_names

    submodule_names = [name for name in submodule_names if not name.endswith(".agent") and
                       '.genesis' not in name and
                       'util' not in name and
                       'oai' not in name and
                       'ToolFactory' not in name and
                       'BaseTool' not in name]

    # remove repetition at the end of the path like 'agency_swarm.agents.coding.CodingAgent.CodingAgent'
    for i in range(len(submodule_names)):
        splitted = submodule_names[i].split(".")
        if splitted[-1] == splitted[-2]:
            submodule_names[i] = ".".join(splitted[:-1])

    return submodule_names


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\__init__.py
================================================
from .get_modules import get_modules

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\__init__.py
================================================
from .AgentCreator import AgentCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisAgency.py
================================================
from agency_swarm import Agency
from .AgentCreator import AgentCreator

from .GenesisCEO import GenesisCEO
from .OpenAPICreator import OpenAPICreator
from .ToolCreator import ToolCreator
from agency_swarm.util.helpers import get_available_agent_descriptions

class GenesisAgency(Agency):
    def __init__(self, with_browsing=True, **kwargs):
        if "max_prompt_tokens" not in kwargs:
            kwargs["max_prompt_tokens"] = 25000

        if 'agency_chart' not in kwargs:
            agent_creator = AgentCreator()
            genesis_ceo = GenesisCEO()
            tool_creator = ToolCreator()
            openapi_creator = OpenAPICreator()
            kwargs['agency_chart'] = [
                genesis_ceo, tool_creator, agent_creator,
                [genesis_ceo, agent_creator],
                [agent_creator, tool_creator],
            ]

            if with_browsing:
                from agency_swarm.agents.BrowsingAgent import BrowsingAgent
                browsing_agent = BrowsingAgent()

                browsing_agent.instructions += ("""\n
# BrowsingAgent's Primary instructions
1. Browse the web to find the API documentation requested by the user. Prefer searching google directly for this API documentation page.
2. Navigate to the API documentation page and ensure that it contains the necessary API endpoints descriptions. You can use the AnalyzeContent tool to check if the page contains the necessary API descriptions. If not, try perform another search in google and keep browsing until you find the right page.
3. If you have confirmed that the page contains the necessary API documentation, export the page with ExportFile tool. Then, send the file_id back to the user along with a brief description of the API.
4. Repeat these steps for each new agent, as requested by the user.
                """)
                kwargs['agency_chart'].append(openapi_creator)
                kwargs['agency_chart'].append([openapi_creator, browsing_agent])

        if 'shared_instructions' not in kwargs:
            kwargs['shared_instructions'] = "./manifesto.md"

        super().__init__(**kwargs)


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\GenesisCEO.py
================================================
from pathlib import Path

from agency_swarm import Agent
from .tools.CreateAgencyFolder import CreateAgencyFolder
from .tools.FinalizeAgency import FinalizeAgency
from .tools.ReadRequirements import ReadRequirements


class GenesisCEO(Agent):
    def __init__(self):
        super().__init__(
            description="Acts as the overseer and communicator across the agency, ensuring alignment with the "
                        "agency's goals.",
            instructions="./instructions.md",
            tools=[CreateAgencyFolder, FinalizeAgency, ReadRequirements],
            temperature=0.4,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\instructions.md
================================================
# GenesisCEO Agent Instructions

As a Genesis CEO Agent within the Agency Swarm framework, your mission is to help users define the structure of their agency and create the initial agents.

1. Pick a name for the agency, determine its goals and mission. Ask the user for any clarification if needed.
2. Propose an initial structure for the agency, including the roles of the agents, their communication flows and what APIs or Tools each agent can use, if specified by the user. Focus on creating at most 2 agents, plus CEO, unless instructed otherwise by the user. Do not name the CEO agent GenesisCEO. It's name must be tailored for the purpose of the agency. Output the code snippet like below. Adjust it accordingly, based on user's input.
3. Upon confirmation of the agency structure, use `CreateAgencyFolder` tool to create a folder for the agency. If any modifications are required please use this tool again with the same agency name and it will overwrite the existing folder.
4. Tell AgentCreator to create these agents one by one, starting with the CEO. Each agent should be sent in a separate message using the `SendMessage` tool. Please make sure to include the agent description, summary of the processes it needs to perform and the APIs or Tools that it can use via the message parameter.
5. Once all agents are created, please use the `FinalizeAgency` tool, and tell the user that he can now navigate to the agency folder and start it with `python agency.py` command.


### Example of communication flows

Here is an example of how communication flows are defined in agency swarm. Essentially, agents that are inside a double array can initiate communication with each other. Agents that are in the top level array can communicate with the user. 

```python
agency = Agency([
    ceo, dev,  # CEO and Developer will be the entry point for communication with the user
    [ceo, dev],  # CEO can initiate communication with Developer
    [ceo, va],   # CEO can initiate communication with Virtual Assistant
    [dev, va]    # Developer can initiate communication with Virtual Assistant
], shared_instructions='agency_manifesto.md') # shared instructions for all agents
```
Keep in mind that this is just an example and you should replace it with the actual agents you are creating. Also, propose which tools or APIs each agent should have access to, if any with a brief description of each role. Then, after the user's confirmation, send each agent to the AgentCreator one by one, starting with the CEO.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\CreateAgencyFolder.py
================================================
import shutil
from pathlib import Path

from pydantic import Field, field_validator, model_validator

import agency_swarm.agency.genesis.GenesisAgency
from agency_swarm import BaseTool

import os


class CreateAgencyFolder(BaseTool):
    """
    This tool creates or modifies an agency folder. You can use it again with the same agency_name to modify a previously created agency, if the user wants to change the agency chart or the manifesto.
    """
    agency_name: str = Field(
        ..., description="Name of the agency to be created. Must not contain spaces or special characters.",
        examples=["AgencyName", "MyAgency", "ExampleAgency"]
    )
    agency_chart: str = Field(
        ..., description="Agency chart to be passed into the Agency class.",
        examples=["[ceo, [ceo, dev], [ceo, va], [dev, va]]"]
    )
    manifesto: str = Field(
        ..., description="Manifesto for the agency, describing its goals and additional context shared by all agents "
                         "in markdown format. It must include information about the working environment, the mission "
                         "and the goals of the agency. Do not add descriptions of the agents themselves or the agency structure.",
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', Path.cwd())

        if self._shared_state.get("agency_name") is None:
            os.mkdir(self.agency_name)
            os.chdir("./" + self.agency_name)
            self._shared_state.set("agency_name", self.agency_name)
            self._shared_state.set("agency_path", Path("./").resolve())
        elif self._shared_state.get("agency_name") == self.agency_name and os.path.exists(self._shared_state.get("agency_path")):
            os.chdir(self._shared_state.get("agency_path"))
            for file in os.listdir():
                if file != "__init__.py" and os.path.isfile(file):
                    os.remove(file)
        else:
            os.mkdir(self._shared_state.get("agency_path"))
            os.chdir("./" + self.agency_name)

        # check that agency chart is valid
        if not self.agency_chart.startswith("[") or not self.agency_chart.endswith("]"):
            raise ValueError("Agency chart must be a list of lists, except for the first agents.")

        # add new lines after every comma, except for those inside second brackets
        # must transform from "[ceo, [ceo, dev], [ceo, va], [dev, va] ]"
        # to "[ceo, [ceo, dev],\n [ceo, va],\n [dev, va] ]"
        agency_chart = self.agency_chart.replace("],", "],\n")

        # create init file
        with open("__init__.py", "w") as f:
            f.write("")

        # create agency.py
        with open("agency.py", "w") as f:
            f.write(agency_py.format(agency_chart=agency_chart))

        # write manifesto
        path = os.path.join("agency_manifesto.md")
        with open(path, "w") as f:
            f.write(self.manifesto)

        os.chdir(self._shared_state.get('default_folder'))

        return f"Agency folder has been created. You can now tell AgentCreator to create agents for {self.agency_name}.\n"


agency_py = """from agency_swarm import Agency


agency = Agency({agency_chart},
                shared_instructions='./agency_manifesto.md', # shared instructions for all agents
                max_prompt_tokens=25000, # default tokens in conversation for all agents
                temperature=0.3, # default temperature for all agents
                )
                
if __name__ == '__main__':
    agency.demo_gradio()
"""

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\FinalizeAgency.py
================================================
import os
from typing import List

from pydantic import Field, model_validator, field_validator

from agency_swarm import BaseTool, get_openai_client
from agency_swarm.util import create_agent_template


class FinalizeAgency(BaseTool):
    """
    This tool finalizes the agency structure and it's imports. Please make sure to use at only at the very end, after all agents have been created.
    """
    agency_path: str = Field(
        None, description="Path to the agency folder. Defaults to the agency currently being created."
    )

    def run(self):
        agency_path = None
        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
            agency_path = self._shared_state.get("agency_path")
        else:
            os.chdir(self.agency_path)
            agency_path = self.agency_path

        client = get_openai_client()

        # read agency.py
        with open("./agency.py", "r") as f:
            agency_py = f.read()
            f.close()

        res = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=examples + [
                {'role': "user", 'content': agency_py},
            ],
            temperature=0.0,
        )

        message = res.choices[0].message.content

        # write agency.py
        with open("./agency.py", "w") as f:
            f.write(message)
            f.close()

        return f"Successfully finalized {agency_path} structure. You can now instruct the user to run the agency.py file."

    @model_validator(mode="after")
    def validate_agency_path(self):
        if not self._shared_state.get("agency_path") and not self.agency_path:
            raise ValueError("Agency path not found. Please specify the agency_path. Ask user for clarification if needed.")


SYSTEM_PROMPT = """"Please read the file provided by the user and fix all the imports and indentation accordingly. 

Only output the full valid python code and nothing else."""

example_input = """
from agency_swarm import Agency

from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent


agency = Agency([ceo, [ceo, news_analysis],
 [ceo, price_tracking],
 [news_analysis, price_tracking]],
shared_instructions='./agency_manifesto.md')

if __name__ == '__main__':
    agency.demo_gradio()
"""

example_output = """from agency_swarm import Agency
from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent

ceo = CEO()
news_analysis = NewsAnalysisAgent()
price_tracking = PriceTrackingAgent()

agency = Agency([ceo, [ceo, market_analyst],
                 [ceo, news_curator],
                 [market_analyst, news_curator]],
                shared_instructions='./agency_manifesto.md')
    
if __name__ == '__main__':
    agency.demo_gradio()"""

examples = [
    {'role': "system", 'content': SYSTEM_PROMPT},
    {'role': "user", 'content': example_input},
    {'role': "assistant", 'content': example_output}
]


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\ReadRequirements.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field
import os


class ReadRequirements(BaseTool):
    """
    Use this tool to read the agency requirements if user provides them as a file.
    """

    file_path: str = Field(
        ..., description="The path to the file that needs to be read."
    )

    def run(self):
        """
        Checks if the file exists, and if so, opens the specified file, reads its contents, and returns them.
        If the file does not exist, raises a ValueError.
        """
        if not os.path.exists(self.file_path):
            raise ValueError(f"File path does not exist: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except Exception as e:
            return f"An error occurred while reading the file: {str(e)}"


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\__init__.py
================================================
from .GenesisCEO import GenesisCEO

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\manifesto.md
================================================
# Genesis Agency Manifesto

You are a part of a Genesis Agency for a framework called Agency Swarm. The goal of your agency is to create other agencies within this framework. Below is a brief description of the framework.

**Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the AI agent creation process and enable anyone to create a collaborative swarms of agents (Agencies), each with distinct roles and capabilities. These agents must function autonomously, yet collaborate with other agents to achieve a common goal.**

Keep in mind that communication with the other agents within your agency via the `SendMessage` tool is synchronous. Other agents will not be executing any tasks post response. Please instruct the recipient agent to continue its execution, if needed. Do not report to the user before the recipient agent has completed its task. If the agent proposes the next steps, for example, you must instruct the recipient agent to execute them.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\instructions.md
================================================
# OpenAPICreator Instructions

You are an agent that creates tools from OpenAPI schemas. User will provide you with a description of the agent's role. If the provided description does not require any API calls, please notify the user.

**Here are your primary instructions:**
1. Think which API is needed for this agent's role, as communicated by the user. Then, tell the BrowsingAgent to find this API documentation page.
2. Explore the provided file from the BrowsingAgent with the `myfiles_broswer` tool to determine which endpoints are needed for this agent's role.
3. If the file does not contain the actual API documentation page, please notify the BrowsingAgent. Keep in mind that you do not need the full API documentation. You can make an educated guess if some information is not available.
4. Use `CreateToolsFromOpenAPISpec` to create the tools by defining the OpenAPI schema accordingly. Make sure to include all the relevant API endpoints that are needed for this agent to execute its role from the provided file. Do not truncate the schema.
5. Repeat these steps for each new agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\OpenAPICreator.py
================================================
from agency_swarm import Agent
from .tools.CreateToolsFromOpenAPISpec import CreateToolsFromOpenAPISpec


class OpenAPICreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools from an OpenAPI specifications.",
            instructions="./instructions.md",
            tools=[CreateToolsFromOpenAPISpec]
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\tools\CreateToolsFromOpenAPISpec.py
================================================
import os

from pydantic import Field, field_validator, model_validator

from agency_swarm import BaseTool

import json

from agency_swarm.agency.genesis.util import check_agency_path, check_agent_path
from agency_swarm.tools import ToolFactory
from agency_swarm.util.openapi import validate_openapi_spec


class CreateToolsFromOpenAPISpec(BaseTool):
    """
    This tool creates a set of tools from an OpenAPI specification. Each method in the specification is converted to a separate tool.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to create the API for. Must be an existing agent."
    )
    openapi_spec: str = Field(
        ..., description="OpenAPI specification for the tool to be created as a valid JSON string. Only the relevant "
                         "endpoints must be included. Responses are not required. Each method should contain "
                         "an operation id and a description. Do not truncate this schema. "
                         "It must be a full valid OpenAPI 3.1.0 specification.",
        examples=[
            '{\n  "openapi": "3.1.0",\n  "info": {\n    "title": "Get weather data",\n    "description": "Retrieves current weather data for a location.",\n    "version": "v1.0.0"\n  },\n  "servers": [\n    {\n      "url": "https://weather.example.com"\n    }\n  ],\n  "paths": {\n    "/location": {\n      "get": {\n        "description": "Get temperature for a specific location",\n        "operationId": "GetCurrentWeather",\n        "parameters": [\n          {\n            "name": "location",\n            "in": "query",\n            "description": "The city and state to retrieve the weather for",\n            "required": true,\n            "schema": {\n              "type": "string"\n            }\n          }\n        ],\n        "deprecated": false\n      }\n    }\n  },\n  "components": {\n    "schemas": {}\n  }\n}'])
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        os.chdir(self._shared_state.get("agency_path"))

        os.chdir(self.agent_name)

        try:
            try:
                tools = ToolFactory.from_openapi_schema(self.openapi_spec)
            except Exception as e:
                raise ValueError(f"Error creating tools from OpenAPI Spec: {e}")

            if len(tools) == 0:
                return "No tools created. Please check the OpenAPI specification."

            tool_names = [tool.__name__ for tool in tools]

            # save openapi spec
            folder_path = "./" + self.agent_name + "/"
            os.chdir(folder_path)

            api_name = json.loads(self.openapi_spec)["info"]["title"]

            api_name = api_name.replace("API", "Api").replace(" ", "")

            api_name = ''.join(['_' + i.lower() if i.isupper() else i for i in api_name]).lstrip('_')

            with open("schemas/" + api_name + ".json", "w") as f:
                f.write(self.openapi_spec)

            return "Successfully added OpenAPI Schema to " + self._shared_state.get("agent_name")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

    @field_validator("openapi_spec", mode='before')
    @classmethod
    def validate_openapi_spec(cls, v):
        try:
            validate_openapi_spec(v)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format:", e)
        except Exception as e:
            raise ValueError("Error validating OpenAPI schema:", e)
        return v

    @model_validator(mode="after")
    def validate_agent_name(self):
        check_agency_path(self)

        check_agent_path(self)



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\__init__.py
================================================
from .OpenAPICreator import OpenAPICreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\instructions.md
================================================
# ToolCreator Agent Instructions

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

**Here are your primary instructions:**
1. Determine which tools the agent must utilize to perform it's role. Make an educated guess if the user has not specified any tools or APIs. Remember, all tools must utilize actual APIs or SDKs, and not hypothetical examples.
2. Create these tools one at a time, using `CreateTool` tool.
3. Test each tool with the `TestTool` function to ensure it is working as expected. Do not ask the user, always test the tool yourself, if it does not require any API keys and all the inputs can be mocked.
4. Only after all the necessary tools are created, notify the user.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\ToolCreator.py
================================================
from agency_swarm import Agent
from .tools.CreateTool import CreateTool
from .tools.TestTool import TestTool


class ToolCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools for the agency using python code.",
            instructions="./instructions.md",
            tools=[CreateTool, TestTool],
            temperature=0,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\tools\CreateTool.py
================================================
import os
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agency_swarm import get_openai_client
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.tools import BaseTool

prompt = """# Agency Swarm Overview

Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the agent creation process and enable anyone to create a collaborative swarm of agents (Agencies), each with distinct roles and capabilities. 

# ToolCreator Agent Instructions for Agency Swarm Framework

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

### Tool Creation Guide

When creating a tool, you are essentially defining a new class that extends `BaseTool`. This process involves several key steps, outlined below.

#### 1. Import Necessary Modules

Start by importing `BaseTool` from `agency_swarm.tools` and `Field` from `pydantic`. These imports will serve as the foundation for your custom tool class. Import any additional packages necessary to implement the tool's logic.

#### 2. Define Your Tool Class

Create a new class that inherits from `BaseTool`. This class will encapsulate the functionality of your tool. `BaseTool` class inherits from the Pydantic's `BaseModel` class.

#### 3. Specify Tool Fields

Define the fields your tool will use, utilizing Pydantic's `Field` for clear descriptions and validation. These fields represent the inputs your tool will work with, including only variables that vary with each use. Define any constant variables like api keys globally.

#### 4. Implement the `run` Method

The `run` method is where your tool's logic is executed. Use the fields defined earlier to perform the tool's intended task. It must contain the actual fully functional correct python code. It can utilize various python packages, previously imported in step 1. Do not include any placeholders or hypothetical examples in the code.

### Example of a Custom Tool

```python
from agency_swarm.tools import BaseTool
from pydantic import Field
import os

account_id = "MY_ACCOUNT_ID"
api_key = os.getenv("MY_API_KEY") # or access_token = os.getenv("MY_ACCESS_TOKEN")

class MyCustomTool(BaseTool):
    \"\"\"
    A brief description of what the custom tool does.
    The docstring should clearly explain the tool's purpose and functionality.
    It will be used by the agent to determine when to use this tool.
    \"\"\"

    # Define the fields with descriptions using Pydantic Field
    example_field: str = Field(
        ..., description="Description of the example field, explaining its purpose and usage for the Agent."
    )

    def run(self):
        \"\"\"
        The implementation of the run method, where the tool's main functionality is executed.
        This method should utilize the fields defined above to perform the task.
        \"\"\"
        # Your custom tool logic goes here
        # Example: 
        # do_something(self.example_field, api_key, account_id)

        # Return the result of the tool's operation as a string
        return "Result of MyCustomTool operation"
```

To share state between 2 or more tools, you can use the `shared_state` attribute of the tool. It is a dictionary that can be used to store and retrieve values across different tools. This can be useful for passing information between tools or agents. Here is an example of how to use the `shared_state`:

```python
class MyCustomTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        # Update the shared state
        self._shared_state.set("key", "value")
        
        return "Result of MyCustomTool operation"
        
# Access shared state in another tool
class AnotherTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        return "Result of AnotherTool operation"
```

This is useful to pass information between tools or agents or to verify the state of the system.  

Remember, you must output the resulting python tool code as a whole in a code block, so the user can just copy and paste it into his program. Each tool code snippet must be ready to use. It must not contain any placeholders or hypothetical examples."""

history = [
            {
                "role": "system",
                "content": prompt
            },
        ]


class CreateTool(BaseTool):
    """This tool creates other custom tools for the agent, based on your requirements and details."""
    agent_name: str = Field(
        ..., description="Name of the agent to create the tool for."
    )
    tool_name: str = Field(..., description="Name of the tool class in camel case.", examples=["ExampleTool"])
    requirements: str = Field(
        ...,
        description="The comprehensive requirements explaning the primary functionality of the tool. It must not contain any code or implementation details."
    )
    details: str = Field(
        None, description="Additional details or error messages, class, function, and variable names."
    )
    mode: Literal["write", "modify"] = Field(
        ..., description="The mode of operation for the tool. 'write' is used to create a new tool or overwrite an existing one. 'modify' is used to modify an existing tool."
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))
        os.chdir(self.agent_name)

        client = get_openai_client()

        if self.mode == "write":
            message = f"Please create a '{self.tool_name}' tool that meets the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."
        else:
            message = f"Please rewrite a '{self.tool_name}' according to the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."

        if self.details:
            message += f"\nAdditional Details: {self.details}"

        if self.mode == "modify":
            message += f"\nThe existing file content is as follows:"

            try:
                with open("./tools/" + self.tool_name + ".py", 'r') as file:
                    prev_content = file.read()
                    message += f"\n\n```{prev_content}```"
            except Exception as e:
                os.chdir(self._shared_state.get("default_folder"))
                return f'Error reading {self.tool_name}: {e}'

        history.append({
                "role": "user",
                "content": message
            })

        messages = history.copy()

        # use the last 6 messages
        messages = messages[-6:]

        # add system message upfront
        messages.insert(0, history[0])

        n = 0
        code = ""
        content = ""
        while n < 3:
            resp = client.chat.completions.create(
                messages=messages,
                model="gpt-4o",
                temperature=0,
            )

            content = resp.choices[0].message.content

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            pattern = r"```(?:[a-zA-Z]+\n)?(.*?)```"
            match = re.findall(pattern, content, re.DOTALL)
            if match:
                code = match[-1].strip()
                history.append(
                    {
                        "role": "assistant",
                        "content": content
                    }
                )
                break
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: Could not find the python code block in the response. Please try again."
                    }
                )

            n += 1

        if n == 3 or not code:
            # remove last message from history
            history.pop()
            os.chdir(self._shared_state.get("default_folder"))
            return "Error: Could not generate a valid file."
        try:
            with open("./tools/" + self.tool_name + ".py", "w") as file:
                file.write(code)

            os.chdir(self._shared_state.get("default_folder"))
            return f'{content}\n\nPlease make sure to now test this tool if possible.'
        except Exception as e:
            os.chdir(self._shared_state.get("default_folder"))
            return f'Error writing to file: {e}'

    @field_validator("requirements", mode="after")
    @classmethod
    def validate_requirements(cls, v):
        if "placeholder" in v:
            raise ValueError("Requirements contain placeholders. "
                             "Please never user placeholders. Instead, implement only the code that you are confident about.")

        # check if code is included in requirements
        pattern = r'(```)((.*\n){5,})(```)'
        if re.search(pattern, v):
            raise ValueError(
                "Requirements contain a code snippet. Please never include code snippets in requirements. "
                "Requirements must be a description of the complete file to be written. You can include specific class, function, and variable names, but not the actual code."
            )

        return v

    @field_validator("details", mode="after")
    @classmethod
    def validate_details(cls, v):
        if len(v) == 0:
            raise ValueError("Details are required. Remember this tool does not have access to other files. Please provide additional details like relevant documentation, error messages, or class, function, and variable names from other files that this file depends on.")
        return v

    @model_validator(mode="after")
    def validate_agency_name(self):
        if not self.agent_name and not self._shared_state.get("agent_name"):
            raise ValueError("Please provide agent name.")

        check_agency_path(self)


if __name__ == "__main__":
    tool = CreateTool(
        requirements="Write a program that takes a list of integers as input and returns the sum of all the integers in the list.",
        mode="write",
        file_path="test.py",
    )
    print(tool.run())

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\tools\TestTool.py
================================================
import os
from typing import Optional

from pydantic import Field, model_validator

from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.tools import BaseTool, ToolFactory


class TestTool(BaseTool):
    """
    This tool tests other tools defined in tools.py file with the given arguments. Make sure to define the run method before testing.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to test the tool for."
    )
    chain_of_thought: str = Field(
        ..., description="Think step by step to determine the correct arguments for testing.", exclude=True
    )
    tool_name: str = Field(..., description="Name of the tool to be run.")
    arguments: Optional[str] = Field(...,
                                     description="Arguments to be passed to the tool for testing "
                                                 "in serialized JSON format.")
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))
        os.chdir(self.agent_name)

        # import tool by self.tool_name from local tools.py file
        try:
            tool = ToolFactory.from_file(f"./tools/{self.tool_name}.py")
        except Exception as e:
            raise ValueError(f"Error importing tool {self.tool_name}: {e}")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

        try:
            if not self.arguments:
                output = tool().run()
            else:
                output = tool(**eval(self.arguments)).run()
        except Exception as e:
            raise ValueError(f"Error running tool {self.tool_name}: {e}")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

        if not output:
            raise ValueError(f"Tool {self.tool_name} did not return any output.")

        return f"Successfully initialized and ran tool. Output: '{output}'"

    @model_validator(mode="after")
    def validate_tool_name(self):
        check_agency_path(self)

        if not self.agent_name and not self._shared_state.get("agent_name"):
            raise ValueError("Please provide agent name.")

        agent_name = self.agent_name or self._shared_state.get("agent_name")

        tool_path = os.path.join(self._shared_state.get("agency_path"), agent_name)
        tool_path = os.path.join(str(tool_path), "tools")
        tool_path = os.path.join(tool_path, self.tool_name + ".py")


        # check if tools.py file exists
        if not os.path.isfile(tool_path):
            available_tools = os.listdir(os.path.join(self._shared_state.get("agency_path"), agent_name))
            available_tools = [tool for tool in available_tools if tool.endswith(".py")]
            available_tools = [tool for tool in available_tools if
                               not tool.startswith("__") and not tool.startswith(".")]
            available_tools = [tool.replace(".py", "") for tool in available_tools]
            available_tools = ", ".join(available_tools)
            raise ValueError(f"Tool {self.tool_name} not found. Available tools are: {available_tools}")

        agent_path = os.path.join(self._shared_state.get("agency_path"), self.agent_name)
        if not os.path.exists(agent_path):
            available_agents = os.listdir(self._shared_state.get("agency_path"))
            available_agents = [agent for agent in available_agents if
                                os.path.isdir(os.path.join(self._shared_state.get("agency_path"), agent))]
            raise ValueError(f"Agent {self.agent_name} not found. Available agents are: {available_agents}")

        return True


if __name__ == "__main__":
    TestTool._shared_state.data = {"agency_path": "/Users/vrsen/Projects/agency-swarm/agency-swarm/TestAgency",
                              "default_folder": "/Users/vrsen/Projects/agency-swarm/agency-swarm/TestAgency"}
    test_tool = TestTool(agent_name="TestAgent", tool_name="PrintTestTool", arguments="{}", chain_of_thought="")
    print(test_tool.run())


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\__init__.py
================================================
from .ToolCreator import ToolCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\util.py
================================================
import os
from pathlib import Path


def check_agency_path(self):
    if not self._shared_state.get("default_folder"):
        self._shared_state.set('default_folder', Path.cwd())

    if not self._shared_state.get("agency_path") and not self.agency_name:
        available_agencies = os.listdir("./")
        available_agencies = [agency for agency in available_agencies if os.path.isdir(agency)]
        raise ValueError(f"Please specify an agency. Available agencies are: {available_agencies}")
    elif not self._shared_state.get("agency_path") and self.agency_name:
        if not os.path.exists(os.path.join("./", self.agency_name)):
            available_agencies = os.listdir("./")
            available_agencies = [agency for agency in available_agencies if os.path.isdir(agency)]
            raise ValueError(f"Agency {self.agency_name} not found. Available agencies are: {available_agencies}")
        self._shared_state.set("agency_path", os.path.join("./", self.agency_name))


def check_agent_path(self):
    agent_path = os.path.join(self._shared_state.get("agency_path"), self.agent_name)
    if not os.path.exists(agent_path):
        available_agents = os.listdir(self._shared_state.get("agency_path"))
        available_agents = [agent for agent in available_agents if
                            os.path.isdir(os.path.join(self._shared_state.get("agency_path"), agent))]
        raise ValueError(f"Agent {self.agent_name} not found. Available agents are: {available_agents}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\__init__.py
================================================
from .GenesisAgency import GenesisAgency

================================================
File: /agency-swarm-main\agency_swarm\agency\__init__.py
================================================
from .agency import Agency


================================================
File: /agency-swarm-main\agency_swarm\agents\agent.py
================================================
import copy
import inspect
import json
import os
from typing import Dict, Union, Any, Type, Literal, TypedDict, Optional
from typing import List

from deepdiff import DeepDiff
from openai import NotFoundError
from openai.types.beta.assistant import ToolResources

from agency_swarm.tools import BaseTool, ToolFactory, Retrieval
from agency_swarm.tools import FileSearch, CodeInterpreter
from agency_swarm.tools.oai.FileSearch import FileSearchConfig
from agency_swarm.util.oai import get_openai_client
from agency_swarm.util.openapi import validate_openapi_spec
from agency_swarm.util.shared_state import SharedState
from pydantic import BaseModel
from openai.lib._parsing._completions import type_to_response_format_param


Directory structure:
└── mgrillo75-email-proc-production
    ├── agency-swarm-main
    │   ├── .cursorrules
    │   ├── .github
    │   │   └── workflows
    │   │       ├── close-issues.yml
    │   │       ├── docs.yml
    │   │       ├── publish.yml
    │   │       └── test.yml
    │   ├── agency_swarm
    │   │   ├── agency
    │   │   │   ├── agency.py
    │   │   │   ├── genesis
    │   │   │   │   ├── AgentCreator
    │   │   │   │   │   ├── AgentCreator.py
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   ├── CreateAgentTemplate.py
    │   │   │   │   │   │   ├── ImportAgent.py
    │   │   │   │   │   │   ├── ReadManifesto.py
    │   │   │   │   │   │   └── util
    │   │   │   │   │   │       ├── get_modules.py
    │   │   │   │   │   │       └── __init__.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── GenesisAgency.py
    │   │   │   │   ├── GenesisCEO
    │   │   │   │   │   ├── GenesisCEO.py
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   ├── CreateAgencyFolder.py
    │   │   │   │   │   │   ├── FinalizeAgency.py
    │   │   │   │   │   │   └── ReadRequirements.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── manifesto.md
    │   │   │   │   ├── OpenAPICreator
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── OpenAPICreator.py
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   └── CreateToolsFromOpenAPISpec.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── ToolCreator
    │   │   │   │   │   ├── instructions.md
    │   │   │   │   │   ├── ToolCreator.py
    │   │   │   │   │   ├── tools
    │   │   │   │   │   │   ├── CreateTool.py
    │   │   │   │   │   │   └── TestTool.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── util.py
    │   │   │   │   └── __init__.py
    │   │   │   └── __init__.py
    │   │   ├── agents
    │   │   │   ├── agent.py
    │   │   │   ├── BrowsingAgent
    │   │   │   │   ├── BrowsingAgent.py
    │   │   │   │   ├── instructions.md
    │   │   │   │   ├── requirements.txt
    │   │   │   │   ├── tools
    │   │   │   │   │   ├── ClickElement.py
    │   │   │   │   │   ├── ExportFile.py
    │   │   │   │   │   ├── GoBack.py
    │   │   │   │   │   ├── ReadURL.py
    │   │   │   │   │   ├── Scroll.py
    │   │   │   │   │   ├── SelectDropdown.py
    │   │   │   │   │   ├── SendKeys.py
    │   │   │   │   │   ├── SolveCaptcha.py
    │   │   │   │   │   ├── util
    │   │   │   │   │   │   ├── get_b64_screenshot.py
    │   │   │   │   │   │   ├── highlights.py
    │   │   │   │   │   │   ├── selenium.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   ├── WebPageSummarizer.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── Devid
    │   │   │   │   ├── Devid.py
    │   │   │   │   ├── instructions.md
    │   │   │   │   ├── tools
    │   │   │   │   │   ├── ChangeFile.py
    │   │   │   │   │   ├── CheckCurrentDir.py
    │   │   │   │   │   ├── CommandExecutor.py
    │   │   │   │   │   ├── DirectoryNavigator.py
    │   │   │   │   │   ├── FileMover.py
    │   │   │   │   │   ├── FileReader.py
    │   │   │   │   │   ├── FileWriter.py
    │   │   │   │   │   ├── ListDir.py
    │   │   │   │   │   ├── util
    │   │   │   │   │   │   ├── format_file_deps.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   └── __init__.py
    │   │   │   └── __init__.py
    │   │   ├── cli.py
    │   │   ├── messages
    │   │   │   ├── message_output.py
    │   │   │   └── __init__.py
    │   │   ├── threads
    │   │   │   ├── thread.py
    │   │   │   ├── thread_async.py
    │   │   │   └── __init__.py
    │   │   ├── tools
    │   │   │   ├── BaseTool.py
    │   │   │   ├── oai
    │   │   │   │   ├── CodeInterpreter.py
    │   │   │   │   ├── FileSearch.py
    │   │   │   │   ├── Retrieval.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── send_message
    │   │   │   │   ├── SendMessage.py
    │   │   │   │   ├── SendMessageAsyncThreading.py
    │   │   │   │   ├── SendMessageBase.py
    │   │   │   │   ├── SendMessageQuick.py
    │   │   │   │   ├── SendMessageSwarm.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── ToolFactory.py
    │   │   │   └── __init__.py
    │   │   ├── user
    │   │   │   ├── user.py
    │   │   │   └── __init__.py
    │   │   ├── util
    │   │   │   ├── cli
    │   │   │   │   ├── create_agent_template.py
    │   │   │   │   ├── import_agent.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── errors.py
    │   │   │   ├── files.py
    │   │   │   ├── helpers
    │   │   │   │   ├── get_available_agent_descriptions.py
    │   │   │   │   ├── list_available_agents.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── oai.py
    │   │   │   ├── openapi.py
    │   │   │   ├── schema.py
    │   │   │   ├── shared_state.py
    │   │   │   ├── streaming.py
    │   │   │   ├── validators.py
    │   │   │   └── __init__.py
    │   │   └── __init__.py
    │   ├── docs
    │   │   ├── advanced-usage
    │   │   │   ├── agencies.md
    │   │   │   ├── agents.md
    │   │   │   ├── azure-openai.md
    │   │   │   ├── communication_flows.md
    │   │   │   ├── open-source-models.md
    │   │   │   └── tools.md
    │   │   ├── api.md
    │   │   ├── assets
    │   │   ├── deployment.md
    │   │   ├── examples.md
    │   │   ├── index.md
    │   │   ├── introduction
    │   │   │   └── showcase.md
    │   │   └── quick_start.md
    │   ├── mkdocs.yml
    │   ├── notebooks
    │   │   ├── agency_async.ipynb
    │   │   ├── azure.ipynb
    │   │   ├── genesis_agency.ipynb
    │   │   ├── os_models_with_astra_assistants_api.ipynb
    │   │   └── web_browser_agent.ipynb
    │   ├── pyproject.toml
    │   ├── README.md
    │   ├── requirements.txt
    │   ├── requirements_docs.txt
    │   ├── requirements_test.txt
    │   ├── run_tests.py
    │   ├── setup.py
    │   └── tests
    │       ├── data
    │       │   ├── files
    │       │   │   ├── csv-test.csv
    │       │   │   ├── generated_data.json
    │       │   │   ├── test-docx.docx
    │       │   │   ├── test-html.html
    │       │   │   ├── test-md.md
    │       │   │   ├── test-pdf.pdf
    │       │   │   ├── test-txt.txt
    │       │   │   └── test-xml.xml
    │       │   ├── schemas
    │       │   │   ├── ga4.json
    │       │   │   ├── get-headers-params.json
    │       │   │   ├── get-weather.json
    │       │   │   └── relevance.json
    │       │   └── tools
    │       │       └── ExampleTool1.py
    │       ├── demos
    │       │   ├── demo_gradio.py
    │       │   ├── streaming_demo.py
    │       │   ├── term_demo.py
    │       │   └── __init__.py
    │       ├── test_agency.py
    │       ├── test_communication.py
    │       ├── test_tool_factory.py
    │       └── __init__.py
    ├── EmailProcessingAgency
    │   ├── agency.py
    │   ├── agency_manifesto.md
    │   ├── EmailCategorizationAgent
    │   │   ├── EmailCategorizationAgent.py
    │   │   ├── instructions.md
    │   │   ├── tools
    │   │   │   ├── EmailCategorizer.py
    │   │   │   └── EmailParser.py
    │   │   └── __init__.py
    │   ├── EmailProcessingAgent
    │   │   ├── EmailProcessingAgent.py
    │   │   ├── instructions-old.md
    │   │   ├── instructions.md
    │   │   ├── tools
    │   │   │   ├── EmailProcessor.py
    │   │   │   ├── ErrorHandling.py
    │   │   │   └── OutlookFolderMonitor.py
    │   │   └── __init__.py
    │   ├── error_log.txt
    │   ├── LeadAgent
    │   │   ├── instructions.md
    │   │   ├── LeadAgent.py
    │   │   └── __init__.py
    │   ├── requirements.txt
    │   ├── settings.json
    │   ├── SummaryGenerationAgent
    │   │   ├── instructions.md
    │   │   ├── SummaryGenerationAgent.py
    │   │   ├── tools
    │   │   │   └── SummaryGenerator.py
    │   │   └── __init__.py
    │   └── __init__.py
    ├── letta-main
    │   ├── .dockerignore
    │   ├── .env.example
    │   ├── .gitattributes
    │   ├── .github
    │   │   ├── ISSUE_TEMPLATE
    │   │   │   ├── bug_report.md
    │   │   │   └── feature_request.md
    │   │   ├── pull_request_template.md
    │   │   └── workflows
    │   │       ├── code_style_checks.yml
    │   │       ├── docker-image-nightly.yml
    │   │       ├── docker-image.yml
    │   │       ├── docker-integration-tests.yaml
    │   │       ├── integration_tests.yml
    │   │       ├── letta-web-openapi-saftey.yml
    │   │       ├── letta-web-safety.yml
    │   │       ├── migration-test.yml
    │   │       ├── poetry-publish-nightly.yml
    │   │       ├── poetry-publish.yml
    │   │       ├── test-pip-install.yml
    │   │       ├── tests.yml
    │   │       ├── test_anthropic.yml
    │   │       ├── test_azure.yml
    │   │       ├── test_cli.yml
    │   │       ├── test_examples.yml
    │   │       ├── test_groq.yml
    │   │       ├── test_memgpt_hosted.yml
    │   │       ├── test_ollama.yml
    │   │       ├── test_openai.yml
    │   │       └── test_together.yml
    │   ├── .pre-commit-config.yaml
    │   ├── alembic
    │   │   ├── env.py
    │   │   ├── README
    │   │   ├── script.py.mako
    │   │   └── versions
    │   │       ├── 1c8880d671ee_make_an_blocks_agents_mapping_table.py
    │   │       ├── 9a505cc7eca9_create_a_baseline_migrations.py
    │   │       ├── b6d7ca024aa9_add_agents_tags_table.py
    │   │       ├── c85a3d07c028_move_files_to_orm.py
    │   │       ├── cda66b6cb0d6_move_sources_to_orm.py
    │   │       ├── d14ae606614c_move_organizations_users_tools_to_orm.py
    │   │       ├── f7507eab4bb9_migrate_blocks_to_orm_model.py
    │   │       └── f81ceea2c08d_create_sandbox_config_and_sandbox_env_.py
    │   ├── alembic.ini
    │   ├── assets
    │   ├── CITATION.cff
    │   ├── compose.yaml
    │   ├── configs
    │   │   └── llm_model_configs
    │   │       └── azure-gpt-4o-mini.json
    │   ├── db
    │   │   ├── Dockerfile.simple
    │   │   └── run_postgres.sh
    │   ├── dev-compose.yaml
    │   ├── development.compose.yml
    │   ├── docker-compose-vllm.yaml
    │   ├── Dockerfile
    │   ├── examples
    │   │   ├── Building agents with Letta.ipynb
    │   │   ├── composio_tool_usage.py
    │   │   ├── docs
    │   │   │   ├── agent_advanced.py
    │   │   │   ├── agent_basic.py
    │   │   │   ├── memory.py
    │   │   │   ├── rest_client.py
    │   │   │   └── tools.py
    │   │   ├── helper.py
    │   │   ├── langchain_tool_usage.py
    │   │   ├── notebooks
    │   │   │   ├── Agentic RAG with Letta.ipynb
    │   │   │   ├── Customizing memory management.ipynb
    │   │   │   ├── data
    │   │   │   │   ├── handbook.pdf
    │   │   │   │   ├── shared_memory_system_prompt.txt
    │   │   │   │   └── task_queue_system_prompt.txt
    │   │   │   ├── Introduction to Letta.ipynb
    │   │   │   └── Multi-agent recruiting workflow.ipynb
    │   │   ├── personal_assistant_demo
    │   │   │   ├── charles.txt
    │   │   │   ├── gmail_test_setup.py
    │   │   │   ├── gmail_unread_polling_listener.py
    │   │   │   ├── google_calendar.py
    │   │   │   ├── google_calendar_preset.yaml
    │   │   │   ├── google_calendar_test_setup.py
    │   │   │   ├── personal_assistant.txt
    │   │   │   ├── personal_assistant_preset.yaml
    │   │   │   ├── README.md
    │   │   │   ├── twilio_flask_listener.py
    │   │   │   ├── twilio_messaging.py
    │   │   │   └── twilio_messaging_preset.yaml
    │   │   ├── resend_example
    │   │   │   ├── README.md
    │   │   │   ├── resend_preset.yaml
    │   │   │   └── resend_send_email_env_vars.py
    │   │   ├── swarm
    │   │   │   ├── simple.py
    │   │   │   └── swarm.py
    │   │   ├── tool_rule_usage.py
    │   │   └── tutorials
    │   │       ├── local-python-client.ipynb
    │   │       ├── memgpt-admin-client.ipynb
    │   │       ├── memgpt_paper.pdf
    │   │       ├── memgpt_rag_agent.ipynb
    │   │       └── python-client.ipynb
    │   ├── init.sql
    │   ├── letta
    │   │   ├── agent.py
    │   │   ├── agent_store
    │   │   │   ├── chroma.py
    │   │   │   ├── db.py
    │   │   │   ├── lancedb.py
    │   │   │   ├── milvus.py
    │   │   │   ├── qdrant.py
    │   │   │   └── storage.py
    │   │   ├── benchmark
    │   │   │   ├── benchmark.py
    │   │   │   └── constants.py
    │   │   ├── cli
    │   │   │   ├── cli.py
    │   │   │   ├── cli_config.py
    │   │   │   └── cli_load.py
    │   │   ├── client
    │   │   │   ├── client.py
    │   │   │   ├── streaming.py
    │   │   │   ├── utils.py
    │   │   │   └── __init__.py
    │   │   ├── config.py
    │   │   ├── constants.py
    │   │   ├── credentials.py
    │   │   ├── data_sources
    │   │   │   ├── connectors.py
    │   │   │   └── connectors_helper.py
    │   │   ├── embeddings.py
    │   │   ├── errors.py
    │   │   ├── functions
    │   │   │   ├── functions.py
    │   │   │   ├── function_sets
    │   │   │   │   ├── base.py
    │   │   │   │   └── extras.py
    │   │   │   ├── helpers.py
    │   │   │   ├── schema_generator.py
    │   │   │   └── __init__.py
    │   │   ├── helpers
    │   │   │   ├── tool_rule_solver.py
    │   │   │   └── __init__.py
    │   │   ├── humans
    │   │   │   ├── examples
    │   │   │   │   ├── basic.txt
    │   │   │   │   └── cs_phd.txt
    │   │   │   └── __init__.py
    │   │   ├── interface.py
    │   │   ├── llm_api
    │   │   │   ├── anthropic.py
    │   │   │   ├── azure_openai.py
    │   │   │   ├── azure_openai_constants.py
    │   │   │   ├── cohere.py
    │   │   │   ├── google_ai.py
    │   │   │   ├── helpers.py
    │   │   │   ├── llm_api_tools.py
    │   │   │   ├── mistral.py
    │   │   │   ├── openai.py
    │   │   │   └── __init__.py
    │   │   ├── local_llm
    │   │   │   ├── chat_completion_proxy.py
    │   │   │   ├── constants.py
    │   │   │   ├── function_parser.py
    │   │   │   ├── grammars
    │   │   │   │   ├── gbnf_grammar_generator.py
    │   │   │   │   ├── json.gbnf
    │   │   │   │   ├── json_func_calls_with_inner_thoughts.gbnf
    │   │   │   │   └── __init__.py
    │   │   │   ├── json_parser.py
    │   │   │   ├── koboldcpp
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── llamacpp
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── llm_chat_completion_wrappers
    │   │   │   │   ├── airoboros.py
    │   │   │   │   ├── chatml.py
    │   │   │   │   ├── configurable_wrapper.py
    │   │   │   │   ├── dolphin.py
    │   │   │   │   ├── llama3.py
    │   │   │   │   ├── simple_summary_wrapper.py
    │   │   │   │   ├── wrapper_base.py
    │   │   │   │   ├── zephyr.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── lmstudio
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── ollama
    │   │   │   │   ├── api.py
    │   │   │   │   └── settings.py
    │   │   │   ├── README.md
    │   │   │   ├── settings
    │   │   │   │   ├── deterministic_mirostat.py
    │   │   │   │   ├── settings.py
    │   │   │   │   ├── simple.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── utils.py
    │   │   │   ├── vllm
    │   │   │   │   └── api.py
    │   │   │   ├── webui
    │   │   │   │   ├── api.py
    │   │   │   │   ├── legacy_api.py
    │   │   │   │   ├── legacy_settings.py
    │   │   │   │   └── settings.py
    │   │   │   └── __init__.py
    │   │   ├── log.py
    │   │   ├── main.py
    │   │   ├── memory.py
    │   │   ├── metadata.py
    │   │   ├── o1_agent.py
    │   │   ├── openai_backcompat
    │   │   │   ├── openai_object.py
    │   │   │   └── __init__.py
    │   │   ├── orm
    │   │   │   ├── agents_tags.py
    │   │   │   ├── base.py
    │   │   │   ├── block.py
    │   │   │   ├── blocks_agents.py
    │   │   │   ├── enums.py
    │   │   │   ├── errors.py
    │   │   │   ├── file.py
    │   │   │   ├── mixins.py
    │   │   │   ├── organization.py
    │   │   │   ├── sandbox_config.py
    │   │   │   ├── source.py
    │   │   │   ├── sqlalchemy_base.py
    │   │   │   ├── tool.py
    │   │   │   ├── user.py
    │   │   │   ├── __all__.py
    │   │   │   └── __init__.py
    │   │   ├── persistence_manager.py
    │   │   ├── personas
    │   │   │   ├── examples
    │   │   │   │   ├── anna_pa.txt
    │   │   │   │   ├── google_search_persona.txt
    │   │   │   │   ├── memgpt_doc.txt
    │   │   │   │   ├── memgpt_starter.txt
    │   │   │   │   ├── o1_persona.txt
    │   │   │   │   ├── sam.txt
    │   │   │   │   ├── sam_pov.txt
    │   │   │   │   ├── sam_simple_pov_gpt35.txt
    │   │   │   │   └── sqldb
    │   │   │   │       └── test.db
    │   │   │   └── __init__.py
    │   │   ├── prompts
    │   │   │   ├── gpt_summarize.py
    │   │   │   ├── gpt_system.py
    │   │   │   ├── system
    │   │   │   │   ├── memgpt_base.txt
    │   │   │   │   ├── memgpt_chat.txt
    │   │   │   │   ├── memgpt_chat_compressed.txt
    │   │   │   │   ├── memgpt_chat_fstring.txt
    │   │   │   │   ├── memgpt_doc.txt
    │   │   │   │   ├── memgpt_gpt35_extralong.txt
    │   │   │   │   ├── memgpt_intuitive_knowledge.txt
    │   │   │   │   ├── memgpt_modified_chat.txt
    │   │   │   │   └── memgpt_modified_o1.txt
    │   │   │   └── __init__.py
    │   │   ├── providers.py
    │   │   ├── pytest.ini
    │   │   ├── schemas
    │   │   │   ├── agent.py
    │   │   │   ├── agents_tags.py
    │   │   │   ├── api_key.py
    │   │   │   ├── block.py
    │   │   │   ├── blocks_agents.py
    │   │   │   ├── embedding_config.py
    │   │   │   ├── enums.py
    │   │   │   ├── file.py
    │   │   │   ├── health.py
    │   │   │   ├── job.py
    │   │   │   ├── letta_base.py
    │   │   │   ├── letta_message.py
    │   │   │   ├── letta_request.py
    │   │   │   ├── letta_response.py
    │   │   │   ├── llm_config.py
    │   │   │   ├── memory.py
    │   │   │   ├── message.py
    │   │   │   ├── openai
    │   │   │   │   ├── chat_completions.py
    │   │   │   │   ├── chat_completion_request.py
    │   │   │   │   ├── chat_completion_response.py
    │   │   │   │   ├── embedding_response.py
    │   │   │   │   └── openai.py
    │   │   │   ├── organization.py
    │   │   │   ├── passage.py
    │   │   │   ├── sandbox_config.py
    │   │   │   ├── source.py
    │   │   │   ├── tool.py
    │   │   │   ├── tool_rule.py
    │   │   │   ├── usage.py
    │   │   │   └── user.py
    │   │   ├── server
    │   │   │   ├── constants.py
    │   │   │   ├── generate_openapi_schema.sh
    │   │   │   ├── rest_api
    │   │   │   │   ├── app.py
    │   │   │   │   ├── auth
    │   │   │   │   │   ├── index.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── auth_token.py
    │   │   │   │   ├── interface.py
    │   │   │   │   ├── routers
    │   │   │   │   │   ├── openai
    │   │   │   │   │   │   ├── assistants
    │   │   │   │   │   │   │   ├── assistants.py
    │   │   │   │   │   │   │   ├── schemas.py
    │   │   │   │   │   │   │   ├── threads.py
    │   │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   │   ├── chat_completions
    │   │   │   │   │   │   │   ├── chat_completions.py
    │   │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   ├── v1
    │   │   │   │   │   │   ├── agents.py
    │   │   │   │   │   │   ├── blocks.py
    │   │   │   │   │   │   ├── health.py
    │   │   │   │   │   │   ├── jobs.py
    │   │   │   │   │   │   ├── llms.py
    │   │   │   │   │   │   ├── organizations.py
    │   │   │   │   │   │   ├── sandbox_configs.py
    │   │   │   │   │   │   ├── sources.py
    │   │   │   │   │   │   ├── tools.py
    │   │   │   │   │   │   ├── users.py
    │   │   │   │   │   │   └── __init__.py
    │   │   │   │   │   └── __init__.py
    │   │   │   │   ├── static_files.py
    │   │   │   │   ├── utils.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── server.py
    │   │   │   ├── startup.sh
    │   │   │   ├── static_files
    │   │   │   │   ├── assets
    │   │   │   │   │   ├── index-3ab03d5b.css
    │   │   │   │   │   └── index-9fa459a2.js
    │   │   │   │   ├── favicon.ico
    │   │   │   │   └── index.html
    │   │   │   ├── utils.py
    │   │   │   ├── ws_api
    │   │   │   │   ├── example_client.py
    │   │   │   │   ├── interface.py
    │   │   │   │   ├── protocol.py
    │   │   │   │   ├── server.py
    │   │   │   │   └── __init__.py
    │   │   │   └── __init__.py
    │   │   ├── services
    │   │   │   ├── agents_tags_manager.py
    │   │   │   ├── blocks_agents_manager.py
    │   │   │   ├── block_manager.py
    │   │   │   ├── organization_manager.py
    │   │   │   ├── sandbox_config_manager.py
    │   │   │   ├── source_manager.py
    │   │   │   ├── tool_execution_sandbox.py
    │   │   │   ├── tool_manager.py
    │   │   │   ├── tool_sandbox_env
    │   │   │   │   └── .gitkeep
    │   │   │   ├── user_manager.py
    │   │   │   └── __init__.py
    │   │   ├── settings.py
    │   │   ├── streaming_interface.py
    │   │   ├── streaming_utils.py
    │   │   ├── system.py
    │   │   ├── utils.py
    │   │   ├── __init__.py
    │   │   └── __main__.py
    │   ├── locust_test.py
    │   ├── main.py
    │   ├── nginx.conf
    │   ├── paper_experiments
    │   │   ├── doc_qa_task
    │   │   │   ├── 0_load_embeddings.sh
    │   │   │   ├── 1_run_docqa.sh
    │   │   │   ├── 2_run_eval.sh
    │   │   │   ├── doc_qa.py
    │   │   │   ├── llm_judge_doc_qa.py
    │   │   │   └── load_wikipedia_embeddings.py
    │   │   ├── nested_kv_task
    │   │   │   ├── data
    │   │   │   │   ├── kv-retrieval-140_keys.jsonl.gz
    │   │   │   │   ├── random_orderings_100_samples_140_indices_1_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_2_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_3_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_4_levels.jsonl
    │   │   │   │   ├── random_orderings_100_samples_140_indices_5_levels.jsonl
    │   │   │   │   └── random_orderings_100_samples_140_indices_6_levels.jsonl
    │   │   │   ├── nested_kv.py
    │   │   │   └── run.sh
    │   │   ├── README.md
    │   │   └── utils.py
    │   ├── poetry.lock
    │   ├── PRIVACY.md
    │   ├── pyproject.toml
    │   ├── README.md
    │   ├── scripts
    │   │   ├── migrate_0.3.17.py
    │   │   ├── migrate_0.3.18.py
    │   │   ├── migrate_tools.py
    │   │   ├── pack_docker.sh
    │   │   └── wait_for_service.sh
    │   ├── TERMS.md
    │   └── tests
    │       ├── clear_postgres_db.py
    │       ├── config.py
    │       ├── configs
    │       │   ├── embedding_model_configs
    │       │   │   ├── azure_embed.json
    │       │   │   ├── letta-hosted.json
    │       │   │   ├── local.json
    │       │   │   ├── ollama.json
    │       │   │   └── openai_embed.json
    │       │   ├── letta_hosted.json
    │       │   ├── llm_model_configs
    │       │   │   ├── azure-gpt-4o-mini.json
    │       │   │   ├── claude-3-5-haiku.json
    │       │   │   ├── gemini-pro.json
    │       │   │   ├── groq.json
    │       │   │   ├── letta-hosted.json
    │       │   │   ├── ollama.json
    │       │   │   ├── openai-gpt-4o.json
    │       │   │   ├── together-llama-3-1-405b.json
    │       │   │   └── together-llama-3-70b.json
    │       │   └── openai.json
    │       ├── conftest.py
    │       ├── constants.py
    │       ├── data
    │       │   ├── functions
    │       │   │   └── dump_json.py
    │       │   ├── memgpt-0.2.11
    │       │   │   ├── agents
    │       │   │   │   ├── agent_test
    │       │   │   │   │   ├── agent_state
    │       │   │   │   │   │   ├── 2024-01-11_12_43_57_PM.json
    │       │   │   │   │   │   └── 2024-01-11_12_43_59_PM.json
    │       │   │   │   │   ├── config.json
    │       │   │   │   │   └── persistence_manager
    │       │   │   │   │       ├── 2024-01-11_12_43_57_PM.persistence.pickle
    │       │   │   │   │       ├── 2024-01-11_12_43_59_PM.persistence.pickle
    │       │   │   │   │       └── index
    │       │   │   │   │           └── nodes.pkl
    │       │   │   │   ├── agent_test_attach
    │       │   │   │   │   ├── agent_state
    │       │   │   │   │   │   ├── 2024-01-11_12_42_17_PM.json
    │       │   │   │   │   │   └── 2024-01-11_12_42_19_PM.json
    │       │   │   │   │   ├── config.json
    │       │   │   │   │   └── persistence_manager
    │       │   │   │   │       ├── 2024-01-11_12_42_17_PM.persistence.pickle
    │       │   │   │   │       ├── 2024-01-11_12_42_19_PM.persistence.pickle
    │       │   │   │   │       └── index
    │       │   │   │   │           └── nodes.pkl
    │       │   │   │   └── agent_test_empty_archival
    │       │   │   │       ├── agent_state
    │       │   │   │       │   ├── 2024-01-11_12_44_32_PM.json
    │       │   │   │       │   └── 2024-01-11_12_44_33_PM.json
    │       │   │   │       ├── config.json
    │       │   │   │       └── persistence_manager
    │       │   │   │           ├── 2024-01-11_12_44_32_PM.persistence.pickle
    │       │   │   │           ├── 2024-01-11_12_44_33_PM.persistence.pickle
    │       │   │   │           └── index
    │       │   │   │               └── nodes.pkl
    │       │   │   ├── archival
    │       │   │   │   └── test
    │       │   │   │       └── nodes.pkl
    │       │   │   └── config
    │       │   ├── memgpt-0.3.17
    │       │   │   └── sqlite.db
    │       │   ├── memgpt_paper.pdf
    │       │   └── test.txt
    │       ├── helpers
    │       │   ├── client_helper.py
    │       │   ├── endpoints_helper.py
    │       │   └── utils.py
    │       ├── integration_test_summarizer.py
    │       ├── pytest.ini
    │       ├── test_agent_tool_graph.py
    │       ├── test_autogen_integration.py
    │       ├── test_base_functions.py
    │       ├── test_cli.py
    │       ├── test_client.py
    │       ├── test_client_legacy.py
    │       ├── test_concurrent_connections.py
    │       ├── test_different_embedding_size.py
    │       ├── test_function_parser.py
    │       ├── test_json_parsers.py
    │       ├── test_local_client.py
    │       ├── test_managers.py
    │       ├── test_memory.py
    │       ├── test_model_letta_perfomance.py
    │       ├── test_new_cli.py
    │       ├── test_o1_agent.py
    │       ├── test_openai_client.py
    │       ├── test_persistence.py
    │       ├── test_providers.py
    │       ├── test_schema_generator.py
    │       ├── test_server.py
    │       ├── test_storage.py
    │       ├── test_stream_buffer_readers.py
    │       ├── test_summarize.py
    │       ├── test_tool_execution_sandbox.py
    │       ├── test_tool_rule_solver.py
    │       ├── test_tool_sandbox
    │       │   └── .gitkeep
    │       ├── test_utils.py
    │       ├── test_websocket_server.py
    │       ├── utils.py
    │       └── __init__.py
    └── settings.json


Files Content:

(Files content cropped to 300k characters, download full ingest to see more)
================================================
File: /agency-swarm-main\.cursorrules
================================================
# AI Agent Creator Instructions for Agency Swarm Framework

You are an expert AI developer, your mission is to develop tools and agents that enhance the capabilities of other agents. These tools and agents are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools and agents, ensuring they are both functional and align with the framework's standards.

## Understanding Your Role

Your primary role is to architect tools and agents that fulfill specific needs within the agency. This involves:

1. **Tool Development:** Develop each tool following the Agency Swarm's specifications, ensuring it is robust and ready for production environments. It must not use any placeholders and be located in the correct agent's tools folder.
2. **Identifying Packages:** Determine the best possible packages or APIs that can be used to create a tool based on the user's requirements. Utilize web search if you are uncertain about which API or package to use.
3. **Instructions for the Agent**: If the agent is underperforming, you will need to adjust it's instructions based on the user's feedback. Find the instructions.md file for the agent and adjust it.

## Agency Swarm Framework Overview

Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the agent creation process and enable anyone to create a collaborative swarm of agents (Agencies), each with distinct roles and capabilities.

### Key Features

- **Customizable Agent Roles**: Define roles like CEO, virtual assistant, developer, etc., and customize their functionalities with [Assistants API](https://platform.openai.com/docs/assistants/overview).
- **Full Control Over Prompts**: Avoid conflicts and restrictions of pre-defined prompts, allowing full customization.
- **Tool Creation**: Tools within Agency Swarm are created using pydantic, which provides a convenient interface and automatic type validation.
- **Efficient Communication**: Agents communicate through a specially designed "send message" tool based on their own descriptions.
- **State Management**: Agency Swarm efficiently manages the state of your assistants on OpenAI, maintaining it in a special `settings.json` file.
- **Deployable in Production**: Agency Swarm is designed to be reliable and easily deployable in production environments.

### Folder Structure

In Agency Swarm, the folder structure is organized as follows:

1. Each agency and agent has its own dedicated folder.
2. Within each agent folder:

   - A 'tools' folder contains all tools for that agent.
   - An 'instructions.md' file provides agent-specific instructions.
   - An '**init**.py' file contains the import of the agent.

3. Tool Import Process:

   - Create a file in the 'tools' folder with the same name as the tool class.
   - The tool needs to be added to the tools list in the agent class. Do not overwrite existing tools when adding a new tool.
   - All new requirements must be added to the requirements.txt file.

4. Agency Configuration:
   - The 'agency.py' file is the main file where all new agents are imported.
   - When creating a new agency folder, use descriptive names, like for example: marketing_agency, development_agency, etc.

Follow this folder structure when creating or modifying files within the Agency Swarm framework:

```
agency_name/
├── agent_name/
│   ├── __init__.py
│   ├── agent_name.py
│   ├── instructions.md
│   └── tools/
│       ├── tool_name1.py
│       ├── tool_name2.py
│       ├── tool_name3.py
│       ├── ...
├── another_agent/
│   ├── __init__.py
│   ├── another_agent.py
│   ├── instructions.md
│   └── tools/
│       ├── tool_name1.py
│       ├── tool_name2.py
│       ├── tool_name3.py
│       ├── ...
├── agency.py
├── agency_manifesto.md
├── requirements.txt
└──...
```

## Instructions

### 1. Create tools

Tools are the specific actions that agents can perform. They are defined in the `tools` folder.

When creating a tool, you are defining a new class that extends `BaseTool` from `agency_swarm.tools`. This process involves several key steps, outlined below.

#### 1. Import Necessary Modules

Start by importing `BaseTool` from `agency_swarm.tools` and `Field` from `pydantic`. These imports will serve as the foundation for your custom tool class. Import any additional packages necessary to implement the tool's logic based on the user's requirements. Import `load_dotenv` from `dotenv` to load the environment variables.

#### 2. Define Your Tool Class

Create a new class that inherits from `BaseTool`. This class will encapsulate the functionality of your tool. `BaseTool` class inherits from the Pydantic's `BaseModel` class.

#### 3. Specify Tool Fields

Define the fields your tool will use, utilizing Pydantic's `Field` for clear descriptions and validation. These fields represent the inputs your tool will work with, including only variables that vary with each use. Define any constant variables globally.

#### 4. Implement the `run` Method

The `run` method is where your tool's logic is executed. Use the fields defined earlier to perform the tool's intended task. It must contain the actual fully functional correct python code. It can utilize various python packages, previously imported in step 1.

### Best Practices

- **Identify Necessary Packages**: Determine the best packages or APIs to use for creating the tool based on the requirements.
- **Documentation**: Ensure each class and method is well-documented. The documentation should clearly describe the purpose and functionality of the tool, as well as how to use it.
- **Code Quality**: Write clean, readable, and efficient code. Adhere to the PEP 8 style guide for Python code.
- **Web Research**: Utilize web browsing to identify the most relevant packages, APIs, or documentation necessary for implementing your tool's logic.
- **Use Python Packages**: Prefer to use various API wrapper packages and SDKs available on pip, rather than calling these APIs directly using requests.
- **Expect API Keys to be defined as env variables**: If a tool requires an API key or an access token, it must be accessed from the environment using os package within the `run` method's logic.
- **Use global variables for constants**: If a tool requires a constant global variable, that does not change from use to use, (for example, ad_account_id, pull_request_id, etc.), define them as constant global variables above the tool class, instead of inside Pydantic `Field`.
- **Add a test case at the bottom of the file**: Add a test case for each tool in if **name** == "**main**": block.

### Example of a Tool

```python
from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv

load_dotenv() # always load the environment variables

account_id = "MY_ACCOUNT_ID"
api_key = os.getenv("MY_API_KEY") # or access_token = os.getenv("MY_ACCESS_TOKEN")

class MyCustomTool(BaseTool):
    """
    A brief description of what the custom tool does.
    The docstring should clearly explain the tool's purpose and functionality.
    It will be used by the agent to determine when to use this tool.
    """
    # Define the fields with descriptions using Pydantic Field
    example_field: str = Field(
        ..., description="Description of the example field, explaining its purpose and usage for the Agent."
    )

    def run(self):
        """
        The implementation of the run method, where the tool's main functionality is executed.
        This method should utilize the fields defined above to perform the task.
        """
        # Your custom tool logic goes here
        # Example:
        # do_something(self.example_field, api_key, account_id)

        # Return the result of the tool's operation as a string
        return "Result of MyCustomTool operation"

if __name__ == "__main__":
    tool = MyCustomTool(example_field="example value")
    print(tool.run())
```

Remember, each tool code snippet you create must be fully ready to use. It must not contain any placeholders or hypothetical examples.

## 2. Create agents

Agents are the core of the framework. Each agent has it's own unique role and functionality and is designed to perform specific tasks. Each file for the agent must be named the same as the agent's name.

### Agent Class

To create an agent, import `Agent` from `agency_swarm` and create a class that inherits from `Agent`. Inside the class you can adjust the following parameters:

```python
from agency_swarm import Agent

class CEO(Agent):
    def __init__(self):
        super().__init__(
            name="CEO",
            description="Responsible for client communication, task planning and management.",
            instructions="./instructions.md", # instructions for the agent
            tools=[MyCustomTool],
            temperature=0.5,
            max_prompt_tokens=25000,
        )
```

- Name: The agent's name, reflecting its role.
- Description: A brief summary of the agent's responsibilities.
- Instructions: Path to a markdown file containing detailed instructions for the agent.
- Tools: A list of tools (extending BaseTool) that the agent can use. (Tools must not be initialized, so the agent can pass the parameters itself)
- Other Parameters: Additional settings like temperature, max_prompt_tokens, etc.

Make sure to create a separate folder for each agent, as described in the folder structure above. After creating the agent, you need to import it into the agency.py file.

#### instructions.md file

Each agent also needs to have an `instructions.md` file, which is the system prompt for the agent. Inside those instructions, you need to define the following:

- **Agent Role**: A description of the role of the agent.
- **Goals**: A list of goals that the agent should achieve, aligned with the agency's mission.
- **Process Workflow**: A step by step guide on how the agent should perform its tasks. Each step must be aligned with the other agents in the agency, and with the tools available to this agent.

Use the following template for the instructions.md file:

```md
# Agent Role

A description of the role of the agent.

# Goals

A list of goals that the agent should achieve, aligned with the agency's mission.

# Process Workflow

1. Step 1
2. Step 2
3. Step 3
```

Instructions for the agent to be created in markdown format. Instructions should include a description of the role and a specific step by step process that this agent needs to perform in order to execute the tasks. The process must also be aligned with all the other agents in the agency. Agents should be able to collaborate with each other to achieve the common goal of the agency.

#### Code Interpreter and FileSearch Options

To utilize the Code Interpreter tool (the Jupyter Notebook Execution environment, without Internet access) and the FileSearch tool (a Retrieval-Augmented Generation (RAG) provided by OpenAI):

1. Import the tools:

   ```python
   from agency_swarm.tools import CodeInterpreter, FileSearch

   ```

2. Add the tools to the agent's tools list:

   ```python
   agent = Agent(
       name="MyAgent",
       tools=[CodeInterpreter, FileSearch],
       # ... other agent parameters
   )

   ```

## 3. Create Agencies

Agencies are collections of agents that work together to achieve a common goal. They are defined in the `agency.py` file.

### Agency Class

To create an agency, import `Agency` from `agency_swarm` and create a class that inherits from `Agency`. Inside the class you can adjust the following parameters:

```python
from agency_swarm import Agency
from CEO import CEO
from Developer import Developer
from VirtualAssistant import VirtualAssistant

dev = Developer()
va = VirtualAssistant()

agency = Agency([
        ceo,  # CEO will be the entry point for communication with the user
        [ceo, dev],  # CEO can initiate communication with Developer
        [ceo, va],   # CEO can initiate communication with Virtual Assistant
        [dev, va]    # Developer can initiate communication with Virtual Assistant
        ],
        shared_instructions='agency_manifesto.md', #shared instructions for all agents
        temperature=0.5, # default temperature for all agents
        max_prompt_tokens=25000 # default max tokens in conversation history
)

if __name__ == "__main__":
    agency.run_demo() # starts the agency in terminal
```

#### Communication Flows

In Agency Swarm, communication flows are directional, meaning they are established from left to right in the agency_chart definition. For instance, in the example above, the CEO can initiate a chat with the developer (dev), and the developer can respond in this chat. However, the developer cannot initiate a chat with the CEO. The developer can initiate a chat with the virtual assistant (va) and assign new tasks.

To allow agents to communicate with each other, simply add them in the second level list inside the agency chart like this: `[ceo, dev], [ceo, va], [dev, va]`. The agent on the left will be able to communicate with the agent on the right.

#### Agency Manifesto

Agency manifesto is a file that contains shared instructions for all agents in the agency. It is a markdown file that is located in the agency folder. Please write the manifesto file when creating a new agency. Include the following:

- **Agency Description**: A brief description of the agency.
- **Mission Statement**: A concise statement that encapsulates the purpose and guiding principles of the agency.
- **Operating Environment**: A description of the operating environment of the agency.

# Notes

IMPORTANT: NEVER output code snippets or file contents in the chat. Always create or modify the actual files in the file system. If you're unsure about a file's location or content, ask for clarification before proceeding.

When creating or modifying files:

1. Use the appropriate file creation or modification syntax (e.g., ```python:path/to/file.py for Python files).
2. Write the full content of the file, not just snippets or placeholders.
3. Ensure all necessary imports and dependencies are included.
4. Follow the specified file creation order rigorously: 1. tools, 2. agents, 3. agency, 4. requirements.txt.

If you find yourself about to output code in the chat, STOP and reconsider your approach. Always prioritize actual file creation and modification over chat explanations.


================================================
File: /agency-swarm-main\.github\workflows\close-issues.yml
================================================
name: Close inactive issues
on:
  schedule:
    - cron: "30 1 * * *"

  workflow_dispatch:

jobs:
  close-issues:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      pull-requests: write
    steps:
      - uses: actions/stale@v5
        with:
          days-before-issue-stale: 30
          days-before-issue-close: 14
          stale-issue-label: "stale"
          stale-issue-message: "This issue is stale because it has been open for 30 days with no activity. Please upgrade to the latest version and test it again."
          close-issue-message: "This issue was closed because it has been inactive for 14 days since being marked as stale. If the issue still persists, please reopen."
          days-before-pr-stale: -1
          days-before-pr-close: -1
          repo-token: ${{ secrets.GITHUB_TOKEN }}


================================================
File: /agency-swarm-main\.github\workflows\docs.yml
================================================
name: docs
on:
  push:
    branches:
      - master 
      - main
permissions:
  contents: write
jobs:
  deploy-docs:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure Git Credentials
        run: |
          git config user.name github-actions[bot]
          git config user.email 41898282+github-actions[bot]@users.noreply.github.com

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - run: echo "cache_id=$(date --utc '+%V')" >> $GITHUB_ENV 
      - uses: actions/cache@v3
        with:
          key: mkdocs-material-${{ env.cache_id }}
          path: .cache
          restore-keys: |
            mkdocs-material-
      - run: pip install -r requirements_docs.txt
      - run: mkdocs gh-deploy --force

================================================
File: /agency-swarm-main\.github\workflows\publish.yml
================================================
name: Publish to PyPI.org
on:
  release:
    types: [published]
  workflow_dispatch:
jobs:
  pypi:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: python3 -m pip install --upgrade build && python3 -m build
      - name: Publish package
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}

================================================
File: /agency-swarm-main\.github\workflows\test.yml
================================================
name: Python Unittest

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements_test.txt

    - name: Run tests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        TEST_SCHEMA_API_KEY: ${{ secrets.TEST_SCHEMA_API_KEY }}
      run: |
        python run_tests.py


================================================
File: /agency-swarm-main\agency_swarm\agency\agency.py
================================================
import inspect
import json
import os
import queue
import threading
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, Type, TypeVar, TypedDict, Union
from openai.lib._parsing._completions import type_to_response_format_param
from openai.types.beta.threads import Message
from openai.types.beta.threads.runs import RunStep
from openai.types.beta.threads.runs.tool_call import (
    CodeInterpreterToolCall,
    FileSearchToolCall,
    FunctionToolCall,
    ToolCall,
)
from pydantic import BaseModel, Field, field_validator, model_validator
from rich.console import Console
from typing_extensions import override

from agency_swarm.agents import Agent
from agency_swarm.messages import MessageOutput
from agency_swarm.messages.message_output import MessageOutputLive
from agency_swarm.threads import Thread
from agency_swarm.threads.thread_async import ThreadAsync
from agency_swarm.tools import BaseTool, CodeInterpreter, FileSearch
from agency_swarm.tools.send_message import SendMessage, SendMessageBase
from agency_swarm.user import User
from agency_swarm.util.errors import RefusalError
from agency_swarm.util.files import get_tools, get_file_purpose
from agency_swarm.util.shared_state import SharedState
from agency_swarm.util.streaming import AgencyEventHandler

console = Console()

T = TypeVar('T', bound=BaseModel)

class SettingsCallbacks(TypedDict):
    load: Callable[[], List[Dict]]
    save: Callable[[List[Dict]], Any]


class ThreadsCallbacks(TypedDict):
    load: Callable[[], Dict]
    save: Callable[[Dict], Any]


class Agency:
    def __init__(self,
                 agency_chart: List,
                 shared_instructions: str = "",
                 shared_files: Union[str, List[str]] = None,
                 async_mode: Literal['threading', "tools_threading"] = None,
                 send_message_tool_class: Type[SendMessageBase] = SendMessage,
                 settings_path: str = "./settings.json",
                 settings_callbacks: SettingsCallbacks = None,
                 threads_callbacks: ThreadsCallbacks = None,
                 temperature: float = 0.3,
                 top_p: float = 1.0,
                 max_prompt_tokens: int = None,
                 max_completion_tokens: int = None,
                 truncation_strategy: dict = None,
                 ):
        """
        Initializes the Agency object, setting up agents, threads, and core functionalities.

        Parameters:
            agency_chart: The structure defining the hierarchy and interaction of agents within the agency.
            shared_instructions (str, optional): A path to a file containing shared instructions for all agents. Defaults to an empty string.
            shared_files (Union[str, List[str]], optional): A path to a folder or a list of folders containing shared files for all agents. Defaults to None.
            async_mode (str, optional): Specifies the mode for asynchronous processing. In "threading" mode, all sub-agents run in separate threads. In "tools_threading" mode, all tools run in separate threads, but agents do not. Defaults to None.
            send_message_tool_class (Type[SendMessageBase], optional): The class to use for the send_message tool. For async communication, use `SendMessageAsyncThreading`. Defaults to SendMessage.
            settings_path (str, optional): The path to the settings file for the agency. Must be json. If file does not exist, it will be created. Defaults to None.
            settings_callbacks (SettingsCallbacks, optional): A dictionary containing functions to load and save settings for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            threads_callbacks (ThreadsCallbacks, optional): A dictionary containing functions to load and save threads for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            temperature (float, optional): The temperature value to use for the agents. Agent-specific values will override this. Defaults to 0.3.
            top_p (float, optional): The top_p value to use for the agents. Agent-specific values will override this. Defaults to None.
            max_prompt_tokens (int, optional): The maximum number of tokens allowed in the prompt for each agent. Agent-specific values will override this. Defaults to None.
            max_completion_tokens (int, optional): The maximum number of tokens allowed in the completion for each agent. Agent-specific values will override this. Defaults to None.
            truncation_strategy (dict, optional): The truncation strategy to use for the completion for each agent. Agent-specific values will override this. Defaults to None.

        This constructor initializes various components of the Agency, including CEO, agents, threads, and user interactions. It parses the agency chart to set up the organizational structure and initializes the messaging tools, agents, and threads necessary for the operation of the agency. Additionally, it prepares a main thread for user interactions.
        """
        self.ceo = None
        self.user = User()
        self.agents = []
        self.agents_and_threads = {}
        self.main_recipients = []
        self.main_thread = None
        self.recipient_agents = None  # for autocomplete
        self.shared_files = shared_files if shared_files else []
        self.async_mode = async_mode
        self.send_message_tool_class = send_message_tool_class
        self.settings_path = settings_path
        self.settings_callbacks = settings_callbacks
        self.threads_callbacks = threads_callbacks
        self.temperature = temperature
        self.top_p = top_p
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.truncation_strategy = truncation_strategy

        # set thread type based send_message_tool_class async mode
        if hasattr(send_message_tool_class.ToolConfig, "async_mode") and send_message_tool_class.ToolConfig.async_mode:
            self._thread_type = ThreadAsync
        else:
            self._thread_type = Thread  

        if self.async_mode == "threading":
            from agency_swarm.tools.send_message import SendMessageAsyncThreading
            print("Warning: 'threading' mode is deprecated. Please use send_message_tool_class = SendMessageAsyncThreading to use async communication.")
            self.send_message_tool_class = SendMessageAsyncThreading
        elif self.async_mode == "tools_threading":
            Thread.async_mode = "tools_threading"
            print("Warning: 'tools_threading' mode is deprecated. Use tool.ToolConfig.async_mode = 'threading' instead.")
        elif self.async_mode is None:
            pass
        else:
            raise Exception("Please select async_mode = 'threading' or 'tools_threading'.")

        if os.path.isfile(os.path.join(self._get_class_folder_path(), shared_instructions)):
            self._read_instructions(os.path.join(self._get_class_folder_path(), shared_instructions))
        elif os.path.isfile(shared_instructions):
            self._read_instructions(shared_instructions)
        else:
            self.shared_instructions = shared_instructions

        self.shared_state = SharedState()

        self._parse_agency_chart(agency_chart)
        self._init_threads()
        self._create_special_tools()
        self._init_agents()

    def get_completion(self, message: str,
                       message_files: List[str] = None,
                       yield_messages: bool = False,
                       recipient_agent: Agent = None,
                       additional_instructions: str = None,
                       attachments: List[dict] = None,
                       tool_choice: dict = None,
                       verbose: bool = False,
                       response_format: dict = None):
        """
        Retrieves the completion for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            yield_messages (bool, optional): Flag to determine if intermediate messages should be yielded. Defaults to True.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
            response_format (dict, optional): The response format to use for the completion.

        Returns:
            Generator or final response: Depending on the 'yield_messages' flag, this method returns either a generator yielding intermediate messages or the final response from the main thread.
        """
        if verbose and yield_messages:
            raise Exception("Verbose mode is not compatible with yield_messages=True")
        
        res = self.main_thread.get_completion(message=message,
                                               message_files=message_files,
                                               attachments=attachments,
                                               recipient_agent=recipient_agent,
                                               additional_instructions=additional_instructions,
                                               tool_choice=tool_choice,
                                               yield_messages=yield_messages or verbose,
                                               response_format=response_format)
        
        if not yield_messages or verbose:
            while True:
                try:
                    message = next(res)
                    if verbose:
                        message.cprint()
                except StopIteration as e:
                    return e.value

        return res


    def get_completion_stream(self,
                              message: str,
                              event_handler: type(AgencyEventHandler),
                              message_files: List[str] = None,
                              recipient_agent: Agent = None,
                              additional_instructions: str = None,
                              attachments: List[dict] = None,
                              tool_choice: dict = None,
                              response_format: dict = None):
        """
        Generates a stream of completions for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            event_handler (type(AgencyEventHandler)): The event handler class to handle the completion stream. https://github.com/openai/openai-python/blob/main/helpers.md
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.

        Returns:
            Final response: Final response from the main thread.
        """
        if not inspect.isclass(event_handler):
            raise Exception("Event handler must not be an instance.")

        res = self.main_thread.get_completion_stream(message=message,
                                                      message_files=message_files,
                                                      event_handler=event_handler,
                                                      attachments=attachments,
                                                      recipient_agent=recipient_agent,
                                                      additional_instructions=additional_instructions,
                                                      tool_choice=tool_choice,
                                                      response_format=response_format)

        while True:
            try:
                next(res)
            except StopIteration as e:
                event_handler.on_all_streams_end()

                return e.value
                
    def get_completion_parse(self, message: str,
                             response_format: Type[T],
                             message_files: List[str] = None,
                             recipient_agent: Agent = None,
                             additional_instructions: str = None,
                             attachments: List[dict] = None,
                             tool_choice: dict = None,
                             verbose: bool = False) -> T:
        """
        Retrieves the completion for a given message from the main thread and parses the response using the provided pydantic model.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            response_format (type(BaseModel)): The response format to use for the completion. 
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
        
        Returns:
            Final response: The final response from the main thread, parsed using the provided pydantic model.
        """
        response_model = None
        if isinstance(response_format, type):
            response_model = response_format
            response_format = type_to_response_format_param(response_format)

        res = self.get_completion(message=message,
                            message_files=message_files,
                            recipient_agent=recipient_agent,
                            additional_instructions=additional_instructions,
                            attachments=attachments,
                            tool_choice=tool_choice,
                            response_format=response_format,
                            verbose=verbose)
        
        try:
            return response_model.model_validate_json(res)
        except:
            parsed_res = json.loads(res)
            if 'refusal' in parsed_res:
                raise RefusalError(parsed_res['refusal'])
            else:
                raise Exception("Failed to parse response: " + res)

    def demo_gradio(self, height=450, dark_mode=True, **kwargs):
        """
        Launches a Gradio-based demo interface for the agency chatbot.

        Parameters:
            height (int, optional): The height of the chatbot widget in the Gradio interface. Default is 600.
            dark_mode (bool, optional): Flag to determine if the interface should be displayed in dark mode. Default is True.
            **kwargs: Additional keyword arguments to be passed to the Gradio interface.
        This method sets up and runs a Gradio interface, allowing users to interact with the agency's chatbot. It includes a text input for the user's messages and a chatbot interface for displaying the conversation. The method handles user input and chatbot responses, updating the interface dynamically.
        """

        try:
            import gradio as gr
        except ImportError:
            raise Exception("Please install gradio: pip install gradio")

        js = """function () {
          gradioURL = window.location.href
          if (!gradioURL.endsWith('?__theme={theme}')) {
            window.location.replace(gradioURL + '?__theme={theme}');
          }
        }"""

        if dark_mode:
            js = js.replace("{theme}", "dark")
        else:
            js = js.replace("{theme}", "light")

        attachments = []
        images = []
        message_file_names = None
        uploading_files = False
        recipient_agent_names = [agent.name for agent in self.main_recipients]
        recipient_agent = self.main_recipients[0]

        with gr.Blocks(js=js) as demo:
            chatbot_queue = queue.Queue()
            chatbot = gr.Chatbot(height=height)
            with gr.Row():
                with gr.Column(scale=9):
                    dropdown = gr.Dropdown(label="Recipient Agent", choices=recipient_agent_names,
                                           value=recipient_agent.name)
                    msg = gr.Textbox(label="Your Message", lines=4)
                with gr.Column(scale=1):
                    file_upload = gr.Files(label="OpenAI Files", type="filepath")
            button = gr.Button(value="Send", variant="primary")

            def handle_dropdown_change(selected_option):
                nonlocal recipient_agent
                recipient_agent = self._get_agent_by_name(selected_option)

            def handle_file_upload(file_list):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                uploading_files = True
                attachments = []
                message_file_names = []
                if file_list:
                    try:
                        for file_obj in file_list:
                            purpose = get_file_purpose(file_obj.name)

                            with open(file_obj.name, 'rb') as f:
                                # Upload the file to OpenAI
                                file = self.main_thread.client.files.create(
                                    file=f,
                                    purpose=purpose
                                )

                            if purpose == "vision":
                                images.append({
                                    "type": "image_file",
                                    "image_file": {"file_id": file.id}
                                })
                            else:
                                attachments.append({
                                    "file_id": file.id,
                                    "tools": get_tools(file.filename)
                                })

                            message_file_names.append(file.filename)
                            print(f"Uploaded file ID: {file.id}")
                        return attachments
                    except Exception as e:
                        print(f"Error: {e}")
                        return str(e)
                    finally:
                        uploading_files = False

                uploading_files = False
                return "No files uploaded"

            def user(user_message, history):
                if not user_message.strip():
                    return user_message, history
                
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                nonlocal attachments
                nonlocal recipient_agent

                # Check if attachments contain file search or code interpreter types
                def check_and_add_tools_in_attachments(attachments, recipient_agent):
                    for attachment in attachments:
                        for tool in attachment.get("tools", []):
                            if tool["type"] == "file_search":
                                if not any(isinstance(t, FileSearch) for t in recipient_agent.tools):
                                    # Add FileSearch tool if it does not exist
                                    recipient_agent.tools.append(FileSearch)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added FileSearch tool to recipient agent to analyze the file.")
                            elif tool["type"] == "code_interpreter":
                                if not any(isinstance(t, CodeInterpreter) for t in recipient_agent.tools):
                                    # Add CodeInterpreter tool if it does not exist
                                    recipient_agent.tools.append(CodeInterpreter)
                                    recipient_agent.client.beta.assistants.update(recipient_agent.id, tools=recipient_agent.get_oai_tools())
                                    print("Added CodeInterpreter tool to recipient agent to analyze the file.")
                    return None

                check_and_add_tools_in_attachments(attachments, recipient_agent)

                if history is None:
                    history = []

                original_user_message = user_message

                # Append the user message with a placeholder for bot response
                if recipient_agent:
                    user_message = f"👤 User 🗣️ @{recipient_agent.name}:\n" + user_message.strip()
                else:
                    user_message = f"👤 User:" + user_message.strip()

                nonlocal message_file_names
                if message_file_names:
                    user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

                return original_user_message, history + [[user_message, None]]

            class GradioEventHandler(AgencyEventHandler):
                message_output = None

                @classmethod
                def change_recipient_agent(cls, recipient_agent_name):
                    nonlocal chatbot_queue
                    chatbot_queue.put("[change_recipient_agent]")
                    chatbot_queue.put(recipient_agent_name)

                @override
                def on_message_created(self, message: Message) -> None:
                    if message.role == "user":
                        full_content = ""
                        for content in message.content:
                            if content.type == "image_file":
                                full_content += f"🖼️ Image File: {content.image_file.file_id}\n"
                                continue

                            if content.type == "image_url":
                                full_content += f"\n{content.image_url.url}\n"
                                continue

                            if content.type == "text":
                                full_content += content.text.value + "\n"


                        self.message_output = MessageOutput("text", self.agent_name, self.recipient_agent_name,
                                                            full_content)

                    else:
                        self.message_output = MessageOutput("text", self.recipient_agent_name, self.agent_name,
                                                            "")

                    chatbot_queue.put("[new_message]")
                    chatbot_queue.put(self.message_output.get_formatted_content())

                @override
                def on_text_delta(self, delta, snapshot):
                    chatbot_queue.put(delta.value)

                @override
                def on_tool_call_created(self, tool_call: ToolCall):
                    if isinstance(tool_call, dict):
                        if "type" not in tool_call:
                            tool_call["type"] = "function"
                        
                        if tool_call["type"] == "function":
                            tool_call = FunctionToolCall(**tool_call)
                        elif tool_call["type"] == "code_interpreter":
                            tool_call = CodeInterpreterToolCall(**tool_call)
                        elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                            tool_call = FileSearchToolCall(**tool_call)
                        else:
                            raise ValueError("Invalid tool call type: " + tool_call["type"])

                    # TODO: add support for code interpreter and retrieval tools
                    if tool_call.type == "function":
                        chatbot_queue.put("[new_message]")
                        self.message_output = MessageOutput("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))
                        chatbot_queue.put(self.message_output.get_formatted_header() + "\n")

                @override
                def on_tool_call_done(self, snapshot: ToolCall):
                    if isinstance(snapshot, dict):
                        if "type" not in snapshot:
                            snapshot["type"] = "function"
                        
                        if snapshot["type"] == "function":
                            snapshot = FunctionToolCall(**snapshot)
                        elif snapshot["type"] == "code_interpreter":
                            snapshot = CodeInterpreterToolCall(**snapshot)
                        elif snapshot["type"] == "file_search":
                            snapshot = FileSearchToolCall(**snapshot)
                        else:
                            raise ValueError("Invalid tool call type: " + snapshot["type"])
                        
                    self.message_output = None

                    # TODO: add support for code interpreter and retrieval tools
                    if snapshot.type != "function":
                        return

                    chatbot_queue.put(str(snapshot.function))

                    if snapshot.function.name == "SendMessage":
                        try:
                            args = eval(snapshot.function.arguments)
                            recipient = args["recipient"]
                            self.message_output = MessageOutput("text", self.recipient_agent_name, recipient,
                                                                args["message"])

                            chatbot_queue.put("[new_message]")
                            chatbot_queue.put(self.message_output.get_formatted_content())
                        except Exception as e:
                            pass

                    self.message_output = None

                @override
                def on_run_step_done(self, run_step: RunStep) -> None:
                    if run_step.type == "tool_calls":
                        for tool_call in run_step.step_details.tool_calls:
                            if tool_call.type != "function":
                                continue

                            if tool_call.function.name == "SendMessage":
                                continue

                            self.message_output = None
                            chatbot_queue.put("[new_message]")

                            self.message_output = MessageOutput("function_output", tool_call.function.name,
                                                                self.recipient_agent_name,
                                                                tool_call.function.output)

                            chatbot_queue.put(self.message_output.get_formatted_header() + "\n")
                            chatbot_queue.put(tool_call.function.output)

                @override
                @classmethod
                def on_all_streams_end(cls):
                    cls.message_output = None
                    chatbot_queue.put("[end]")

            def bot(original_message, history):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal recipient_agent
                nonlocal recipient_agent_names
                nonlocal images
                nonlocal uploading_files

                if not original_message:
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                if uploading_files:
                    history.append([None, "Uploading files... Please wait."])
                    yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    return "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))

                print("Message files: ", attachments)
                print("Images: ", images)
                
                if images and len(images) > 0:
                    original_message = [
                        {
                            "type": "text",
                            "text": original_message,
                        },
                        *images
                    ]


                completion_thread = threading.Thread(target=self.get_completion_stream, args=(
                    original_message, GradioEventHandler, [], recipient_agent, "", attachments, None))
                completion_thread.start()

                attachments = []
                message_file_names = []
                images = []
                uploading_files = False

                new_message = True
                while True:
                    try:
                        bot_message = chatbot_queue.get(block=True)

                        if bot_message == "[end]":
                            completion_thread.join()
                            break

                        if bot_message == "[new_message]":
                            new_message = True
                            continue

                        if bot_message == "[change_recipient_agent]":
                            new_agent_name = chatbot_queue.get(block=True)
                            recipient_agent = self._get_agent_by_name(new_agent_name)
                            yield "", history, gr.update(value=new_agent_name, choices=set([*recipient_agent_names, recipient_agent.name]))
                            continue

                        if new_message:
                            history.append([None, bot_message])
                            new_message = False
                        else:
                            history[-1][1] += bot_message

                        yield "", history, gr.update(value=recipient_agent.name, choices=set([*recipient_agent_names, recipient_agent.name]))
                    except queue.Empty:
                        break

            button.click(
                user,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot]
            ).then(
                bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
            )
            dropdown.change(handle_dropdown_change, dropdown)
            file_upload.change(handle_file_upload, file_upload)
            msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
                bot, [msg, chatbot], [msg, chatbot, dropdown]
            )

            # Enable queuing for streaming intermediate outputs
            demo.queue(default_concurrency_limit=10)

        # Launch the demo
        demo.launch(**kwargs)
        return demo

    def _recipient_agent_completer(self, text, state):
        """
        Autocomplete completer for recipient agent names.
        """
        options = [agent for agent in self.recipient_agents if agent.lower().startswith(text.lower())]
        if state < len(options):
            return options[state]
        else:
            return None

    def _setup_autocomplete(self):
        """
        Sets up readline with the completer function.
        """
        try:
            import readline
        except ImportError:
            # Attempt to import pyreadline for Windows compatibility
            try:
                import pyreadline as readline
            except ImportError:
                print(
                    "Module 'readline' not found. Autocomplete will not work. If you are using Windows, try installing 'pyreadline3'.")
                return

        if not readline:
            return

        try:
            readline.set_completer(self._recipient_agent_completer)
            readline.parse_and_bind('tab: complete')
        except Exception as e:
            print(f"Error setting up autocomplete for agents in terminal: {e}. Autocomplete will not work.")

    def run_demo(self):
        """
        Executes agency in the terminal with autocomplete for recipient agent names.
        """
        outer_self = self
        from agency_swarm import AgencyEventHandler
        class TermEventHandler(AgencyEventHandler):
            message_output = None

            @override
            def on_message_created(self, message: Message) -> None:
                if message.role == "user":
                    self.message_output = MessageOutputLive("text", self.agent_name, self.recipient_agent_name,
                                                            "")
                    self.message_output.cprint_update(message.content[0].text.value)
                else:
                    self.message_output = MessageOutputLive("text", self.recipient_agent_name, self.agent_name, "")

            @override
            def on_message_done(self, message: Message) -> None:
                self.message_output = None

            @override
            def on_text_delta(self, delta, snapshot):
                self.message_output.cprint_update(snapshot.value)

            @override
            def on_tool_call_created(self, tool_call):
                if isinstance(tool_call, dict):
                    if "type" not in tool_call:
                        tool_call["type"] = "function"
                    
                    if tool_call["type"] == "function":
                        tool_call = FunctionToolCall(**tool_call)
                    elif tool_call["type"] == "code_interpreter":
                        tool_call = CodeInterpreterToolCall(**tool_call)
                    elif tool_call["type"] == "file_search" or tool_call["type"] == "retrieval":
                        tool_call = FileSearchToolCall(**tool_call)
                    else:
                        raise ValueError("Invalid tool call type: " + tool_call["type"])

                # TODO: add support for code interpreter and retirieval tools

                if tool_call.type == "function":
                    self.message_output = MessageOutputLive("function", self.recipient_agent_name, self.agent_name,
                                                            str(tool_call.function))

            @override
            def on_tool_call_delta(self, delta, snapshot):
                if isinstance(snapshot, dict):
                    if "type" not in snapshot:
                        snapshot["type"] = "function"
                    
                    if snapshot["type"] == "function":
                        snapshot = FunctionToolCall(**snapshot)
                    elif snapshot["type"] == "code_interpreter":
                        snapshot = CodeInterpreterToolCall(**snapshot)
                    elif snapshot["type"] == "file_search":
                        snapshot = FileSearchToolCall(**snapshot)
                    else:
                        raise ValueError("Invalid tool call type: " + snapshot["type"])
                    
                self.message_output.cprint_update(str(snapshot.function))

            @override
            def on_tool_call_done(self, snapshot):
                self.message_output = None

                # TODO: add support for code interpreter and retrieval tools
                if snapshot.type != "function":
                    return

                if snapshot.function.name == "SendMessage" and not (hasattr(outer_self.send_message_tool_class.ToolConfig, 'output_as_result') and outer_self.send_message_tool_class.ToolConfig.output_as_result):
                    try:
                        args = eval(snapshot.function.arguments)
                        recipient = args["recipient"]
                        self.message_output = MessageOutputLive("text", self.recipient_agent_name, recipient,
                                                                "")

                        self.message_output.cprint_update(args["message"])
                    except Exception as e:
                        pass

                self.message_output = None

            @override
            def on_run_step_done(self, run_step: RunStep) -> None:
                if run_step.type == "tool_calls":
                    for tool_call in run_step.step_details.tool_calls:
                        if tool_call.type != "function":
                            continue

                        if tool_call.function.name == "SendMessage":
                            continue

                        self.message_output = None
                        self.message_output = MessageOutputLive("function_output", tool_call.function.name,
                                                                self.recipient_agent_name, tool_call.function.output)
                        self.message_output.cprint_update(tool_call.function.output)

                    self.message_output = None

            @override
            def on_end(self):
                self.message_output = None

        self.recipient_agents = [str(agent.name) for agent in self.main_recipients]

        self._setup_autocomplete()  # Prepare readline for autocomplete

        while True:
            console.rule()
            text = input("👤 USER: ")

            if not text:
                continue

            if text.lower() == "exit":
                break

            recipient_agent = None
            if "@" in text:
                recipient_agent = text.split("@")[1].split(" ")[0]
                text = text.replace(f"@{recipient_agent}", "").strip()
                try:
                    recipient_agent = \
                        [agent for agent in self.recipient_agents if agent.lower() == recipient_agent.lower()][0]
                    recipient_agent = self._get_agent_by_name(recipient_agent)
                except Exception as e:
                    print(f"Recipient agent {recipient_agent} not found.")
                    continue

            self.get_completion_stream(message=text, event_handler=TermEventHandler, recipient_agent=recipient_agent)

    def get_customgpt_schema(self, url: str):
        """Returns the OpenAPI schema for the agency from the CEO agent, that you can use to integrate with custom gpts.

        Parameters:
            url (str): Your server url where the api will be hosted.
        """

        return self.ceo.get_openapi_schema(url)

    def plot_agency_chart(self):
        pass

    def _init_agents(self):
        """
        Initializes all agents in the agency with unique IDs, shared instructions, and OpenAI models.

        This method iterates through each agent in the agency, assigns a unique ID, adds shared instructions, and initializes the OpenAI models for each agent.

        There are no input parameters.

        There are no output parameters as this method is used for internal initialization purposes within the Agency class.
        """
        if self.settings_callbacks:
            loaded_settings = self.settings_callbacks["load"]()
            with open(self.settings_path, 'w') as f:
                json.dump(loaded_settings, f, indent=4)

        for agent in self.agents:
            if "temp_id" in agent.id:
                agent.id = None

            agent.add_shared_instructions(self.shared_instructions)
            agent.settings_path = self.settings_path

            if self.shared_files:
                if isinstance(self.shared_files, str):
                    self.shared_files = [self.shared_files]

                if isinstance(agent.files_folder, str):
                    agent.files_folder = [agent.files_folder]
                    agent.files_folder += self.shared_files
                elif isinstance(agent.files_folder, list):
                    agent.files_folder += self.shared_files

            if self.temperature is not None and agent.temperature is None:
                agent.temperature = self.temperature
            if self.top_p and agent.top_p is None:
                agent.top_p = self.top_p
            if self.max_prompt_tokens is not None and agent.max_prompt_tokens is None:
                agent.max_prompt_tokens = self.max_prompt_tokens
            if self.max_completion_tokens is not None and agent.max_completion_tokens is None:
                agent.max_completion_tokens = self.max_completion_tokens
            if self.truncation_strategy is not None and agent.truncation_strategy is None:
                agent.truncation_strategy = self.truncation_strategy
            
            if not agent.shared_state:
                agent.shared_state = self.shared_state

            agent.init_oai()

        if self.settings_callbacks:
            with open(self.agents[0].get_settings_path(), 'r') as f:
                settings = f.read()
            settings = json.loads(settings)
            self.settings_callbacks["save"](settings)

    def _init_threads(self):
        """
        Initializes threads for communication between agents within the agency.

        This method creates Thread objects for each pair of interacting agents as defined in the agents_and_threads attribute of the Agency. Each thread facilitates communication and task execution between an agent and its designated recipient agent.

        No input parameters.

        Output Parameters:
            This method does not return any value but updates the agents_and_threads attribute with initialized Thread objects.
        """
        self.main_thread = Thread(self.user, self.ceo)

        # load thread ids
        loaded_thread_ids = {}
        if self.threads_callbacks:
            loaded_thread_ids = self.threads_callbacks["load"]()
            if "main_thread" in loaded_thread_ids and loaded_thread_ids["main_thread"]:
                self.main_thread.id = loaded_thread_ids["main_thread"]
            else:
                self.main_thread.init_thread()

        # Save main_thread into agents_and_threads
        self.agents_and_threads["main_thread"] = self.main_thread

        # initialize threads
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            for other_agent, items in threads.items():
                # create thread class
                self.agents_and_threads[agent_name][other_agent] = self._thread_type(
                    self._get_agent_by_name(items["agent"]),
                    self._get_agent_by_name(
                        items["recipient_agent"]))

                # load thread id if available
                if agent_name in loaded_thread_ids and other_agent in loaded_thread_ids[agent_name]:
                    self.agents_and_threads[agent_name][other_agent].id = loaded_thread_ids[agent_name][other_agent]
                # init threads if threre are threads callbacks so the ids are saved for later use
                elif self.threads_callbacks:
                    self.agents_and_threads[agent_name][other_agent].init_thread()

        # save thread ids
        if self.threads_callbacks:
            loaded_thread_ids = {}
            for agent_name, threads in self.agents_and_threads.items():
                if agent_name == "main_thread":
                    continue
                loaded_thread_ids[agent_name] = {}
                for other_agent, thread in threads.items():
                    loaded_thread_ids[agent_name][other_agent] = thread.id

            loaded_thread_ids["main_thread"] = self.main_thread.id

            self.threads_callbacks["save"](loaded_thread_ids)

    def _parse_agency_chart(self, agency_chart):
        """
        Parses the provided agency chart to initialize and organize agents within the agency.

        Parameters:
            agency_chart: A structure representing the hierarchical organization of agents within the agency.
                    It can contain Agent objects and lists of Agent objects.

        This method iterates through each node in the agency chart. If a node is an Agent, it is set as the CEO if not already assigned.
        If a node is a list, it iterates through the agents in the list, adding them to the agency and establishing communication
        threads between them. It raises an exception if the agency chart is invalid or if multiple CEOs are defined.
        """
        if not isinstance(agency_chart, list):
            raise Exception("Invalid agency chart.")

        if len(agency_chart) == 0:
            raise Exception("Agency chart cannot be empty.")

        for node in agency_chart:
            if isinstance(node, Agent):
                if not self.ceo:
                    self.ceo = node
                    self._add_agent(self.ceo)
                else:
                    self._add_agent(node)
                self._add_main_recipient(node)

            elif isinstance(node, list):
                for i, agent in enumerate(node):
                    if not isinstance(agent, Agent):
                        raise Exception("Invalid agency chart.")

                    index = self._add_agent(agent)

                    if i == len(node) - 1:
                        continue

                    if agent.name not in self.agents_and_threads.keys():
                        self.agents_and_threads[agent.name] = {}

                    if i < len(node) - 1:
                        other_agent = node[i + 1]
                        if other_agent.name == agent.name:
                            continue
                        if other_agent.name not in self.agents_and_threads[agent.name].keys():
                            self.agents_and_threads[agent.name][other_agent.name] = {
                                "agent": agent.name,
                                "recipient_agent": other_agent.name,
                            }
            else:
                raise Exception("Invalid agency chart.")

    def _add_agent(self, agent):
        """
        Adds an agent to the agency, assigning a temporary ID if necessary.

        Parameters:
            agent (Agent): The agent to be added to the agency.

        Returns:
            int: The index of the added agent within the agency's agents list.

        This method adds an agent to the agency's list of agents. If the agent does not have an ID, it assigns a temporary unique ID. It checks for uniqueness of the agent's name before addition. The method returns the index of the agent in the agency's agents list, which is used for referencing the agent within the agency.
        """
        if not agent.id:
            # assign temp id
            agent.id = "temp_id_" + str(uuid.uuid4())
        if agent.id not in self._get_agent_ids():
            if agent.name in self._get_agent_names():
                raise Exception("Agent names must be unique.")
            self.agents.append(agent)
            return len(self.agents) - 1
        else:
            return self._get_agent_ids().index(agent.id)

    def _add_main_recipient(self, agent):
        """
        Adds an agent to the agency's list of main recipients.

        Parameters:
            agent (Agent): The agent to be added to the agency's list of main recipients.

        This method adds an agent to the agency's list of main recipients. These are agents that can be directly contacted by the user.
        """
        main_recipient_ids = [agent.id for agent in self.main_recipients]

        if agent.id not in main_recipient_ids:
            self.main_recipients.append(agent)

    def _read_instructions(self, path):
        """
        Reads shared instructions from a specified file and stores them in the agency.

        Parameters:
            path (str): The file path from which to read the shared instructions.

        This method opens the file located at the given path, reads its contents, and stores these contents in the 'shared_instructions' attribute of the agency. This is used to provide common guidelines or instructions to all agents within the agency.
        """
        path = path
        with open(path, 'r') as f:
            self.shared_instructions = f.read()

    def _create_special_tools(self):
        """
        Creates and assigns 'SendMessage' tools to each agent based on the agency's structure.

        This method iterates through the agents and threads in the agency, creating SendMessage tools for each agent. These tools enable agents to send messages to other agents as defined in the agency's structure. The SendMessage tools are tailored to the specific recipient agents that each agent can communicate with.

        No input parameters.

        No output parameters; this method modifies the agents' toolset internally.
        """
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            recipient_names = list(threads.keys())
            recipient_agents = self._get_agents_by_names(recipient_names)
            if len(recipient_agents) == 0:
                continue
            agent = self._get_agent_by_name(agent_name)
            agent.add_tool(self._create_send_message_tool(agent, recipient_agents))
            if self._thread_type == ThreadAsync:
                agent.add_tool(self._create_get_response_tool(agent, recipient_agents))

    def _create_send_message_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a SendMessage tool to enable an agent to send messages to specified recipient agents.


        Parameters:
            agent (Agent): The agent who will be sending messages.
            recipient_agents (List[Agent]): A list of recipient agents who can receive messages.

        Returns:
            SendMessage: A SendMessage tool class that is dynamically created and configured for the given agent and its recipient agents. This tool allows the agent to send messages to the specified recipients, facilitating inter-agent communication within the agency.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        agent_descriptions = ""
        for recipient_agent in recipient_agents:
            if not recipient_agent.description:
                continue
            agent_descriptions += recipient_agent.name + ": "
            agent_descriptions += recipient_agent.description + "\n"

        class SendMessage(self.send_message_tool_class):
            recipient: recipients = Field(..., description=agent_descriptions)

            @field_validator('recipient')
            @classmethod
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

        SendMessage._caller_agent = agent
        SendMessage._agents_and_threads = self.agents_and_threads

        return SendMessage

    def _create_get_response_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a CheckStatus tool to enable an agent to check the status of a task with a specified recipient agent.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        outer_self = self

        class GetResponse(BaseTool):
            """This tool allows you to check the status of a task or get a response from a specified recipient agent, if the task has been completed. You must always use 'SendMessage' tool with the designated agent first."""
            recipient: recipients = Field(...,
                                          description=f"Recipient agent that you want to check the status of. Valid recipients are: {recipient_names}")

            @field_validator('recipient')
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(f"Recipient {value} is not valid. Valid recipients are: {recipient_names}")
                return value

            def run(self):
                thread = outer_self.agents_and_threads[self._caller_agent.name][self.recipient.value]

                return thread.check_status()

        GetResponse._caller_agent = agent

        return GetResponse

    def _get_agent_by_name(self, agent_name):
        """
        Retrieves an agent from the agency based on the agent's name.

        Parameters:
            agent_name (str): The name of the agent to be retrieved.

        Returns:
            Agent: The agent object with the specified name.

        Raises:
            Exception: If no agent with the given name is found in the agency.
        """
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        raise Exception(f"Agent {agent_name} not found.")

    def _get_agents_by_names(self, agent_names):
        """
        Retrieves a list of agent objects based on their names.

        Parameters:
            agent_names: A list of strings representing the names of the agents to be retrieved.

        Returns:
            A list of Agent objects corresponding to the given names.
        """
        return [self._get_agent_by_name(agent_name) for agent_name in agent_names]

    def _get_agent_ids(self):
        """
        Retrieves the IDs of all agents currently in the agency.

        Returns:
            List[str]: A list containing the unique IDs of all agents.
        """
        return [agent.id for agent in self.agents]

    def _get_agent_names(self):
        """
        Retrieves the names of all agents in the agency.

        Returns:
            List[str]: A list of names of all agents currently part of the agency.
        """
        return [agent.name for agent in self.agents]

    def _get_class_folder_path(self):
        """
        Retrieves the absolute path of the directory containing the class file.

        Returns:
            str: The absolute path of the directory where the class file is located.
        """
        return os.path.abspath(os.path.dirname(inspect.getfile(self.__class__)))

    def delete(self):
        """
        This method deletes the agency and all its agents, cleaning up any files and vector stores associated with each agent.
        """
        for agent in self.agents:
            agent.delete()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\AgentCreator.py
================================================
from agency_swarm import Agent
from .tools.ImportAgent import ImportAgent
from .tools.CreateAgentTemplate import CreateAgentTemplate
from .tools.ReadManifesto import ReadManifesto

class AgentCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new agents for the agency.",
            instructions="./instructions.md",
            tools=[ImportAgent, CreateAgentTemplate, ReadManifesto],
            temperature=0.3,
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\instructions.md
================================================
# AgentCreator Agent Instructions

You are an agent that creates other agents as instructed by the user. 

The user will communicate to you each agent that needs to be created. Below are your instructions that needs to be followed for each agent communicated by the user.

**Primary Instructions:**
1. First, read the manifesto using `ReadManifesto` tool if you have not already done so. This file contains the agency manifesto that describes the agency's purpose and goals.
2. If a similar agent to the requested one is accessible through the `ImportAgent` tool, import this agent and inform the user that the agent has been created. Skip the following steps.
3. If not, create a new agent using `CreateAgentTemplate` tool. 
4. Tell the `ToolCreator` agent to create tools or APIs for this agent. Make sure to also communicate the agent description, name and a summary of the processes that it needs to perform. CEO Agents do not need to utilize any tools, so you can skip this and the following steps.
5. If there are no issues and tools have been successfully created, notify the user that the agent has been created. Otherwise, try to resolve any issues with the tool creator before reporting back to the user.
6. Repeat this process for each agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\CreateAgentTemplate.py
================================================
import os
import shutil
from typing import List

from pydantic import Field, model_validator

from agency_swarm import BaseTool
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.util import create_agent_template

allowed_tools: List = ["CodeInterpreter"]

web_developer_example_instructions = """# Web Developer Agent Instructions

You are an agent that builds responsive web applications using Next.js and Material-UI (MUI). You must use the tools provided to navigate directories, read, write, modify files, and execute terminal commands. 

### Primary Instructions:
1. Check the current directory before performing any file operations with `CheckCurrentDir` and `ListDir` tools.
2. Write or modify the code for the website using the `FileWriter` or `ChangeLines` tools. Make sure to use the correct file paths and file names. Read the file first if you need to modify it.
3. Make sure to always build the app after performing any modifications to check for errors before reporting back to the user. Keep in mind that all files must be reflected on the current website
4. Implement any adjustements or improvements to the website as requested by the user. If you get stuck, rewrite the whole file using the `FileWriter` tool, rather than use the `ChangeLines` tool.
"""


class CreateAgentTemplate(BaseTool):
    """
    This tool creates a template folder for a new agent. Always use this tool first, before creating tools or APIs for the agent.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to be created. Cannot include special characters or spaces."
    )
    agent_description: str = Field(
        ..., description="Description of the agent to be created."
    )
    instructions: str = Field(
        ..., description="Instructions for the agent to be created in markdown format. "
                         "Instructions should include a decription of the role and a specific step by step process "
                         "that this agent need to perform in order to execute the tasks. "
                         "The process must also be aligned with all the other agents in the agency. Agents should be "
                         "able to collaborate with each other to achieve the common goal of the agency.",
        examples=[
            web_developer_example_instructions,
        ]
    )
    default_tools: List[str] = Field(
        [], description=f"List of default tools to be included in the agent. Possible values are {allowed_tools}."
                        f"CodeInterpreter allows the agent to execute python code in a remote python environment.",
        example=["CodeInterpreter"],
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("manifesto_read"):
            raise ValueError("Please read the manifesto first with the ReadManifesto tool.")

        self._shared_state.set("agent_name", self.agent_name)

        os.chdir(self._shared_state.get("agency_path"))

        # remove folder if it already exists
        if os.path.exists(self.agent_name):
            shutil.rmtree(self.agent_name)

        create_agent_template(self.agent_name,
                              self.agent_description,
                              instructions=self.instructions,
                              code_interpreter=True if "CodeInterpreter" in self.default_tools else None,
                              include_example_tool=False)

        # # create or append to init file
        path = self._shared_state.get("agency_path")
        class_name = self.agent_name.replace(" ", "").strip()
        if not os.path.isfile("__init__.py"):
            with open("__init__.py", "w") as f:
                f.write(f"from .{class_name} import {class_name}")
        else:
            with open("__init__.py", "a") as f:
                f.write(f"\nfrom .{class_name} import {class_name}")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {class_name} import {class_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        if "ceo" in self.agent_name.lower():
            return f"You can tell the user that the process of creating {self.agent_name} has been completed, because CEO agent does not need to utilizie any tools or APIs."

        return f"Agent template has been created for {self.agent_name}. Please now tell ToolCreator to create tools for this agent or OpenAPICreator to create API schemas, if this agent needs to utilize any tools or APIs. If this is unclear, please ask the user for more information."

    @model_validator(mode="after")
    def validate_tools(self):
        check_agency_path(self)

        for tool in self.default_tools:
            if tool not in allowed_tools:
                raise ValueError(f"Tool {tool} is not allowed. Allowed tools are: {allowed_tools}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ImportAgent.py
================================================
import os

from pydantic import Field, field_validator

from agency_swarm import BaseTool
from agency_swarm.util.cli import import_agent
from agency_swarm.util.helpers import get_available_agent_descriptions, list_available_agents


class ImportAgent(BaseTool):
    """
    This tool imports an existing agent from agency swarm framework. Please make sure to first use the GetAvailableAgents tool to get the list of available agents.
    """
    agent_name: str = Field(...,
                            description=get_available_agent_descriptions())
    agency_path: str = Field(
        None, description="Path to the agency where the agent will be imported. Default is the current agency.")

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set("default_folder", os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_path:
            return "Error: You must set the agency_path."

        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
        else:
            os.chdir(self.agency_path)

        import_agent(self.agent_name, "./")

        # add agent on second line to agency.py
        with open("agency.py", "r") as f:
            lines = f.readlines()
            lines.insert(1, f"from {self.agent_name} import {self.agent_name}\n")

        with open("agency.py", "w") as f:
            f.writelines(lines)

        os.chdir(self._shared_state.get("default_folder"))

        return (f"Success. {self.agent_name} has been imported. "
                f"You can now tell the user to user proceed with next agents.")

    @field_validator("agent_name", mode='after')
    @classmethod
    def agent_name_exists(cls, v):
        available_agents = list_available_agents()
        if v not in available_agents:
            raise ValueError(
                f"Agent with name {v} does not exist. Available agents are: {available_agents}")
        return v

if __name__ == "__main__":
    tool = ImportAgent(agent_name="Devid")
    tool._shared_state.set("agency_path", "./")
    tool.run()


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\ReadManifesto.py
================================================
import os

from pydantic import Field

from agency_swarm import BaseTool


class ReadManifesto(BaseTool):
    """
    This tool reads a manifesto for the agency being created from a markdown file.
    """
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', os.getcwd())

        if not self._shared_state.get("agency_path") and not self.agency_name:
            raise ValueError("Please specify the agency name. Ask user for clarification if needed.")

        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))

        with open("agency_manifesto.md", "r") as f:
            manifesto = f.read()

        os.chdir(self._shared_state.get("default_folder"))

        self._shared_state.set("manifesto_read", True)

        return manifesto


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\get_modules.py
================================================
import importlib.resources
import pathlib


def get_modules(module_name):
    """
    Get all submodule names from a given module based on file names, without importing them,
    excluding those containing '.agent' or '.genesis' in their paths.

    Args:
    - module_name: The name of the module to search through.

    Returns:
    - A list of submodule names found within the given module.
    """
    submodule_names = []

    try:
        # Using importlib.resources to access the package contents
        with importlib.resources.path(module_name, '') as package_path:
            # Walk through the package directory using pathlib
            for path in pathlib.Path(package_path).rglob('*.py'):
                if path.name != '__init__.py':
                    # Construct the module name from the file path
                    relative_path = path.relative_to(package_path)
                    module_path = '.'.join(relative_path.with_suffix('').parts)

                    submodule_names.append(f"{module_name}.{module_path}")

    except ImportError:
        print(f"Module {module_name} not found.")
        return submodule_names

    submodule_names = [name for name in submodule_names if not name.endswith(".agent") and
                       '.genesis' not in name and
                       'util' not in name and
                       'oai' not in name and
                       'ToolFactory' not in name and
                       'BaseTool' not in name]

    # remove repetition at the end of the path like 'agency_swarm.agents.coding.CodingAgent.CodingAgent'
    for i in range(len(submodule_names)):
        splitted = submodule_names[i].split(".")
        if splitted[-1] == splitted[-2]:
            submodule_names[i] = ".".join(splitted[:-1])

    return submodule_names


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\tools\util\__init__.py
================================================
from .get_modules import get_modules

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\AgentCreator\__init__.py
================================================
from .AgentCreator import AgentCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisAgency.py
================================================
from agency_swarm import Agency
from .AgentCreator import AgentCreator

from .GenesisCEO import GenesisCEO
from .OpenAPICreator import OpenAPICreator
from .ToolCreator import ToolCreator
from agency_swarm.util.helpers import get_available_agent_descriptions

class GenesisAgency(Agency):
    def __init__(self, with_browsing=True, **kwargs):
        if "max_prompt_tokens" not in kwargs:
            kwargs["max_prompt_tokens"] = 25000

        if 'agency_chart' not in kwargs:
            agent_creator = AgentCreator()
            genesis_ceo = GenesisCEO()
            tool_creator = ToolCreator()
            openapi_creator = OpenAPICreator()
            kwargs['agency_chart'] = [
                genesis_ceo, tool_creator, agent_creator,
                [genesis_ceo, agent_creator],
                [agent_creator, tool_creator],
            ]

            if with_browsing:
                from agency_swarm.agents.BrowsingAgent import BrowsingAgent
                browsing_agent = BrowsingAgent()

                browsing_agent.instructions += ("""\n
# BrowsingAgent's Primary instructions
1. Browse the web to find the API documentation requested by the user. Prefer searching google directly for this API documentation page.
2. Navigate to the API documentation page and ensure that it contains the necessary API endpoints descriptions. You can use the AnalyzeContent tool to check if the page contains the necessary API descriptions. If not, try perform another search in google and keep browsing until you find the right page.
3. If you have confirmed that the page contains the necessary API documentation, export the page with ExportFile tool. Then, send the file_id back to the user along with a brief description of the API.
4. Repeat these steps for each new agent, as requested by the user.
                """)
                kwargs['agency_chart'].append(openapi_creator)
                kwargs['agency_chart'].append([openapi_creator, browsing_agent])

        if 'shared_instructions' not in kwargs:
            kwargs['shared_instructions'] = "./manifesto.md"

        super().__init__(**kwargs)


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\GenesisCEO.py
================================================
from pathlib import Path

from agency_swarm import Agent
from .tools.CreateAgencyFolder import CreateAgencyFolder
from .tools.FinalizeAgency import FinalizeAgency
from .tools.ReadRequirements import ReadRequirements


class GenesisCEO(Agent):
    def __init__(self):
        super().__init__(
            description="Acts as the overseer and communicator across the agency, ensuring alignment with the "
                        "agency's goals.",
            instructions="./instructions.md",
            tools=[CreateAgencyFolder, FinalizeAgency, ReadRequirements],
            temperature=0.4,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\instructions.md
================================================
# GenesisCEO Agent Instructions

As a Genesis CEO Agent within the Agency Swarm framework, your mission is to help users define the structure of their agency and create the initial agents.

1. Pick a name for the agency, determine its goals and mission. Ask the user for any clarification if needed.
2. Propose an initial structure for the agency, including the roles of the agents, their communication flows and what APIs or Tools each agent can use, if specified by the user. Focus on creating at most 2 agents, plus CEO, unless instructed otherwise by the user. Do not name the CEO agent GenesisCEO. It's name must be tailored for the purpose of the agency. Output the code snippet like below. Adjust it accordingly, based on user's input.
3. Upon confirmation of the agency structure, use `CreateAgencyFolder` tool to create a folder for the agency. If any modifications are required please use this tool again with the same agency name and it will overwrite the existing folder.
4. Tell AgentCreator to create these agents one by one, starting with the CEO. Each agent should be sent in a separate message using the `SendMessage` tool. Please make sure to include the agent description, summary of the processes it needs to perform and the APIs or Tools that it can use via the message parameter.
5. Once all agents are created, please use the `FinalizeAgency` tool, and tell the user that he can now navigate to the agency folder and start it with `python agency.py` command.


### Example of communication flows

Here is an example of how communication flows are defined in agency swarm. Essentially, agents that are inside a double array can initiate communication with each other. Agents that are in the top level array can communicate with the user. 

```python
agency = Agency([
    ceo, dev,  # CEO and Developer will be the entry point for communication with the user
    [ceo, dev],  # CEO can initiate communication with Developer
    [ceo, va],   # CEO can initiate communication with Virtual Assistant
    [dev, va]    # Developer can initiate communication with Virtual Assistant
], shared_instructions='agency_manifesto.md') # shared instructions for all agents
```
Keep in mind that this is just an example and you should replace it with the actual agents you are creating. Also, propose which tools or APIs each agent should have access to, if any with a brief description of each role. Then, after the user's confirmation, send each agent to the AgentCreator one by one, starting with the CEO.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\CreateAgencyFolder.py
================================================
import shutil
from pathlib import Path

from pydantic import Field, field_validator

import agency_swarm.agency.genesis.GenesisAgency
from agency_swarm import BaseTool

import os


class CreateAgencyFolder(BaseTool):
    """
    This tool creates or modifies an agency folder. You can use it again with the same agency_name to modify a previously created agency, if the user wants to change the agency chart or the manifesto.
    """
    agency_name: str = Field(
        ..., description="Name of the agency to be created. Must not contain spaces or special characters.",
        examples=["AgencyName", "MyAgency", "ExampleAgency"]
    )
    agency_chart: str = Field(
        ..., description="Agency chart to be passed into the Agency class.",
        examples=["[ceo, [ceo, dev], [ceo, va], [dev, va]]"]
    )
    manifesto: str = Field(
        ..., description="Manifesto for the agency, describing its goals and additional context shared by all agents "
                         "in markdown format. It must include information about the working environment, the mission "
                         "and the goals of the agency. Do not add descriptions of the agents themselves or the agency structure.",
    )

    def run(self):
        if not self._shared_state.get("default_folder"):
            self._shared_state.set('default_folder', Path.cwd())

        if self._shared_state.get("agency_name") is None:
            os.mkdir(self.agency_name)
            os.chdir("./" + self.agency_name)
            self._shared_state.set("agency_name", self.agency_name)
            self._shared_state.set("agency_path", Path("./").resolve())
        elif self._shared_state.get("agency_name") == self.agency_name and os.path.exists(self._shared_state.get("agency_path")):
            os.chdir(self._shared_state.get("agency_path"))
            for file in os.listdir():
                if file != "__init__.py" and os.path.isfile(file):
                    os.remove(file)
        else:
            os.mkdir(self._shared_state.get("agency_path"))
            os.chdir("./" + self.agency_name)

        # check that agency chart is valid
        if not self.agency_chart.startswith("[") or not self.agency_chart.endswith("]"):
            raise ValueError("Agency chart must be a list of lists, except for the first agents.")

        # add new lines after every comma, except for those inside second brackets
        # must transform from "[ceo, [ceo, dev], [ceo, va], [dev, va] ]"
        # to "[ceo, [ceo, dev],\n [ceo, va],\n [dev, va] ]"
        agency_chart = self.agency_chart.replace("],", "],\n")

        # create init file
        with open("__init__.py", "w") as f:
            f.write("")

        # create agency.py
        with open("agency.py", "w") as f:
            f.write(agency_py.format(agency_chart=agency_chart))

        # write manifesto
        path = os.path.join("agency_manifesto.md")
        with open(path, "w") as f:
            f.write(self.manifesto)

        os.chdir(self._shared_state.get('default_folder'))

        return f"Agency folder has been created. You can now tell AgentCreator to create agents for {self.agency_name}.\n"


agency_py = """from agency_swarm import Agency


agency = Agency({agency_chart},
                shared_instructions='./agency_manifesto.md', # shared instructions for all agents
                max_prompt_tokens=25000, # default tokens in conversation for all agents
                temperature=0.3, # default temperature for all agents
                )
                
if __name__ == '__main__':
    agency.demo_gradio()
"""

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\FinalizeAgency.py
================================================
import os
from typing import List

from pydantic import Field, model_validator, field_validator

from agency_swarm import BaseTool, get_openai_client
from agency_swarm.util import create_agent_template


class FinalizeAgency(BaseTool):
    """
    This tool finalizes the agency structure and it's imports. Please make sure to use at only at the very end, after all agents have been created.
    """
    agency_path: str = Field(
        None, description="Path to the agency folder. Defaults to the agency currently being created."
    )

    def run(self):
        agency_path = None
        if self._shared_state.get("agency_path"):
            os.chdir(self._shared_state.get("agency_path"))
            agency_path = self._shared_state.get("agency_path")
        else:
            os.chdir(self.agency_path)
            agency_path = self.agency_path

        client = get_openai_client()

        # read agency.py
        with open("./agency.py", "r") as f:
            agency_py = f.read()
            f.close()

        res = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=examples + [
                {'role': "user", 'content': agency_py},
            ],
            temperature=0.0,
        )

        message = res.choices[0].message.content

        # write agency.py
        with open("./agency.py", "w") as f:
            f.write(message)
            f.close()

        return f"Successfully finalized {agency_path} structure. You can now instruct the user to run the agency.py file."

    @model_validator(mode="after")
    def validate_agency_path(self):
        if not self._shared_state.get("agency_path") and not self.agency_path:
            raise ValueError("Agency path not found. Please specify the agency_path. Ask user for clarification if needed.")


SYSTEM_PROMPT = """"Please read the file provided by the user and fix all the imports and indentation accordingly. 

Only output the full valid python code and nothing else."""

example_input = """
from agency_swarm import Agency

from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent


agency = Agency([ceo, [ceo, news_analysis],
 [ceo, price_tracking],
 [news_analysis, price_tracking]],
shared_instructions='./agency_manifesto.md')

if __name__ == '__main__':
    agency.demo_gradio()
"""

example_output = """from agency_swarm import Agency
from CEO import CEO
from NewsAnalysisAgent import NewsAnalysisAgent
from PriceTrackingAgent import PriceTrackingAgent

ceo = CEO()
news_analysis = NewsAnalysisAgent()
price_tracking = PriceTrackingAgent()

agency = Agency([ceo, [ceo, market_analyst],
                 [ceo, news_curator],
                 [market_analyst, news_curator]],
                shared_instructions='./agency_manifesto.md')
    
if __name__ == '__main__':
    agency.demo_gradio()"""

examples = [
    {'role': "system", 'content': SYSTEM_PROMPT},
    {'role': "user", 'content': example_input},
    {'role': "assistant", 'content': example_output}
]


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\tools\ReadRequirements.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field
import os


class ReadRequirements(BaseTool):
    """
    Use this tool to read the agency requirements if user provides them as a file.
    """

    file_path: str = Field(
        ..., description="The path to the file that needs to be read."
    )

    def run(self):
        """
        Checks if the file exists, and if so, opens the specified file, reads its contents, and returns them.
        If the file does not exist, raises a ValueError.
        """
        if not os.path.exists(self.file_path):
            raise ValueError(f"File path does not exist: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except Exception as e:
            return f"An error occurred while reading the file: {str(e)}"


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\GenesisCEO\__init__.py
================================================
from .GenesisCEO import GenesisCEO

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\manifesto.md
================================================
# Genesis Agency Manifesto

You are a part of a Genesis Agency for a framework called Agency Swarm. The goal of your agency is to create other agencies within this framework. Below is a brief description of the framework.

**Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the AI agent creation process and enable anyone to create a collaborative swarms of agents (Agencies), each with distinct roles and capabilities. These agents must function autonomously, yet collaborate with other agents to achieve a common goal.**

Keep in mind that communication with the other agents within your agency via the `SendMessage` tool is synchronous. Other agents will not be executing any tasks post response. Please instruct the recipient agent to continue its execution, if needed. Do not report to the user before the recipient agent has completed its task. If the agent proposes the next steps, for example, you must instruct the recipient agent to execute them.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\instructions.md
================================================
# OpenAPICreator Instructions

You are an agent that creates tools from OpenAPI schemas. User will provide you with a description of the agent's role. If the provided description does not require any API calls, please notify the user.

**Here are your primary instructions:**
1. Think which API is needed for this agent's role, as communicated by the user. Then, tell the BrowsingAgent to find this API documentation page.
2. Explore the provided file from the BrowsingAgent with the `myfiles_broswer` tool to determine which endpoints are needed for this agent's role.
3. If the file does not contain the actual API documentation page, please notify the BrowsingAgent. Keep in mind that you do not need the full API documentation. You can make an educated guess if some information is not available.
4. Use `CreateToolsFromOpenAPISpec` to create the tools by defining the OpenAPI schema accordingly. Make sure to include all the relevant API endpoints that are needed for this agent to execute its role from the provided file. Do not truncate the schema.
5. Repeat these steps for each new agent that needs to be created, as instructed by the user.

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\OpenAPICreator.py
================================================
from agency_swarm import Agent
from .tools.CreateToolsFromOpenAPISpec import CreateToolsFromOpenAPISpec


class OpenAPICreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools from an OpenAPI specifications.",
            instructions="./instructions.md",
            tools=[CreateToolsFromOpenAPISpec]
        )

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\tools\CreateToolsFromOpenAPISpec.py
================================================
import os

from pydantic import Field, field_validator, model_validator

from agency_swarm import BaseTool

import json

from agency_swarm.agency.genesis.util import check_agency_path, check_agent_path
from agency_swarm.tools import ToolFactory
from agency_swarm.util.openapi import validate_openapi_spec


class CreateToolsFromOpenAPISpec(BaseTool):
    """
    This tool creates a set of tools from an OpenAPI specification. Each method in the specification is converted to a separate tool.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to create the API for. Must be an existing agent."
    )
    openapi_spec: str = Field(
        ..., description="OpenAPI specification for the tool to be created as a valid JSON string. Only the relevant "
                         "endpoints must be included. Responses are not required. Each method should contain "
                         "an operation id and a description. Do not truncate this schema. "
                         "It must be a full valid OpenAPI 3.1.0 specification.",
        examples=[
            '{\n  "openapi": "3.1.0",\n  "info": {\n    "title": "Get weather data",\n    "description": "Retrieves current weather data for a location.",\n    "version": "v1.0.0"\n  },\n  "servers": [\n    {\n      "url": "https://weather.example.com"\n    }\n  ],\n  "paths": {\n    "/location": {\n      "get": {\n        "description": "Get temperature for a specific location",\n        "operationId": "GetCurrentWeather",\n        "parameters": [\n          {\n            "name": "location",\n            "in": "query",\n            "description": "The city and state to retrieve the weather for",\n            "required": true,\n            "schema": {\n              "type": "string"\n            }\n          }\n        ],\n        "deprecated": false\n      }\n    }\n  },\n  "components": {\n    "schemas": {}\n  }\n}'])
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        os.chdir(self._shared_state.get("agency_path"))

        os.chdir(self.agent_name)

        try:
            try:
                tools = ToolFactory.from_openapi_schema(self.openapi_spec)
            except Exception as e:
                raise ValueError(f"Error creating tools from OpenAPI Spec: {e}")

            if len(tools) == 0:
                return "No tools created. Please check the OpenAPI specification."

            tool_names = [tool.__name__ for tool in tools]

            # save openapi spec
            folder_path = "./" + self.agent_name + "/"
            os.chdir(folder_path)

            api_name = json.loads(self.openapi_spec)["info"]["title"]

            api_name = api_name.replace("API", "Api").replace(" ", "")

            api_name = ''.join(['_' + i.lower() if i.isupper() else i for i in api_name]).lstrip('_')

            with open("schemas/" + api_name + ".json", "w") as f:
                f.write(self.openapi_spec)

            return "Successfully added OpenAPI Schema to " + self._shared_state.get("agent_name")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

    @field_validator("openapi_spec", mode='before')
    @classmethod
    def validate_openapi_spec(cls, v):
        try:
            validate_openapi_spec(v)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format:", e)
        except Exception as e:
            raise ValueError("Error validating OpenAPI schema:", e)
        return v

    @model_validator(mode="after")
    def validate_agent_name(self):
        check_agency_path(self)

        check_agent_path(self)



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\OpenAPICreator\__init__.py
================================================
from .OpenAPICreator import OpenAPICreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\instructions.md
================================================
# ToolCreator Agent Instructions

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

**Here are your primary instructions:**
1. Determine which tools the agent must utilize to perform it's role. Make an educated guess if the user has not specified any tools or APIs. Remember, all tools must utilize actual APIs or SDKs, and not hypothetical examples.
2. Create these tools one at a time, using `CreateTool` tool.
3. Test each tool with the `TestTool` function to ensure it is working as expected. Do not ask the user, always test the tool yourself, if it does not require any API keys and all the inputs can be mocked.
4. Only after all the necessary tools are created, notify the user.



================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\ToolCreator.py
================================================
from agency_swarm import Agent
from .tools.CreateTool import CreateTool
from .tools.TestTool import TestTool


class ToolCreator(Agent):
    def __init__(self):
        super().__init__(
            description="This agent is responsible for creating new tools for the agency using python code.",
            instructions="./instructions.md",
            tools=[CreateTool, TestTool],
            temperature=0,
        )




================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\tools\CreateTool.py
================================================
import os
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agency_swarm import get_openai_client
from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.tools import BaseTool

prompt = """# Agency Swarm Overview

Agency Swarm started as a desire and effort of Arsenii Shatokhin (aka VRSEN) to fully automate his AI Agency with AI. By building this framework, we aim to simplify the agent creation process and enable anyone to create a collaborative swarm of agents (Agencies), each with distinct roles and capabilities. 

# ToolCreator Agent Instructions for Agency Swarm Framework

As a ToolCreator Agent within the Agency Swarm framework, your mission is to develop tools that enhance the capabilities of other agents. These tools are pivotal for enabling agents to communicate, collaborate, and efficiently achieve their collective objectives. Below are detailed instructions to guide you through the process of creating tools, ensuring they are both functional and align with the framework's standards.

### Tool Creation Guide

When creating a tool, you are essentially defining a new class that extends `BaseTool`. This process involves several key steps, outlined below.

#### 1. Import Necessary Modules

Start by importing `BaseTool` from `agency_swarm.tools` and `Field` from `pydantic`. These imports will serve as the foundation for your custom tool class. Import any additional packages necessary to implement the tool's logic.

#### 2. Define Your Tool Class

Create a new class that inherits from `BaseTool`. This class will encapsulate the functionality of your tool. `BaseTool` class inherits from the Pydantic's `BaseModel` class.

#### 3. Specify Tool Fields

Define the fields your tool will use, utilizing Pydantic's `Field` for clear descriptions and validation. These fields represent the inputs your tool will work with, including only variables that vary with each use. Define any constant variables like api keys globally.

#### 4. Implement the `run` Method

The `run` method is where your tool's logic is executed. Use the fields defined earlier to perform the tool's intended task. It must contain the actual fully functional correct python code. It can utilize various python packages, previously imported in step 1. Do not include any placeholders or hypothetical examples in the code.

### Example of a Custom Tool

```python
from agency_swarm.tools import BaseTool
from pydantic import Field
import os

account_id = "MY_ACCOUNT_ID"
api_key = os.getenv("MY_API_KEY") # or access_token = os.getenv("MY_ACCESS_TOKEN")

class MyCustomTool(BaseTool):
    \"\"\"
    A brief description of what the custom tool does.
    The docstring should clearly explain the tool's purpose and functionality.
    It will be used by the agent to determine when to use this tool.
    \"\"\"

    # Define the fields with descriptions using Pydantic Field
    example_field: str = Field(
        ..., description="Description of the example field, explaining its purpose and usage for the Agent."
    )

    def run(self):
        \"\"\"
        The implementation of the run method, where the tool's main functionality is executed.
        This method should utilize the fields defined above to perform the task.
        \"\"\"
        # Your custom tool logic goes here
        # Example: 
        # do_something(self.example_field, api_key, account_id)

        # Return the result of the tool's operation as a string
        return "Result of MyCustomTool operation"
```

To share state between 2 or more tools, you can use the `shared_state` attribute of the tool. It is a dictionary that can be used to store and retrieve values across different tools. This can be useful for passing information between tools or agents. Here is an example of how to use the `shared_state`:

```python
class MyCustomTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        # Update the shared state
        self._shared_state.set("key", "value")
        
        return "Result of MyCustomTool operation"
        
# Access shared state in another tool
class AnotherTool(BaseTool):
    def run(self):
        # Access the shared state
        value = self._shared_state.get("key")
        
        return "Result of AnotherTool operation"
```

This is useful to pass information between tools or agents or to verify the state of the system.  

Remember, you must output the resulting python tool code as a whole in a code block, so the user can just copy and paste it into his program. Each tool code snippet must be ready to use. It must not contain any placeholders or hypothetical examples."""

history = [
            {
                "role": "system",
                "content": prompt
            },
        ]


class CreateTool(BaseTool):
    """This tool creates other custom tools for the agent, based on your requirements and details."""
    agent_name: str = Field(
        ..., description="Name of the agent to create the tool for."
    )
    tool_name: str = Field(..., description="Name of the tool class in camel case.", examples=["ExampleTool"])
    requirements: str = Field(
        ...,
        description="The comprehensive requirements explaning the primary functionality of the tool. It must not contain any code or implementation details."
    )
    details: str = Field(
        None, description="Additional details or error messages, class, function, and variable names."
    )
    mode: Literal["write", "modify"] = Field(
        ..., description="The mode of operation for the tool. 'write' is used to create a new tool or overwrite an existing one. 'modify' is used to modify an existing tool."
    )
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))
        os.chdir(self.agent_name)

        client = get_openai_client()

        if self.mode == "write":
            message = f"Please create a '{self.tool_name}' tool that meets the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."
        else:
            message = f"Please rewrite a '{self.tool_name}' according to the following requirements: '{self.requirements}'.\n\nThe tool class must be named '{self.tool_name}'."

        if self.details:
            message += f"\nAdditional Details: {self.details}"

        if self.mode == "modify":
            message += f"\nThe existing file content is as follows:"

            try:
                with open("./tools/" + self.tool_name + ".py", 'r') as file:
                    prev_content = file.read()
                    message += f"\n\n```{prev_content}```"
            except Exception as e:
                os.chdir(self._shared_state.get("default_folder"))
                return f'Error reading {self.tool_name}: {e}'

        history.append({
                "role": "user",
                "content": message
            })

        messages = history.copy()

        # use the last 6 messages
        messages = messages[-6:]

        # add system message upfront
        messages.insert(0, history[0])

        n = 0
        code = ""
        content = ""
        while n < 3:
            resp = client.chat.completions.create(
                messages=messages,
                model="gpt-4o",
                temperature=0,
            )

            content = resp.choices[0].message.content

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            pattern = r"```(?:[a-zA-Z]+\n)?(.*?)```"
            match = re.findall(pattern, content, re.DOTALL)
            if match:
                code = match[-1].strip()
                history.append(
                    {
                        "role": "assistant",
                        "content": content
                    }
                )
                break
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: Could not find the python code block in the response. Please try again."
                    }
                )

            n += 1

        if n == 3 or not code:
            # remove last message from history
            history.pop()
            os.chdir(self._shared_state.get("default_folder"))
            return "Error: Could not generate a valid file."
        try:
            with open("./tools/" + self.tool_name + ".py", "w") as file:
                file.write(code)

            os.chdir(self._shared_state.get("default_folder"))
            return f'{content}\n\nPlease make sure to now test this tool if possible.'
        except Exception as e:
            os.chdir(self._shared_state.get("default_folder"))
            return f'Error writing to file: {e}'

    @field_validator("requirements", mode="after")
    @classmethod
    def validate_requirements(cls, v):
        if "placeholder" in v:
            raise ValueError("Requirements contain placeholders. "
                             "Please never user placeholders. Instead, implement only the code that you are confident about.")

        # check if code is included in requirements
        pattern = r'(```)((.*\n){5,})(```)'
        if re.search(pattern, v):
            raise ValueError(
                "Requirements contain a code snippet. Please never include code snippets in requirements. "
                "Requirements must be a description of the complete file to be written. You can include specific class, function, and variable names, but not the actual code."
            )

        return v

    @field_validator("details", mode="after")
    @classmethod
    def validate_details(cls, v):
        if len(v) == 0:
            raise ValueError("Details are required. Remember this tool does not have access to other files. Please provide additional details like relevant documentation, error messages, or class, function, and variable names from other files that this file depends on.")
        return v

    @model_validator(mode="after")
    def validate_agency_name(self):
        if not self.agent_name and not self._shared_state.get("agent_name"):
            raise ValueError("Please provide agent name.")

        check_agency_path(self)


if __name__ == "__main__":
    tool = CreateTool(
        requirements="Write a program that takes a list of integers as input and returns the sum of all the integers in the list.",
        mode="write",
        file_path="test.py",
    )
    print(tool.run())

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\tools\TestTool.py
================================================
import os
from typing import Optional

from pydantic import Field, model_validator

from agency_swarm.agency.genesis.util import check_agency_path
from agency_swarm.tools import BaseTool, ToolFactory


class TestTool(BaseTool):
    """
    This tool tests other tools defined in tools.py file with the given arguments. Make sure to define the run method before testing.
    """
    agent_name: str = Field(
        ..., description="Name of the agent to test the tool for."
    )
    chain_of_thought: str = Field(
        ..., description="Think step by step to determine the correct arguments for testing.", exclude=True
    )
    tool_name: str = Field(..., description="Name of the tool to be run.")
    arguments: Optional[str] = Field(...,
                                     description="Arguments to be passed to the tool for testing "
                                                 "in serialized JSON format.")
    agency_name: str = Field(
        None, description="Name of the agency to create the tool for. Defaults to the agency currently being created."
    )

    def run(self):
        if self.agency_name:
            os.chdir("./" + self.agency_name)
        else:
            os.chdir(self._shared_state.get("agency_path"))
        os.chdir(self.agent_name)

        # import tool by self.tool_name from local tools.py file
        try:
            tool = ToolFactory.from_file(f"./tools/{self.tool_name}.py")
        except Exception as e:
            raise ValueError(f"Error importing tool {self.tool_name}: {e}")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

        try:
            if not self.arguments:
                output = tool().run()
            else:
                output = tool(**eval(self.arguments)).run()
        except Exception as e:
            raise ValueError(f"Error running tool {self.tool_name}: {e}")
        finally:
            os.chdir(self._shared_state.get("default_folder"))

        if not output:
            raise ValueError(f"Tool {self.tool_name} did not return any output.")

        return f"Successfully initialized and ran tool. Output: '{output}'"

    @model_validator(mode="after")
    def validate_tool_name(self):
        check_agency_path(self)

        if not self.agent_name and not self._shared_state.get("agent_name"):
            raise ValueError("Please provide agent name.")

        agent_name = self.agent_name or self._shared_state.get("agent_name")

        tool_path = os.path.join(self._shared_state.get("agency_path"), agent_name)
        tool_path = os.path.join(str(tool_path), "tools")
        tool_path = os.path.join(tool_path, self.tool_name + ".py")


        # check if tools.py file exists
        if not os.path.isfile(tool_path):
            available_tools = os.listdir(os.path.join(self._shared_state.get("agency_path"), agent_name))
            available_tools = [tool for tool in available_tools if tool.endswith(".py")]
            available_tools = [tool for tool in available_tools if
                               not tool.startswith("__") and not tool.startswith(".")]
            available_tools = [tool.replace(".py", "") for tool in available_tools]
            available_tools = ", ".join(available_tools)
            raise ValueError(f"Tool {self.tool_name} not found. Available tools are: {available_tools}")

        agent_path = os.path.join(self._shared_state.get("agency_path"), self.agent_name)
        if not os.path.exists(agent_path):
            available_agents = os.listdir(self._shared_state.get("agency_path"))
            available_agents = [agent for agent in available_agents if
                                os.path.isdir(os.path.join(self._shared_state.get("agency_path"), agent))]
            raise ValueError(f"Agent {self.agent_name} not found. Available agents are: {available_agents}")

        return True


if __name__ == "__main__":
    TestTool._shared_state.data = {"agency_path": "/Users/vrsen/Projects/agency-swarm/agency-swarm/TestAgency",
                              "default_folder": "/Users/vrsen/Projects/agency-swarm/agency-swarm/TestAgency"}
    test_tool = TestTool(agent_name="TestAgent", tool_name="PrintTestTool", arguments="{}", chain_of_thought="")
    print(test_tool.run())


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\ToolCreator\__init__.py
================================================
from .ToolCreator import ToolCreator

================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\util.py
================================================
import os
from pathlib import Path


def check_agency_path(self):
    if not self._shared_state.get("default_folder"):
        self._shared_state.set('default_folder', Path.cwd())

    if not self._shared_state.get("agency_path") and not self.agency_name:
        available_agencies = os.listdir("./")
        available_agencies = [agency for agency in available_agencies if os.path.isdir(agency)]
        raise ValueError(f"Please specify an agency. Available agencies are: {available_agencies}")
    elif not self._shared_state.get("agency_path") and self.agency_name:
        if not os.path.exists(os.path.join("./", self.agency_name)):
            available_agencies = os.listdir("./")
            available_agencies = [agency for agency in available_agencies if os.path.isdir(agency)]
            raise ValueError(f"Agency {self.agency_name} not found. Available agencies are: {available_agencies}")
        self._shared_state.set("agency_path", os.path.join("./", self.agency_name))


def check_agent_path(self):
    agent_path = os.path.join(self._shared_state.get("agency_path"), self.agent_name)
    if not os.path.exists(agent_path):
        available_agents = os.listdir(self._shared_state.get("agency_path"))
        available_agents = [agent for agent in available_agents if
                            os.path.isdir(os.path.join(self._shared_state.get("agency_path"), agent))]
        raise ValueError(f"Agent {self.agent_name} not found. Available agents are: {available_agents}")


================================================
File: /agency-swarm-main\agency_swarm\agency\genesis\__init__.py
================================================
from .GenesisAgency import GenesisAgency

================================================
File: /agency-swarm-main\agency_swarm\agency\__init__.py
================================================
from .agency import Agency


================================================
File: /agency-swarm-main\agency_swarm\agents\agent.py
================================================
import copy
import inspect
import json
import os
from typing import Dict, Union, Any, Type, Literal, TypedDict, Optional
from typing import List

from deepdiff import DeepDiff
from openai import NotFoundError
from openai.types.beta.assistant import ToolResources

from agency_swarm.tools import BaseTool, ToolFactory, Retrieval
from agency_swarm.tools import FileSearch, CodeInterpreter
from agency_swarm.tools.oai.FileSearch import FileSearchConfig
from agency_swarm.util.oai import get_openai_client
from agency_swarm.util.openapi import validate_openapi_spec
from agency_swarm.util.shared_state import SharedState
from pydantic import BaseModel
from openai.lib._parsing._completions import type_to_response_format_param

class ExampleMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str
    attachments: Optional[List[dict]]
    metadata: Optional[Dict[str, str]]


class Agent():
    _shared_state: SharedState = None
    
    @property
    def assistant(self):
        if not hasattr(self, '_assistant') or self._assistant is None:
            raise Exception("Assistant is not initialized. Please run init_oai() first.")
        return self._assistant

    @assistant.setter
    def assistant(self, value):
        self._assistant = value

    @property
    def functions(self):
        return [tool for tool in self.tools if issubclass(tool, BaseTool)]
    
    @property
    def shared_state(self):
        return self._shared_state

    @shared_state.setter
    def shared_state(self, value):
        self._shared_state = value
        for tool in self.tools:
            if issubclass(tool, BaseTool):
                tool._shared_state = value

    def response_validator(self, message: str | list) -> str:
        """
        Validates the response from the agent. If the response is invalid, it must raise an exception with instructions
        for the caller agent on how to proceed.

        Parameters:
            message (str): The response from the agent.

        Returns:
            str: The validated response.
        """
        return message

    def __init__(
            self,
            id: str = None,
            name: str = None,
            description: str = None,
            instructions: str = "",
            tools: List[Union[Type[BaseTool], Type[FileSearch], Type[CodeInterpreter], type[Retrieval]]] = None,
            tool_resources: ToolResources = None,
            temperature: float = None,
            top_p: float = None,
            response_format: Union[str, dict, type] = "auto",
            tools_folder: str = None,
            files_folder: Union[List[str], str] = None,
            schemas_folder: Union[List[str], str] = None,
            api_headers: Dict[str, Dict[str, str]] = None,
            api_params: Dict[str, Dict[str, str]] = None,
            file_ids: List[str] = None,
            metadata: Dict[str, str] = None,
            model: str = "gpt-4o-2024-08-06",
            validation_attempts: int = 1,
            max_prompt_tokens: int = None,
            max_completion_tokens: int = None,
            truncation_strategy: dict = None,
            examples: List[ExampleMessage] = None,
            file_search: FileSearchConfig = None,
            parallel_tool_calls: bool = True,
            refresh_from_id: bool = True,
    ):
        """
        Initializes an Agent with specified attributes, tools, and OpenAI client.

        Parameters:
            id (str, optional): Loads the assistant from OpenAI assistant ID. Assistant will be created or loaded from settings if ID is not provided. Defaults to None.
            name (str, optional): Name of the agent. Defaults to the class name if not provided.
            description (str, optional): A brief description of the agent's purpose. Defaults to None.
            instructions (str, optional): Path to a file containing specific instructions for the agent. Defaults to an empty string.
            tools (List[Union[Type[BaseTool], Type[Retrieval], Type[CodeInterpreter]]], optional): A list of tools (as classes) that the agent can use. Defaults to an empty list.
            tool_resources (ToolResources, optional): A set of resources that are used by the assistant's tools. The resources are specific to the type of tool. For example, the code_interpreter tool requires a list of file IDs, while the file_search tool requires a list of vector store IDs. Defaults to None.
            temperature (float, optional): The temperature parameter for the OpenAI API. Defaults to None.
            top_p (float, optional): The top_p parameter for the OpenAI API. Defaults to None.
            response_format (Union[str, Dict, type], optional): The response format for the OpenAI API. If BaseModel is provided, it will be converted to a response format. Defaults to None.
            tools_folder (str, optional): Path to a directory containing tools associated with the agent. Each tool must be defined in a separate file. File must be named as the class name of the tool. Defaults to None.
            files_folder (Union[List[str], str], optional): Path or list of paths to directories containing files associated with the agent. Defaults to None.
            schemas_folder (Union[List[str], str], optional): Path or list of paths to directories containing OpenAPI schemas associated with the agent. Defaults to None.
            api_headers (Dict[str,Dict[str, str]], optional): Headers to be used for the openapi requests. Each key must be a full filename from schemas_folder. Defaults to an empty dictionary.
            api_params (Dict[str, Dict[str, str]], optional): Extra params to be used for the openapi requests. Each key must be a full filename from schemas_folder. Defaults to an empty dictionary.
            metadata (Dict[str, str], optional): Metadata associated with the agent. Defaults to an empty dictionary.
            model (str, optional): The model identifier for the OpenAI API. Defaults to "gpt-4o".
            validation_attempts (int, optional): Number of attempts to validate the response with response_validator function. Defaults to 1.
            max_prompt_tokens (int, optional): Maximum number of tokens allowed in the prompt. Defaults to None.
            max_completion_tokens (int, optional): Maximum number of tokens allowed in the completion. Defaults to None.
            truncation_strategy (TruncationStrategy, optional): Truncation strategy for the OpenAI API. Defaults to None.
            examples (List[Dict], optional): A list of example messages for the agent. Defaults to None.
            file_search (FileSearchConfig, optional): A dictionary containing the file search tool configuration. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.
            refresh_from_id (bool, optional): Whether to load and update the agent from the OpenAI assistant ID when provided. Defaults to True.

        This constructor sets up the agent with its unique properties, initializes the OpenAI client, reads instructions if provided, and uploads any associated files.
        """
        # public attributes
        self.id = id
        self.name = name if name else self.__class__.__name__
        self.description = description
        self.instructions = instructions
        self.tools = tools[:] if tools is not None else []
        self.tools = [tool for tool in self.tools if tool.__name__ != "ExampleTool"]
        self.tool_resources = tool_resources
        self.temperature = temperature
        self.top_p = top_p
        self.response_format = response_format
        # use structured outputs if response_format is a BaseModel
        if isinstance(self.response_format, type):
            self.response_format = type_to_response_format_param(self.response_format)
        self.tools_folder = tools_folder
        self.files_folder = files_folder if files_folder else []
        self.schemas_folder = schemas_folder if schemas_folder else []
        self.api_headers = api_headers if api_headers else {}
        self.api_params = api_params if api_params else {}
        self.metadata = metadata if metadata else {}
        self.model = model
        self.validation_attempts = validation_attempts
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.truncation_strategy = truncation_strategy
        self.examples = examples
        self.file_search = file_search
        self.parallel_tool_calls = parallel_tool_calls
        self.refresh_from_id = refresh_from_id

        self.settings_path = './settings.json'

        # private attributes
        self._assistant: Any = None
        self._shared_instructions = None

        # init methods
        self.client = get_openai_client()
        self._read_instructions()

        # upload files
        self._upload_files()
        if file_ids:
            print("Warning: 'file_ids' parameter is deprecated. Please use 'tool_resources' parameter instead.")
            self.add_file_ids(file_ids, "file_search")

        self._parse_schemas()
        self._parse_tools_folder()

    # --- OpenAI Assistant Methods ---

    def init_oai(self):
        """
        Initializes the OpenAI assistant for the agent.

        This method handles the initialization and potential updates of the agent's OpenAI assistant. It loads the assistant based on a saved ID, updates the assistant if necessary, or creates a new assistant if it doesn't exist. After initialization or update, it saves the assistant's settings.

        Output:
            self: Returns the agent instance for chaining methods or further processing.
        """

        # check if settings.json exists
        path = self.get_settings_path()

        # load assistant from id
        if self.id:
            if not self.refresh_from_id:
                return self
            
            self.assistant = self.client.beta.assistants.retrieve(self.id)
            # Assign attributes to self if they are None
            self.instructions = self.instructions or self.assistant.instructions
            self.name = self.name if self.name != self.__class__.__name__ else self.assistant.name
            self.description = self.description or self.assistant.description
            self.temperature = self.assistant.temperature if self.temperature is None else self.temperature
            self.top_p = self.top_p or self.assistant.top_p
            self.response_format = self.response_format or self.assistant.response_format
            if not isinstance(self.response_format, str):
                self.response_format = self.response_format or self.response_format.model_dump()
            else:
                self.response_format = self.response_format or self.assistant.response_format
            self.tool_resources = self.tool_resources or self.assistant.tool_resources.model_dump()
            self.metadata = self.metadata or self.assistant.metadata
            self.model = self.model or self.assistant.model
            self.tool_resources = self.tool_resources or self.assistant.tool_resources.model_dump()

            for tool in self.assistant.tools:
                # update assistants created with v1
                if tool.type == "retrieval":
                    self.client.beta.assistants.update(self.id, tools=self.get_oai_tools())

            # update assistant if parameters are different
            if not self._check_parameters(self.assistant.model_dump()):
                self._update_assistant()

            return self

        # load assistant from settings
        if os.path.exists(path):
            with open(path, 'r') as f:
                settings = json.load(f)
                # iterate settings and find the assistant with the same name
                for assistant_settings in settings:
                    if assistant_settings['name'] == self.name:
                        try:
                            self.assistant = self.client.beta.assistants.retrieve(assistant_settings['id'])
                            self.id = assistant_settings['id']

                            # update assistant if parameters are different
                            if not self._check_parameters(self.assistant.model_dump()):
                                print("Updating agent... " + self.name)
                                self._update_assistant()

                            if self.assistant.tool_resources:
                                self.tool_resources = self.assistant.tool_resources.model_dump()

                            self._update_settings()
                            return self
                        except NotFoundError:
                            continue

        # create assistant if settings.json does not exist or assistant with the same name does not exist
        self.assistant = self.client.beta.assistants.create(
            model=self.model,
            name=self.name,
            description=self.description,
            instructions=self.instructions,
            tools=self.get_oai_tools(),
            tool_resources=self.tool_resources,
            metadata=self.metadata,
            temperature=self.temperature,
            top_p=self.top_p,
            response_format=self.response_format,
        )

        if self.assistant.tool_resources:
            self.tool_resources = self.assistant.tool_resources.model_dump()

        self.id = self.assistant.id

        self._save_settings()

        return self

    def _update_assistant(self):
        """
        Updates the existing assistant's parameters on the OpenAI server.

        This method updates the assistant's details such as name, description, instructions, tools, file IDs, metadata, and the model. It only updates parameters that have non-empty values. After updating the assistant, it also updates the local settings file to reflect these changes.

        No input parameters are directly passed to this method as it uses the agent's instance attributes.

        No output parameters are returned, but the method updates the assistant's details on the OpenAI server and locally updates the settings file.
        """
        tool_resources = copy.deepcopy(self.tool_resources)
        if tool_resources and tool_resources.get('file_search'):
            tool_resources['file_search'].pop('vector_stores', None)

        params = {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": self.get_oai_tools(),
            "tool_resources": tool_resources,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "response_format": self.response_format,
            "metadata": self.metadata,
            "model": self.model
        }
        params = {k: v for k, v in params.items() if v}
        self.assistant = self.client.beta.assistants.update(
            self.id,
            **params,
        )
        self._update_settings()

    def _upload_files(self):
        def add_id_to_file(f_path, id):
            """Add file id to file name"""
            if os.path.isfile(f_path):
                file_name, file_ext = os.path.splitext(f_path)
                f_path_new = file_name + "_" + id + file_ext
                os.rename(f_path, f_path_new)
                return f_path_new

        def get_id_from_file(f_path):
            """Get file id from file name"""
            if os.path.isfile(f_path):
                file_name, file_ext = os.path.splitext(f_path)
                file_name = os.path.basename(file_name)
                file_name = file_name.split("_")
                if len(file_name) > 1:
                    return file_name[-1] if "file-" in file_name[-1] else None
                else:
                    return None

        files_folders = self.files_folder if isinstance(self.files_folder, list) else [self.files_folder]

        file_search_ids = []
        code_interpreter_ids = []

        for files_folder in files_folders:
            if isinstance(files_folder, str):
                f_path = files_folder

                if not os.path.isdir(f_path):
                    f_path = os.path.join(self.get_class_folder_path(), files_folder)
                    f_path = os.path.normpath(f_path)

                if os.path.isdir(f_path):
                    f_paths = os.listdir(f_path)

                    f_paths = [f for f in f_paths if not f.startswith(".")]

                    f_paths = [os.path.join(f_path, f) for f in f_paths]

                    code_interpreter_file_extensions = [
                        ".json",  # JSON
                        ".csv",  # CSV
                        ".xml",  # XML
                        ".jpeg",  # JPEG
                        ".jpg",  # JPEG
                        ".gif",  # GIF
                        ".png",  # PNG
                        ".zip"  # ZIP
                    ]

                    for f_path in f_paths:
                        file_ext = os.path.splitext(f_path)[1]

                        f_path = f_path.strip()
                        file_id = get_id_from_file(f_path)
                        if file_id:
                            print("File already uploaded. Skipping... " + os.path.basename(f_path))
                        else:
                            print("Uploading new file... " + os.path.basename(f_path))
                            with open(f_path, 'rb') as f:
                                file_id = self.client.with_options(
                                    timeout=80 * 1000,
                                ).files.create(file=f, purpose="assistants").id
                            add_id_to_file(f_path, file_id)

                        if file_ext in code_interpreter_file_extensions:
                            code_interpreter_ids.append(file_id)
                        else:
                            file_search_ids.append(file_id)
                else:
                    print(f"Files folder '{f_path}' is not a directory. Skipping...", )
            else:
                print("Files folder path must be a string or list of strings. Skipping... ", files_folder)

        if FileSearch not in self.tools and file_search_ids:
            print("Detected files without FileSearch. Adding FileSearch tool...")
            self.add_tool(FileSearch)
        if CodeInterpreter not in self.tools and code_interpreter_ids:
            print("Detected files without CodeInterpreter. Adding CodeInterpreter tool...")
            self.add_tool(CodeInterpreter)

        self.add_file_ids(file_search_ids, "file_search")
        self.add_file_ids(code_interpreter_ids, "code_interpreter")

    # --- Tool Methods ---

    # TODO: fix 2 methods below
    def add_tool(self, tool):
        if not isinstance(tool, type):
            raise Exception("Tool must not be initialized.")

        subclasses = [FileSearch, CodeInterpreter, Retrieval]
        for subclass in subclasses:
            if issubclass(tool, subclass):
                if not any(issubclass(t, subclass) for t in self.tools):
                    self.tools.append(tool)
                return
        
        if issubclass(tool, BaseTool):
            if tool.__name__ == "ExampleTool":
                print("Skipping importing ExampleTool...")
                return
            self.tools = [t for t in self.tools if t.__name__ != tool.__name__]
            self.tools.append(tool)
        else:
            raise Exception("Invalid tool type.")

    def get_oai_tools(self):
        tools = []
        for tool in self.tools:
            if not isinstance(tool, type):
                print(tool)
                raise Exception("Tool must not be initialized.")

            if issubclass(tool, FileSearch):
                tools.append(tool(file_search=self.file_search).model_dump(exclude_none=True))
            elif issubclass(tool, CodeInterpreter):
                tools.append(tool().model_dump())
            elif issubclass(tool, Retrieval):
                tools.append(tool().model_dump())
            elif issubclass(tool, BaseTool):
                tools.append({
                    "type": "function",
                    "function": tool.openai_schema
                })
            else:
                raise Exception("Invalid tool type.")
        return tools

    def _parse_schemas(self):
        schemas_folders = self.schemas_folder if isinstance(self.schemas_folder, list) else [self.schemas_folder]

        for schemas_folder in schemas_folders:
            if isinstance(schemas_folder, str):
                f_path = schemas_folder

                if not os.path.isdir(f_path):
                    f_path = os.path.join(self.get_class_folder_path(), schemas_folder)
                    f_path = os.path.normpath(f_path)

                if os.path.isdir(f_path):
                    f_paths = os.listdir(f_path)

                    f_paths = [f for f in f_paths if not f.startswith(".")]

                    f_paths = [os.path.join(f_path, f) for f in f_paths]

                    for f_path in f_paths:
                        with open(f_path, 'r') as f:
                            openapi_spec = f.read()
                        try:
                            validate_openapi_spec(openapi_spec)
                        except Exception as e:
                            print("Invalid OpenAPI schema: " + os.path.basename(f_path))
                            raise e
                        try:
                            headers = None
                            params = None
                            if os.path.basename(f_path) in self.api_headers:
                                headers = self.api_headers[os.path.basename(f_path)]
                            if os.path.basename(f_path) in self.api_params:
                                params = self.api_params[os.path.basename(f_path)]
                            tools = ToolFactory.from_openapi_schema(openapi_spec, headers=headers, params=params)
                        except Exception as e:
                            print("Error parsing OpenAPI schema: " + os.path.basename(f_path))
                            raise e
                        for tool in tools:
                            self.add_tool(tool)
                else:
                    print("Schemas folder path is not a directory. Skipping... ", f_path)
            else:
                print("Schemas folder path must be a string or list of strings. Skipping... ", schemas_folder)

    def _parse_tools_folder(self):
        if not self.tools_folder:
            return

        if not os.path.isdir(self.tools_folder):
            self.tools_folder = os.path.join(self.get_class_folder_path(), self.tools_folder)
            self.tools_folder = os.path.normpath(self.tools_folder)

        if os.path.isdir(self.tools_folder):
            f_paths = os.listdir(self.tools_folder)
            f_paths = [f for f in f_paths if not f.startswith(".") and not f.startswith("__")]
            f_paths = [os.path.join(self.tools_folder, f) for f in f_paths]
            for f_path in f_paths:
                if not f_path.endswith(".py"):
                    continue
                if os.path.isfile(f_path):
                    try:
                        tool = ToolFactory.from_file(f_path)
                        self.add_tool(tool)
                    except Exception as e:
                        print(f"Error parsing tool file {os.path.basename(f_path)}: {e}. Skipping...")
                else:
                    print("Items in tools folder must be files. Skipping... ", f_path)
        else:
            print("Tools folder path is not a directory. Skipping... ", self.tools_folder)

    def get_openapi_schema(self, url):
        """Get openapi schema that contains all tools from the agent as different api paths. Make sure to call this after agency has been initialized."""
        if self.assistant is None:
            raise Exception(
                "Assistant is not initialized. Please initialize the agency first, before using this method")

        return ToolFactory.get_openapi_schema(self.tools, url)

    # --- Settings Methods ---

    def _check_parameters(self, assistant_settings, debug=False):
        """
        Checks if the agent's parameters match with the given assistant settings.

        Parameters:
            assistant_settings (dict): A dictionary containing the settings of an assistant.
            debug (bool): If True, prints debug statements. Default is False.

        Returns:
            bool: True if all the agent's parameters match the assistant settings, False otherwise.

        This method compares the current agent's parameters such as name, description, instructions, tools, file IDs, metadata, and model with the given assistant settings. It uses DeepDiff to compare complex structures like tools and metadata. If any parameter does not match, it returns False; otherwise, it returns True.
        """
        if self.name != assistant_settings['name']:
            if debug:
                print(f"Name mismatch: {self.name} != {assistant_settings['name']}")
            return False

        if self.description != assistant_settings['description']:
            if debug:
                print(f"Description mismatch: {self.description} != {assistant_settings['description']}")
            return False

        if self.instructions != assistant_settings['instructions']:
            if debug:
                print(f"Instructions mismatch: {self.instructions} != {assistant_settings['instructions']}")
            return False

        def clean_tool(tool):
            if isinstance(tool, dict):
                if 'function' in tool and 'strict' in tool['function'] and not tool['function']['strict']:
                    tool['function'].pop('strict', None)
            return tool

        local_tools = [clean_tool(tool) for tool in self.get_oai_tools()]
        assistant_tools = [clean_tool(tool) for tool in assistant_settings['tools']]

        # find file_search and code_interpreter tools in local_tools and assistant_tools
        # Find file_search tools in local and assistant tools
        local_file_search = next((tool for tool in local_tools if tool['type'] == 'file_search'), None)
        assistant_file_search = next((tool for tool in assistant_tools if tool['type'] == 'file_search'), None)

        if local_file_search:
            # If local file_search doesn't have a 'file_search' key, use assistant's if available
            if 'file_search' not in local_file_search and assistant_file_search and 'file_search' in assistant_file_search:
                local_file_search['file_search'] = assistant_file_search['file_search']
            elif 'file_search' in local_file_search:
                # Update max_num_results if not set locally but available in assistant
                if 'max_num_results' not in local_file_search['file_search'] and assistant_file_search and \
                   assistant_file_search['file_search'].get('max_num_results') is not None:
                    local_file_search['file_search']['max_num_results'] = assistant_file_search['file_search']['max_num_results']
                
                # Update ranking_options if not set locally but available in assistant
                if 'ranking_options' not in local_file_search['file_search'] and assistant_file_search and \
                   assistant_file_search['file_search'].get('ranking_options') is not None:
                    local_file_search['file_search']['ranking_options'] = assistant_file_search['file_search']['ranking_options']

        local_tools.sort(key=lambda x: json.dumps(x, sort_keys=True))
        assistant_tools.sort(key=lambda x: json.dumps(x, sort_keys=True))

        tools_diff = DeepDiff(local_tools, assistant_tools, ignore_order=True)
        if tools_diff:
            if debug:
                print(f"Tools mismatch: {tools_diff}")
                print("Local tools:", local_tools)
                print("Assistant tools:", assistant_tools)
            return False

        if self.temperature != assistant_settings['temperature']:
            if debug:
                print(f"Temperature mismatch: {self.temperature} != {assistant_settings['temperature']}")
            return False

        if self.top_p != assistant_settings['top_p']:
            if debug:
                print(f"Top_p mismatch: {self.top_p} != {assistant_settings['top_p']}")
            return False

        # adjust differences between local and assistant tool resources
        tool_resources_settings = copy.deepcopy(self.tool_resources)
        if tool_resources_settings is None:
            tool_resources_settings = {}
        if tool_resources_settings.get('file_search'):
            tool_resources_settings['file_search'].pop('vector_stores', None)
        if tool_resources_settings.get('file_search') is None:
            tool_resources_settings['file_search'] = {'vector_store_ids': []}
        if tool_resources_settings.get('code_interpreter') is None:
            tool_resources_settings['code_interpreter'] = {"file_ids": []}
        
        assistant_tool_resources = assistant_settings['tool_resources']
        if assistant_tool_resources is None:
            assistant_tool_resources = {}
        if assistant_tool_resources.get('code_interpreter') is None:
            assistant_tool_resources['code_interpreter'] = {"file_ids": []}
        if assistant_tool_resources.get('file_search') is None:
            assistant_tool_resources['file_search'] = {'vector_store_ids': []}

        tool_resources_diff = DeepDiff(tool_resources_settings, assistant_tool_resources, ignore_order=True)
        if tool_resources_diff != {}:
            if debug:
                print(f"Tool resources mismatch: {tool_resources_diff}")
                print("Local tool resources:", tool_resources_settings)
                print("Assistant tool resources:", assistant_settings['tool_resources'])
            return False

        metadata_diff = DeepDiff(self.metadata, assistant_settings['metadata'], ignore_order=True)
        if metadata_diff != {}:
            if debug:
                print(f"Metadata mismatch: {metadata_diff}")
            return False

        if self.model != assistant_settings['model']:
            if debug:
                print(f"Model mismatch: {self.model} != {assistant_settings['model']}")
            return False

        response_format_diff = DeepDiff(self.response_format, assistant_settings['response_format'], ignore_order=True)
        if response_format_diff != {}:
            if debug:
                print(f"Response format mismatch: {response_format_diff}")
            return False

        return True

    def _save_settings(self):
        path = self.get_settings_path()
        # check if settings.json exists
        if not os.path.isfile(path):
            with open(path, 'w') as f:
                json.dump([self.assistant.model_dump()], f, indent=4)
        else:
            settings = []
            with open(path, 'r') as f:
                settings = json.load(f)
                settings.append(self.assistant.model_dump())
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)

    def _update_settings(self):
        path = self.get_settings_path()
        # check if settings.json exists
        if os.path.isfile(path):
            settings = []
            with open(path, 'r') as f:
                settings = json.load(f)
                for i, assistant_settings in enumerate(settings):
                    if assistant_settings['id'] == self.id:
                        settings[i] = self.assistant.model_dump()
                        break
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)

    # --- Helper Methods ---

    def add_file_ids(self, file_ids: List[str], tool_resource: Literal["code_interpreter", "file_search"]):
        if not file_ids:
            return

        if self.tool_resources is None:
            self.tool_resources = {}

        if tool_resource == "code_interpreter":
            if CodeInterpreter not in self.tools:
                raise Exception("CodeInterpreter tool not found in tools.")

            if tool_resource not in self.tool_resources or self.tool_resources[
                tool_resource] is None:
                self.tool_resources[tool_resource] = {
                    "file_ids": file_ids
                }

            self.tool_resources[tool_resource]['file_ids'] = file_ids
        elif tool_resource == "file_search":
            if FileSearch not in self.tools:
                raise Exception("FileSearch tool not found in tools.")

            if tool_resource not in self.tool_resources or self.tool_resources[
                tool_resource] is None:
                self.tool_resources[tool_resource] = {
                    "vector_stores": [{
                        "file_ids": file_ids
                    }]
                }
            elif not self.tool_resources[tool_resource].get('vector_store_ids'):
                self.tool_resources[tool_resource]['vector_stores'] = [{
                    "file_ids": file_ids
                }]
            else:
                vector_store_id = self.tool_resources[tool_resource]['vector_store_ids'][0]
                self.client.beta.vector_stores.file_batches.create(
                    vector_store_id=vector_store_id,
                    file_ids=file_ids
                )
        else:
            raise Exception("Invalid tool resource.")

    def get_settings_path(self):
        return self.settings_path

    def _read_instructions(self):
        class_instructions_path = os.path.normpath(os.path.join(self.get_class_folder_path(), self.instructions))
        if os.path.isfile(class_instructions_path):
            with open(class_instructions_path, 'r') as f:
                self.instructions = f.read()
        elif os.path.isfile(self.instructions):
            with open(self.instructions, 'r') as f:
                self.instructions = f.read()
        elif "./instructions.md" in self.instructions or "./instructions.txt" in self.instructions:
            raise Exception("Instructions file not found.")

    def get_class_folder_path(self):
        try:
            # First, try to use the __file__ attribute of the module
            return os.path.abspath(os.path.dirname(self.__module__.__file__))
        except (TypeError, OSError, AttributeError) as e:
            # If that fails, fall back to inspect
            try:
                class_file = inspect.getfile(self.__class__)
            except (TypeError, OSError, AttributeError) as e:
                return "./"
            return os.path.abspath(os.path.realpath(os.path.dirname(class_file)))

    def add_shared_instructions(self, instructions: str):
        if not instructions:
            return

        if self._shared_instructions is None:
            self._shared_instructions = instructions
        else:
            self.instructions = self.instructions.replace(self._shared_instructions, "")
            self.instructions = self.instructions.strip().strip("\n")
            self._shared_instructions = instructions

        self.instructions = self._shared_instructions + "\n\n" + self.instructions

    # --- Cleanup Methods ---
    def delete(self):
        """Deletes assistant, all vector stores, and all files associated with the agent."""
        self._delete_assistant()
        self._delete_files()
        self._delete_settings()

    def _delete_files(self):
        if not self.tool_resources:
            return

        file_ids = []
        if self.tool_resources.get('code_interpreter'):
            file_ids = self.tool_resources['code_interpreter'].get('file_ids', [])

        if self.tool_resources.get('file_search'):
            file_search_vector_store_ids = self.tool_resources['file_search'].get('vector_store_ids', [])
            for vector_store_id in file_search_vector_store_ids:
                files = self.client.beta.vector_stores.files.list(vector_store_id=vector_store_id, limit=100)
                for file in files:
                    file_ids.append(file.id)

                self.client.beta.vector_stores.delete(vector_store_id)

        for file_id in file_ids:
            self.client.files.delete(file_id)

    def _delete_assistant(self):
        self.client.beta.assistants.delete(self.id)
        self._delete_settings()

    def _delete_settings(self):
        path = self.get_settings_path()
        # check if settings.json exists
        if os.path.isfile(path):
            settings = []
            with open(path, 'r') as f:
                settings = json.load(f)
                for i, assistant_settings in enumerate(settings):
                    if assistant_settings['id'] == self.id:
                        settings.pop(i)
                        break
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\BrowsingAgent.py
================================================
import json
import re

from agency_swarm.agents import Agent
from agency_swarm.tools.oai import FileSearch
from typing_extensions import override
import base64


class BrowsingAgent(Agent):
    SCREENSHOT_FILE_NAME = "screenshot.jpg"

    def __init__(self, selenium_config=None, **kwargs):
        from .tools.util.selenium import set_selenium_config
        super().__init__(
            name="BrowsingAgent",
            description="This agent is designed to navigate and search web effectively.",
            instructions="./instructions.md",
            files_folder="./files",
            schemas_folder="./schemas",
            tools=[],
            tools_folder="./tools",
            temperature=0,
            max_prompt_tokens=16000,
            model="gpt-4o",
            validation_attempts=25,
            **kwargs
        )
        if selenium_config is not None:
            set_selenium_config(selenium_config)

        self.prev_message = ""

    @override
    def response_validator(self, message):
        from .tools.util.selenium import get_web_driver, set_web_driver
        from .tools.util import highlight_elements_with_labels, remove_highlight_and_labels
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.select import Select

        # Filter out everything in square brackets
        filtered_message = re.sub(r'\[.*?\]', '', message).strip()
        
        if filtered_message and self.prev_message == filtered_message:
            raise ValueError("Do not repeat yourself. If you are stuck, try a different approach or search in google for the page you are looking for directly.")
        
        self.prev_message = filtered_message

        if "[send screenshot]" in message.lower():
            wd = get_web_driver()
            remove_highlight_and_labels(wd)
            self.take_screenshot()
            response_text = "Here is the screenshot of the current web page:"

        elif '[highlight clickable elements]' in message.lower():
            wd = get_web_driver()
            highlight_elements_with_labels(wd, 'a, button, div[onclick], div[role="button"], div[tabindex], '
                                               'span[onclick], span[role="button"], span[tabindex]')
            self._shared_state.set("elements_highlighted", 'a, button, div[onclick], div[role="button"], div[tabindex], '
                                               'span[onclick], span[role="button"], span[tabindex]')

            self.take_screenshot()

            all_elements = wd.find_elements(By.CSS_SELECTOR, '.highlighted-element')

            all_element_texts = [element.text for element in all_elements]

            element_texts_json = {}
            for i, element_text in enumerate(all_element_texts):
                element_texts_json[str(i + 1)] = self.remove_unicode(element_text)
            
            element_texts_json = {k: v for k, v in element_texts_json.items() if v}

            element_texts_formatted = ", ".join([f"{k}: {v}" for k, v in element_texts_json.items()])

            response_text = ("Here is the screenshot of the current web page with highlighted clickable elements. \n\n"
                             "Texts of the elements are: " + element_texts_formatted + ".\n\n"
                             "Elements without text are not shown, but are available on screenshot. \n"
                             "Please make sure to analyze the screenshot to find the clickable element you need to click on.")

        elif '[highlight text fields]' in message.lower():
            wd = get_web_driver()
            highlight_elements_with_labels(wd, 'input, textarea')
            self._shared_state.set("elements_highlighted", "input, textarea")

            self.take_screenshot()

            all_elements = wd.find_elements(By.CSS_SELECTOR, '.highlighted-element')

            all_element_texts = [element.text for element in all_elements]

            element_texts_json = {}
            for i, element_text in enumerate(all_element_texts):
                element_texts_json[str(i + 1)] = self.remove_unicode(element_text)

            element_texts_formatted = ", ".join([f"{k}: {v}" for k, v in element_texts_json.items()])

            response_text = ("Here is the screenshot of the current web page with highlighted text fields: \n"
                             "Texts of the elements are: " + element_texts_formatted + ".\n"
                             "Please make sure to analyze the screenshot to find the text field you need to fill.")

        elif '[highlight dropdowns]' in message.lower():
            wd = get_web_driver()
            highlight_elements_with_labels(wd, 'select')
            self._shared_state.set("elements_highlighted", "select")

            self.take_screenshot()

            all_elements = wd.find_elements(By.CSS_SELECTOR, '.highlighted-element')

            all_selector_values = {}

            i = 0
            for element in all_elements:
                select = Select(element)
                options = select.options
                selector_values = {}
                for j, option in enumerate(options):
                    selector_values[str(j)] = option.text
                    if j > 10:
                        break
                all_selector_values[str(i + 1)] = selector_values

            all_selector_values = {k: v for k, v in all_selector_values.items() if v}
            all_selector_values_formatted = ", ".join([f"{k}: {v}" for k, v in all_selector_values.items()])

            response_text = ("Here is the screenshot with highlighted dropdowns. \n"
                             "Selector values are: " + all_selector_values_formatted + ".\n"
                             "Please make sure to analyze the screenshot to find the dropdown you need to select.")

        else:
            return message

        set_web_driver(wd)
        content = self.create_response_content(response_text)
        raise ValueError(content)

    def take_screenshot(self):
        from .tools.util.selenium import get_web_driver
        from .tools.util import get_b64_screenshot
        wd = get_web_driver()
        screenshot = get_b64_screenshot(wd)
        screenshot_data = base64.b64decode(screenshot)
        with open(self.SCREENSHOT_FILE_NAME, "wb") as screenshot_file:
            screenshot_file.write(screenshot_data)

    def create_response_content(self, response_text):
        with open(self.SCREENSHOT_FILE_NAME, "rb") as file:
            file_id = self.client.files.create(
                file=file,
                purpose="vision",
            ).id

        content = [
            {"type": "text", "text": response_text},
            {
                "type": "image_file",
                "image_file": {"file_id": file_id}
            }
        ]
        return content

    # Function to check for Unicode escape sequences
    def remove_unicode(self, data):
        return re.sub(r'[^\x00-\x7F]+', '', data)



================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\instructions.md
================================================
# Browsing Agent Instructions

As an advanced browsing agent, you are equipped with specialized tools to navigate and search the web effectively. Your primary objective is to fulfill the user's requests by efficiently utilizing these tools.

### Primary Instructions:

1. **Avoid Guessing URLs**: Never attempt to guess the direct URL. Always perform a Google search if applicable, or return to your previous search results.
2. **Navigating to New Pages**: Always use the `ClickElement` tool to open links when navigating to a new web page from the current source. Do not guess the direct URL.
3. **Single Page Interaction**: You can only open and interact with one web page at a time. The previous web page will be closed when you open a new one. To navigate back, use the `GoBack` tool.
4. **Requesting Screenshots**: Before using tools that interact with the web page, ask the user to send you the appropriate screenshot using one of the commands below.

### Commands to Request Screenshots:

- **'[send screenshot]'**: Sends the current browsing window as an image. Use this command if the user asks what is on the page.
- **'[highlight clickable elements]'**: Highlights all clickable elements on the current web page. This must be done before using the `ClickElement` tool.
- **'[highlight text fields]'**: Highlights all text fields on the current web page. This must be done before using the `SendKeys` tool.
- **'[highlight dropdowns]'**: Highlights all dropdowns on the current web page. This must be done before using the `SelectDropdown` tool.

### Important Reminders:

- Only open and interact with one web page at a time. Do not attempt to read or click on multiple links simultaneously. Complete your interactions with the current web page before proceeding to a different source.


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\requirements.txt
================================================
selenium
webdriver-manager
selenium_stealth

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\ClickElement.py
================================================
import time

from pydantic import Field
from selenium.webdriver.common.by import By

from agency_swarm.tools import BaseTool
from .util import get_web_driver, set_web_driver
from .util.highlights import remove_highlight_and_labels


class ClickElement(BaseTool):
    """
    This tool clicks on an element on the current web page based on its number.

    Before using this tool make sure to highlight clickable elements on the page by outputting '[highlight clickable elements]' message.
    """
    element_number: int = Field(
        ...,
        description="The number of the element to click on. The element numbers are displayed on the page after highlighting elements.",
    )

    def run(self):
        wd = get_web_driver()

        if 'button' not in self._shared_state.get("elements_highlighted", ""):
            raise ValueError("Please highlight clickable elements on the page first by outputting '[highlight clickable elements]' message. You must output just the message without calling the tool first, so the user can respond with the screenshot.")

        all_elements = wd.find_elements(By.CSS_SELECTOR, '.highlighted-element')

        # iterate through all elements with a number in the text
        try:
            element_text = all_elements[self.element_number - 1].text
            element_text = element_text.strip() if element_text else ""
            # Subtract 1 because sequence numbers start at 1, but list indices start at 0
            try:
                all_elements[self.element_number - 1].click()
            except Exception as e:
                if "element click intercepted" in str(e).lower():
                    wd.execute_script("arguments[0].click();", all_elements[self.element_number - 1])
                else:
                    raise e

            time.sleep(3)

            result = f"Clicked on element {self.element_number}. Text on clicked element: '{element_text}'. Current URL is {wd.current_url} To further analyze the page, output '[send screenshot]' command."
        except IndexError:
            result = "Element number is invalid. Please try again with a valid element number."
        except Exception as e:
            result = str(e)

        wd = remove_highlight_and_labels(wd)

        wd.execute_script("document.body.style.zoom='1.5'")

        set_web_driver(wd)

        self._shared_state.set("elements_highlighted", "")

        return result

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\ExportFile.py
================================================
import base64
import os

from agency_swarm.tools import BaseTool
from .util import get_web_driver


class ExportFile(BaseTool):
    """This tool converts the current full web page into a file and returns its file_id. You can then send this file id back to the user for further processing."""

    def run(self):
        wd = get_web_driver()
        from agency_swarm import get_openai_client
        client = get_openai_client()

        # Define the parameters for the PDF
        params = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
        }

        # Execute the command to print to PDF
        result = wd.execute_cdp_cmd('Page.printToPDF', params)
        pdf = result['data']

        pdf_bytes = base64.b64decode(pdf)

        # Save the PDF to a file
        with open("exported_file.pdf", "wb") as f:
            f.write(pdf_bytes)

        file_id = client.files.create(file=open("exported_file.pdf", "rb"), purpose="assistants",).id

        self._shared_state.set("file_id", file_id)

        return "Success. File exported with id: `" + file_id + "` You can now send this file id back to the user."


if __name__ == "__main__":
    wd = get_web_driver()
    wd.get("https://www.google.com")
    tool = ExportFile()
    tool.run()


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\GoBack.py
================================================
import time

from agency_swarm.tools import BaseTool

from .util.selenium import get_web_driver, set_web_driver


class GoBack(BaseTool):
    """W
    This tool allows you to go back 1 page in the browser history. Use it in case of a mistake or if a page shows you unexpected content.
    """

    def run(self):
        wd = get_web_driver()

        wd.back()

        time.sleep(3)

        set_web_driver(wd)

        return "Success. Went back 1 page. Current URL is: " + wd.current_url


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\ReadURL.py
================================================
import time

from pydantic import Field

from agency_swarm.tools import BaseTool
from .util.selenium import get_web_driver, set_web_driver


class ReadURL(BaseTool):
    """
This tool reads a single URL and opens it in your current browser window. For each new source, either navigate directly to a URL that you believe contains the answer to the user's question or perform a Google search (e.g., 'https://google.com/search?q=search') if necessary. 

If you are unsure of the direct URL, do not guess. Instead, use the ClickElement tool to click on links that might contain the desired information on the current web page.

Note: This tool only supports opening one URL at a time. The previous URL will be closed when you open a new one.
    """
    chain_of_thought: str = Field(
        ..., description="Think step-by-step about where you need to navigate next to find the necessary information.",
        exclude=True
    )
    url: str = Field(
        ..., description="URL of the webpage.", examples=["https://google.com/search?q=search"]
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        wd = get_web_driver()

        wd.get(self.url)

        time.sleep(2)

        set_web_driver(wd)

        self._shared_state.set("elements_highlighted", "")

        return "Current URL is: " + wd.current_url + "\n" + "Please output '[send screenshot]' next to analyze the current web page or '[highlight clickable elements]' for further navigation."


if __name__ == "__main__":
    tool = ReadURL(url="https://google.com")
    print(tool.run())

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\Scroll.py
================================================
from typing import Literal

from pydantic import Field

from agency_swarm.tools import BaseTool
from .util.selenium import get_web_driver, set_web_driver


class Scroll(BaseTool):
    """
    This tool allows you to scroll the current web page up or down by 1 screen height.
    """
    direction: Literal["up", "down"] = Field(
        ..., description="Direction to scroll."
    )

    def run(self):
        wd = get_web_driver()

        height = wd.get_window_size()['height']

        # Get the zoom level
        zoom_level = wd.execute_script("return document.body.style.zoom || '1';")
        zoom_level = float(zoom_level.strip('%')) / 100 if '%' in zoom_level else float(zoom_level)

        # Adjust height by zoom level
        adjusted_height = height / zoom_level

        current_scroll_position = wd.execute_script("return window.pageYOffset;")
        total_scroll_height = wd.execute_script("return document.body.scrollHeight;")

        result = ""

        if self.direction == "up":
            if current_scroll_position == 0:
                # Reached the top of the page
                result = "Reached the top of the page. Cannot scroll up any further.\n"
            else:
                wd.execute_script(f"window.scrollBy(0, -{adjusted_height});")
                result = "Scrolled up by 1 screen height. Make sure to output '[send screenshot]' command to analyze the page after scrolling."

        elif self.direction == "down":
            if current_scroll_position + adjusted_height >= total_scroll_height:
                # Reached the bottom of the page
                result = "Reached the bottom of the page. Cannot scroll down any further.\n"
            else:
                wd.execute_script(f"window.scrollBy(0, {adjusted_height});")
                result = "Scrolled down by 1 screen height. Make sure to output '[send screenshot]' command to analyze the page after scrolling."

        set_web_driver(wd)

        return result



================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\SelectDropdown.py
================================================
from typing import Dict
from pydantic import Field, model_validator
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from agency_swarm.tools import BaseTool
from .util import get_web_driver, set_web_driver
from .util.highlights import remove_highlight_and_labels


class SelectDropdown(BaseTool):
    """
    This tool selects an option in a dropdown on the current web page based on the description of that element and which option to select.

    Before using this tool make sure to highlight dropdown elements on the page by outputting '[highlight dropdowns]' message.
    """

    key_value_pairs: Dict[str, str] = Field(...,
        description="A dictionary where the key is the sequence number of the dropdown element and the value is the index of the option to select.",
        examples=[{"1": 0, "2": 1}, {"3": 2}]
    )

    @model_validator(mode='before')
    @classmethod
    def check_key_value_pairs(cls, data):
        if not data.get('key_value_pairs'):
            raise ValueError(
                "key_value_pairs is required. Example format: "
                "key_value_pairs={'1': 0, '2': 1}"
            )
        return data

    def run(self):
        wd = get_web_driver()

        if 'select' not in self._shared_state.get("elements_highlighted", ""):
            raise ValueError("Please highlight dropdown elements on the page first by outputting '[highlight dropdowns]' message. You must output just the message without calling the tool first, so the user can respond with the screenshot.")

        all_elements = wd.find_elements(By.CSS_SELECTOR, '.highlighted-element')

        try:
            for key, value in self.key_value_pairs.items():
                key = int(key)
                element = all_elements[key - 1]

                select = Select(element)

                # Select the first option (index 0)
                select.select_by_index(int(value))
            result = f"Success. Option is selected in the dropdown. To further analyze the page, output '[send screenshot]' command."
        except Exception as e:
            result = str(e)

        remove_highlight_and_labels(wd)

        set_web_driver(wd)

        return result


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\SendKeys.py
================================================
import time
from typing import Dict

from pydantic import Field
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By

from agency_swarm.tools import BaseTool
from .util import get_web_driver, set_web_driver
from .util.highlights import remove_highlight_and_labels


from pydantic import model_validator

class SendKeys(BaseTool):
    """
    This tool sends keys into input fields on the current webpage based on the description of that element and what needs to be typed. It then clicks "Enter" on the last element to submit the form. You do not need to tell it to press "Enter"; it will do that automatically.

    Before using this tool make sure to highlight the input elements on the page by outputting '[highlight text fields]' message.
    """
    elements_and_texts: Dict[int, str] = Field(...,
        description="A dictionary where the key is the element number and the value is the text to be typed.",
        examples=[
            {52: "johndoe@gmail.com", 53: "password123"},
            {3: "John Doe", 4: "123 Main St"},
        ]
    )

    @model_validator(mode='before')  
    @classmethod
    def check_elements_and_texts(cls, data):
        if not data.get('elements_and_texts'):
            raise ValueError(
                "elements_and_texts is required. Example format: "
                "elements_and_texts={1: 'John Doe', 2: '123 Main St'}"
            )
        return data

    def run(self):
        wd = get_web_driver()
        if 'input' not in self._shared_state.get("elements_highlighted", ""):
            raise ValueError("Please highlight input elements on the page first by outputting '[highlight text fields]' message. You must output just the message without calling the tool first, so the user can respond with the screenshot.")

        all_elements = wd.find_elements(By.CSS_SELECTOR, '.highlighted-element')

        i = 0
        try:
            for key, value in self.elements_and_texts.items():
                key = int(key)
                element = all_elements[key - 1]

                try:
                    element.click()
                    element.send_keys(Keys.CONTROL + "a")  # Select all text in input
                    element.send_keys(Keys.DELETE)
                    element.clear()
                except Exception as e:
                    pass
                element.send_keys(value)
                # send enter key to the last element
                if i == len(self.elements_and_texts) - 1:
                    element.send_keys(Keys.RETURN)
                    time.sleep(3)
                i += 1
            result = f"Sent input to element and pressed Enter. Current URL is {wd.current_url} To further analyze the page, output '[send screenshot]' command."
        except Exception as e:
            result = str(e)

        remove_highlight_and_labels(wd)

        set_web_driver(wd)

        return result


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\SolveCaptcha.py
================================================
import base64
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import presence_of_element_located, \
    frame_to_be_available_and_switch_to_it
from selenium.webdriver.support.wait import WebDriverWait

from agency_swarm.tools import BaseTool
from .util import get_b64_screenshot, remove_highlight_and_labels
from .util.selenium import get_web_driver
from agency_swarm.util import get_openai_client


class SolveCaptcha(BaseTool):
    """
    This tool asks a human to solve captcha on the current webpage. Make sure that captcha is visible before running it.
    """

    def run(self):
        wd = get_web_driver()

        try:
            WebDriverWait(wd, 10).until(
                frame_to_be_available_and_switch_to_it((By.XPATH, "//iframe[@title='reCAPTCHA']"))
            )

            element = WebDriverWait(wd, 3).until(
                presence_of_element_located((By.ID, "recaptcha-anchor"))
            )
        except Exception as e:
            return "Could not find captcha checkbox"

        try:
            # Scroll the element into view
            wd.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(1)  # Give some time for the scrolling to complete

            # Click the element using JavaScript
            wd.execute_script("arguments[0].click();", element)
        except Exception as e:
            return f"Could not click captcha checkbox: {str(e)}"

        try:
            # Now check if the reCAPTCHA is checked
            WebDriverWait(wd, 3).until(
                lambda d: d.find_element(By.CLASS_NAME, "recaptcha-checkbox").get_attribute(
                    "aria-checked") == "true"
            )

            return "Success"
        except Exception as e:
            pass

        wd.switch_to.default_content()

        client = get_openai_client()

        WebDriverWait(wd, 10).until(
            frame_to_be_available_and_switch_to_it(
                (By.XPATH, "//iframe[@title='recaptcha challenge expires in two minutes']"))
        )

        time.sleep(2)

        attempts = 0
        while attempts < 5:
            tiles = wd.find_elements(By.CLASS_NAME, "rc-imageselect-tile")

            # filter out tiles with rc-imageselect-dynamic-selected class
            tiles = [tile for tile in tiles if
                     not tile.get_attribute("class").endswith("rc-imageselect-dynamic-selected")]

            image_content = []
            i = 0
            for tile in tiles:
                i += 1
                screenshot = get_b64_screenshot(wd, tile)

                image_content.append(
                    {
                        "type": "text",
                        "text": f"Image {i}:",
                    }
                )
                image_content.append(
                    {
                        "type": "image_url",
                        "image_url":
                            {
                                "url": f"data:image/jpeg;base64,{screenshot}",
                                "detail": "high",
                            }
                    },
                )
            # highlight all titles with rc-imageselect-tile class but not with rc-imageselect-dynamic-selected
            # wd = highlight_elements_with_labels(wd, 'td.rc-imageselect-tile:not(.rc-imageselect-dynamic-selected)')

            # screenshot = get_b64_screenshot(wd, wd.find_element(By.ID, "rc-imageselect"))

            task_text = wd.find_element(By.CLASS_NAME, "rc-imageselect-instructions").text.strip().replace("\n",
                                                                                                           " ")

            continuous_task = 'once there are none left' in task_text.lower()

            task_text = task_text.replace("Click verify", "Output 0")
            task_text = task_text.replace("click skip", "Output 0")
            task_text = task_text.replace("once", "if")
            task_text = task_text.replace("none left", "none")
            task_text = task_text.replace("all", "only")
            task_text = task_text.replace("squares", "images")

            additional_info = ""
            if len(tiles) > 9:
                additional_info = ("Keep in mind that all images are a part of a bigger image "
                                   "from left to right, and top to bottom. The grid is 4x4. ")

            messages = [
                {
                    "role": "system",
                    "content": f"""You are an advanced AI designed to support users with visual impairments. 
                    User will provide you with {i} images numbered from 1 to {i}. Your task is to output 
                    the numbers of the images that contain the requested object, or at least some part of the requested 
                    object. {additional_info}If there are no individual images that satisfy this condition, output 0.
                    """.replace("\n", ""),
                },
                {
                    "role": "user",
                    "content": [
                        *image_content,
                        {
                            "type": "text",
                            "text": f"{task_text}. Only output numbers separated by commas and nothing else. "
                                    f"Output 0 if there are none."
                        }
                    ]
                }]

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1024,
                temperature=0.0,
            )

            message = response.choices[0].message
            message_text = message.content

            # check if 0 is in the message
            if "0" in message_text and "10" not in message_text:
                # Find the button by its ID
                verify_button = wd.find_element(By.ID, "recaptcha-verify-button")

                verify_button_text = verify_button.text

                # Click the button
                wd.execute_script("arguments[0].click();", verify_button)

                time.sleep(1)

                try:
                    if self.verify_checkbox(wd):
                        return "Success. Captcha solved."
                except Exception as e:
                    print('Not checked')
                    pass

            else:
                numbers = [int(s.strip()) for s in message_text.split(",") if s.strip().isdigit()]

                # Click the tiles based on the provided numbers
                for number in numbers:
                    wd.execute_script("arguments[0].click();", tiles[number - 1])
                    time.sleep(0.5)

                time.sleep(3)

                if not continuous_task:
                    # Find the button by its ID
                    verify_button = wd.find_element(By.ID, "recaptcha-verify-button")

                    verify_button_text = verify_button.text

                    # Click the button
                    wd.execute_script("arguments[0].click();", verify_button)

                    try:
                        if self.verify_checkbox(wd):
                            return "Success. Captcha solved."
                    except Exception as e:
                        pass
                else:
                    continue

            if "verify" in verify_button_text.lower():
                attempts += 1

        wd = remove_highlight_and_labels(wd)

        wd.switch_to.default_content()

        # close captcha
        try:
            element = WebDriverWait(wd, 3).until(
                presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']"))
            )

            wd.execute_script(f"document.elementFromPoint({element.location['x']}, {element.location['y']-10}).click();")
        except Exception as e:
            print(e)
            pass

        return "Could not solve captcha."

    def verify_checkbox(self, wd):
        wd.switch_to.default_content()

        try:
            WebDriverWait(wd, 10).until(
                frame_to_be_available_and_switch_to_it((By.XPATH, "//iframe[@title='reCAPTCHA']"))
            )

            WebDriverWait(wd, 5).until(
                lambda d: d.find_element(By.CLASS_NAME, "recaptcha-checkbox").get_attribute(
                    "aria-checked") == "true"
            )

            return True
        except Exception as e:
            wd.switch_to.default_content()

            WebDriverWait(wd, 10).until(
                frame_to_be_available_and_switch_to_it(
                    (By.XPATH, "//iframe[@title='recaptcha challenge expires in two minutes']"))
            )

        return False



================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\util\get_b64_screenshot.py
================================================

def get_b64_screenshot(wd, element=None):
    if element:
        screenshot_b64 = element.screenshot_as_base64
    else:
        screenshot_b64 = wd.get_screenshot_as_base64()

    return screenshot_b64

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\util\highlights.py
================================================
def highlight_elements_with_labels(driver, selector):
    """
    This function highlights clickable elements like buttons, links, and certain divs and spans
    that match the given CSS selector on the webpage with a red border and ensures that labels are visible and positioned
    correctly within the viewport.

    :param driver: Instance of Selenium WebDriver.
    :param selector: CSS selector for the elements to be highlighted.
    """
    script = f"""
        // Helper function to check if an element is visible
        function isElementVisible(element) {{
            var rect = element.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0 || 
                rect.top >= (window.innerHeight || document.documentElement.clientHeight) || 
                rect.bottom <= 0 || 
                rect.left >= (window.innerWidth || document.documentElement.clientWidth) || 
                rect.right <= 0) {{
                return false;
            }}
            // Check if any parent element is hidden, which would hide this element as well
            var parent = element;
            while (parent) {{
                var style = window.getComputedStyle(parent);
                if (style.display === 'none' || style.visibility === 'hidden') {{
                    return false;
                }}
                parent = parent.parentElement;
            }}
            return true;
        }}

        // Remove previous labels and styles if they exist
        document.querySelectorAll('.highlight-label').forEach(function(label) {{
            label.remove();
        }});
        document.querySelectorAll('.highlighted-element').forEach(function(element) {{
            element.classList.remove('highlighted-element');
            element.removeAttribute('data-highlighted');
        }});

        // Inject custom style for highlighting elements
        var styleElement = document.getElementById('highlight-style');
        if (!styleElement) {{
            styleElement = document.createElement('style');
            styleElement.id = 'highlight-style';
            document.head.appendChild(styleElement);
        }}
        styleElement.textContent = `
            .highlighted-element {{ 
                border: 2px solid red !important; 
                position: relative; 
                box-sizing: border-box; 
            }}
            .highlight-label {{ 
                position: absolute; 
                z-index: 2147483647; 
                background: yellow; 
                color: black; 
                font-size: 25px; 
                padding: 3px 5px; 
                border: 1px solid black; 
                border-radius: 3px; 
                white-space: nowrap; 
                box-shadow: 0px 0px 2px #000; 
                top: -25px; 
                left: 0; 
                display: none;
            }}
        `;

        // Function to create and append a label to the body
        function createAndAdjustLabel(element, index) {{
            if (!isElementVisible(element)) return;

            element.classList.add('highlighted-element');
            var label = document.createElement('div');
            label.className = 'highlight-label';
            label.textContent = index.toString();
            label.style.display = 'block'; // Make the label visible

            // Calculate label position
            var rect = element.getBoundingClientRect();
            var top = rect.top + window.scrollY - 25; // Position label above the element
            var left = rect.left + window.scrollX;

            label.style.top = top + 'px';
            label.style.left = left + 'px';

            document.body.appendChild(label); // Append the label to the body
        }}

        // Select all clickable elements and apply the styles
        var allElements = document.querySelectorAll('{selector}');
        var index = 1;
        allElements.forEach(function(element) {{
            // Check if the element is not already highlighted and is visible
            if (!element.dataset.highlighted && isElementVisible(element)) {{
                element.dataset.highlighted = 'true';
                createAndAdjustLabel(element, index++);
            }}
        }});
        """

    driver.execute_script(script)

    return driver


def remove_highlight_and_labels(driver):
    """
    This function removes all red borders and labels from the webpage elements,
    reversing the changes made by the highlight functions using Selenium WebDriver.

    :param driver: Instance of Selenium WebDriver.
    """
    selector = ('a, button, input, textarea, div[onclick], div[role="button"], div[tabindex], span[onclick], '
                'span[role="button"], span[tabindex]')
    script = f"""
        // Remove all labels
        document.querySelectorAll('.highlight-label').forEach(function(label) {{
            label.remove();
        }});

        // Remove the added style for red borders
        var highlightStyle = document.getElementById('highlight-style');
        if (highlightStyle) {{
            highlightStyle.remove();
        }}

        // Remove inline styles added by highlighting function
        document.querySelectorAll('{selector}').forEach(function(element) {{
            element.style.border = '';
        }});
        """

    driver.execute_script(script)

    return driver

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\util\selenium.py
================================================
import os

wd = None

selenium_config = {
    "chrome_profile_path": None,
    "headless": True,
    "full_page_screenshot": True,
}


def get_web_driver():
    print("Initializing WebDriver...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        print("Selenium imported successfully.")
    except ImportError:
        print("Selenium not installed. Please install it with pip install selenium")
        raise ImportError

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        print("webdriver_manager imported successfully.")
    except ImportError:
        print("webdriver_manager not installed. Please install it with pip install webdriver-manager")
        raise ImportError

    try:
        from selenium_stealth import stealth
        print("selenium_stealth imported successfully.")
    except ImportError:
        print("selenium_stealth not installed. Please install it with pip install selenium-stealth")
        raise ImportError

    global wd, selenium_config

    if wd:
        print("Returning existing WebDriver instance.")
        return wd

    chrome_profile_path = selenium_config.get("chrome_profile_path", None)
    profile_directory = None
    user_data_dir = None
    if isinstance(chrome_profile_path, str) and os.path.exists(chrome_profile_path):
        profile_directory = os.path.split(chrome_profile_path)[-1].strip("\\").rstrip("/")
        user_data_dir = os.path.split(chrome_profile_path)[0].strip("\\").rstrip("/")
        print(f"Using Chrome profile: {profile_directory}")
        print(f"Using Chrome user data dir: {user_data_dir}")
        print(f"Using Chrome profile path: {chrome_profile_path}")

    chrome_options = webdriver.ChromeOptions()
    print("ChromeOptions initialized.")

    chrome_driver_path = "/usr/bin/chromedriver"
    if not os.path.exists(chrome_driver_path):
        print("ChromeDriver not found at /usr/bin/chromedriver. Installing using webdriver_manager.")
        chrome_driver_path = ChromeDriverManager().install()
    else:
        print(f"ChromeDriver found at {chrome_driver_path}.")

    if selenium_config.get("headless", False):
        chrome_options.add_argument('--headless')
        print("Headless mode enabled.")
    if selenium_config.get("full_page_screenshot", False):
        chrome_options.add_argument("--start-maximized")
        print("Full page screenshot mode enabled.")
    else:
        chrome_options.add_argument("--window-size=1920,1080")
        print("Window size set to 1920,1080.")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    print("Chrome options configured.")

    if user_data_dir and profile_directory:
        chrome_options.add_argument(f"user-data-dir={user_data_dir}")
        chrome_options.add_argument(f"profile-directory={profile_directory}")
        print(f"Using user data dir: {user_data_dir} and profile directory: {profile_directory}")

    try:
        wd = webdriver.Chrome(service=ChromeService(chrome_driver_path), options=chrome_options)
        print("WebDriver initialized successfully.")
        if wd.capabilities['chrome']['userDataDir']:
            print(f"Profile path in use: {wd.capabilities['chrome']['userDataDir']}")
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        raise e

    if not selenium_config.get("chrome_profile_path", None):
        stealth(
            wd,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        print("Stealth mode configured.")

    wd.implicitly_wait(3)
    print("Implicit wait set to 3 seconds.")

    return wd


def set_web_driver(new_wd):
    # remove all popups
    js_script = """
    var popUpSelectors = ['modal', 'popup', 'overlay', 'dialog']; // Add more selectors that are commonly used for pop-ups
    popUpSelectors.forEach(function(selector) {
        var elements = document.querySelectorAll(selector);
        elements.forEach(function(element) {
            // You can choose to hide or remove; here we're removing the element
            element.parentNode.removeChild(element);
        });
    });
    """

    new_wd.execute_script(js_script)

    # Close LinkedIn specific popups
    if "linkedin.com" in new_wd.current_url:
        linkedin_js_script = """
        var linkedinSelectors = ['div.msg-overlay-list-bubble', 'div.ml4.msg-overlay-list-bubble__tablet-height'];
        linkedinSelectors.forEach(function(selector) {
            var elements = document.querySelectorAll(selector);
            elements.forEach(function(element) {
                element.parentNode.removeChild(element);
            });
        });
        """
        new_wd.execute_script(linkedin_js_script)

    new_wd.execute_script("document.body.style.zoom='1.2'")

    global wd
    wd = new_wd


def set_selenium_config(config):
    global selenium_config
    selenium_config = config


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\util\__init__.py
================================================
from .get_b64_screenshot import get_b64_screenshot
from .selenium import get_web_driver, set_web_driver
from .highlights import remove_highlight_and_labels, highlight_elements_with_labels


================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\WebPageSummarizer.py
================================================
from selenium.webdriver.common.by import By

from agency_swarm.tools import BaseTool
from .util import get_web_driver, set_web_driver


class WebPageSummarizer(BaseTool):
    """
    This tool summarizes the content of the current web page, extracting the main points and providing a concise summary.
    """

    def run(self):
        from agency_swarm import get_openai_client

        wd = get_web_driver()
        client = get_openai_client()

        content = wd.find_element(By.TAG_NAME, "body").text

        # only use the first 10000 characters
        content = " ".join(content.split()[:10000])

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Your task is to summarize the content of the provided webpage. The summary should be concise and informative, capturing the main points and takeaways of the page."},
                {"role": "user", "content": "Summarize the content of the following webpage:\n\n" + content},
            ],
            temperature=0.0,
        )

        return completion.choices[0].message.content

if __name__ == "__main__":
    wd = get_web_driver()
    wd.get("https://en.wikipedia.org/wiki/Python_(programming_language)")
    set_web_driver(wd)
    tool = WebPageSummarizer()
    print(tool.run())

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\tools\__init__.py
================================================
from .Scroll import Scroll
from .ReadURL import ReadURL
from .SendKeys import SendKeys
from .ClickElement import ClickElement
from .GoBack import GoBack
from .SelectDropdown import SelectDropdown
from .SolveCaptcha import SolveCaptcha
from .ExportFile import ExportFile
from .WebPageSummarizer import WebPageSummarizer

================================================
File: /agency-swarm-main\agency_swarm\agents\BrowsingAgent\__init__.py
================================================
from .BrowsingAgent import BrowsingAgent

================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\Devid.py
================================================
from typing_extensions import override
import re
from agency_swarm.agents import Agent
from agency_swarm.tools import FileSearch
from agency_swarm.util.validators import llm_validator


class Devid(Agent):
    def __init__(self):
        super().__init__(
            name="Devid",
            description="Devid is an AI software engineer capable of performing advanced coding tasks.",
            instructions="./instructions.md",
            files_folder="./files",
            schemas_folder="./schemas",
            tools=[FileSearch],
            tools_folder="./tools",
            validation_attempts=1,
            temperature=0,
            max_prompt_tokens=25000,
        )

    @override
    def response_validator(self, message):
        pattern = r'(```)((.*\n){5,})(```)'

        if re.search(pattern, message):
            # take only first 100 characters
            raise ValueError(
                "You returned code snippet. Please never return code snippets to me. "
                "Use the FileWriter tool to write the code locally. Then, test it if possible. Continue."
            )

        llm_validator(statement="Verify whether the update from the AI Developer Agent confirms the task's "
                                "successful completion. If the task remains unfinished, provide guidance "
                                "within the 'reason' argument on the next steps the agent should take. For "
                                "instance, if the agent encountered an error, advise the inclusion of debug "
                                "statements for another attempt. Should the agent outline potential "
                                "solutions or further actions, direct the agent to execute those plans. "
                                "Message does not have to contain code snippets. Just confirmation.",
                      client=self.client)(message)

        return message


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\instructions.md
================================================
# Devid Operational Guide

As an AI software developer known as Devid, your role involves reading, writing, and modifying files to fulfill tasks derived from user requests. 

**Operational Environment**:
- You have direct access to the internet, system executions, or environment variables. 
- Interaction with the local file system to read, write, and modify files is permitted.
- Python is installed in your environment, enabling the execution of Python scripts and code snippets.
- Node.js and npm are also installed, allowing for the execution of Node.js scripts and code snippets.
- Installation of additional third-party libraries is within your capabilities.
- Execution of commands in the terminal to compile and run code is possible.

## Primary Instructions:

1. Begin by fully understanding the task at hand. Use the `myfiles_browser` tool to access and review any files uploaded by the user. If initial access to files fails, retry the operation until successful. Continue browsing the files until you have gathered sufficient information to proceed. Skip this step if no files were provided.
2. Verify your current directory's path and contents with `ListDir` and `CheckCurrentDir`. If necessary, navigate to the correct directory using the `DirectoryNavigator` tool or create a new directory for the task.
3. Utilize the `FileWriter` for creating or modifying files. To read a file, employ the `FileReader` tool. Always modify local files when executing tasks and avoid sending code snippets to the user. Work on one file at a time and refrain from creating or modifying multiple files simultaneously. Complete each file with `FileWriter` before proceeding to the next, integrating these files into the dependencies of the main file.
4. Execute your written code with the `CommandExecutor` by running the appropriate terminal commands. Iteratively debug and test to achieve the desired outcome. Seek clarification from the user only after all internal resolution efforts have been exhausted. To install additional libraries, execute the necessary terminal commands.
5. Repeat the above steps for each task.

**Important Note**: Your capabilities include accessing and interacting with local files, online resources, and the terminal. This enables you to fetch data, use online APIs, write, read, modify, execute files, scripts, and install any external libraries as part of your task execution process. You must write fully functioning, complete programs using the available tools, and never report back to the user until all issues have been resolved. Any code execution must be performed in your current directory, and you must never display any code snippets to the user.

================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\ChangeFile.py
================================================
import os
from enum import Enum
from typing import Literal, Optional, List

from pydantic import Field, model_validator, field_validator, BaseModel

from agency_swarm import BaseTool

class LineChange(BaseModel):
    """
    Line changes to be made.
    """
    line_number: int = Field(
        ..., description="Line number to change.",
        examples=[1, 2, 3]
    )
    new_line: Optional[str] = Field(
        None, description="New line to replace the old line. Not required only for delete mode.",
        examples=["This is a new line"]
    )
    mode: Literal["replace", "insert", "delete"] = Field(
        "replace", description='Mode to use for the line change. "replace" replaces the line with the new line. '
                               '"insert" inserts the new line at the specified line number, moving the previous line down.'
                               ' "delete" deletes the specified line number.',
    )

    @model_validator(mode='after')
    def validate_new_line(self):
        mode, new_line = self.mode, self.new_line
        if mode == "delete" and new_line is not None:
            raise ValueError("new_line should not be specified for delete mode.")
        elif mode in ["replace", "insert"] and new_line is None:
            raise ValueError("new_line should be specified for replace and insert modes.")
        return self


class ChangeFile(BaseTool):
    """
    This tool changes specified lines in a file. Returns the new file contents with line numbers at the start of each line.
    """
    chain_of_thought: str = Field(
        ..., description="Please think step-by-step about the required changes to the file in order to construct a fully functioning and correct program according to the requirements.",
        exclude=True,
    )
    file_path: str = Field(
        ..., description="Path to the file with extension.",
        examples=["./file.txt", "./file.json", "../../file.py"]
    )
    changes: List[LineChange] = Field(
        ..., description="Line changes to be made to the file.",
        examples=[{"line_number": 1, "new_line": "This is a new line", "mode": "replace"}]
    )

    def run(self):
        # read file
        with open(self.file_path, "r") as f:
            file_contents = f.readlines()

            # Process changes in a way that accounts for modifications affecting line numbers
            for change in sorted(self.changes, key=lambda x: x.line_number, reverse=True):
                try:
                    if change.mode == "replace" and 0 < change.line_number <= len(file_contents):
                        file_contents[change.line_number - 1] = change.new_line + '\n'
                    elif change.mode == "insert":
                        file_contents.insert(change.line_number - 1, change.new_line + '\n')
                    elif change.mode == "delete" and 0 < change.line_number <= len(file_contents):
                        file_contents.pop(change.line_number - 1)
                except IndexError:
                    return f"Error: Line number {change.line_number} is out of the file's range."

        # write file
        with open(self.file_path, "w") as f:
            f.writelines(file_contents)

        with open(self.file_path, "r") as f:
            file_contents = f.readlines()

        # return file contents with line numbers
        return "\n".join([f"{i + 1}. {line}" for i, line in enumerate(file_contents)])

    # use field validation to ensure that the file path is valid
    @field_validator("file_path", mode='after')
    @classmethod
    def validate_file_path(cls, v: str):
        if not os.path.exists(v):
            raise ValueError("File path does not exist.")

        return v

================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\CheckCurrentDir.py
================================================
from pydantic import Field

from agency_swarm import BaseTool


class CheckCurrentDir(BaseTool):
    """
    This tool checks the current directory path.
    """
    chain_of_thought: str = Field(
        ...,
        description="Please think step-by-step about what you need to do next, after checking current directory to solve the task.",
        exclude=True,
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        import os

        return os.getcwd()


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\CommandExecutor.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field
import subprocess
import shlex
from dotenv import load_dotenv, find_dotenv

class CommandExecutor(BaseTool):
    """
    Executes a specified command in the terminal and captures the output.

    This tool runs a given command in the system's default shell and returns the stdout and stderr.
    """

    command: str = Field(
        ..., description="The command to execute in the terminal."
    )

    def run(self):
        """
        Executes the command and captures its output.

        Returns:
            A dictionary containing the standard output (stdout), standard error (stderr),
            and the exit code of the command.
        """
        load_dotenv(find_dotenv() or None)
        # Ensure the command is safely split for subprocess
        command_parts = shlex.split(self.command)

        # Execute the command and capture the output
        result = subprocess.run(command_parts, capture_output=True, text=True)

        # check if the command failed
        if result.returncode != 0 or result.stderr:
            return (f"stdout: {result.stdout}\nstderr: {result.stderr}\nexit code: {result.returncode}\n\n"
                    f"Please add error handling and continue debugging until the command runs successfully.")

        return f"stdout: {result.stdout}\nstderr: {result.stderr}\nexit code: {result.returncode}"

if __name__ == "__main__":
    tool = CommandExecutor(command="ls -l")
    print(tool.run())


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\DirectoryNavigator.py
================================================
import os
from pydantic import Field, model_validator, field_validator

from agency_swarm.tools import BaseTool


class DirectoryNavigator(BaseTool):
    """Allows you to navigate directories. Do not use this tool more than once at a time.
    You must finish all tasks in the current directory before navigating into new directory."""
    path: str = Field(
        ..., description="The path of the directory to navigate to."
    )
    create: bool = Field(
        False, description="If True, the directory will be created if it does not exist."
    )

    class ToolConfig:
        one_call_at_a_time: bool = True

    def run(self):
        try:
            os.chdir(self.path)
            return f'Successfully changed directory to: {self.path}'
        except Exception as e:
            return f'Error changing directory: {e}'

    @field_validator("create", mode="before")
    @classmethod
    def validate_create(cls, v):
        if not isinstance(v, bool):
            if v.lower() == "true":
                return True
            elif v.lower() == "false":
                return False
        return v

    @model_validator(mode='after')
    def validate_path(self):
        if not os.path.isdir(self.path):
            if "/mnt/data" in self.path:
                raise ValueError("You tried to access an openai file directory with a local directory reader tool. " +
                                 "Please use the `myfiles_browser` tool to access openai files instead. " +
                                 "Your local files are most likely located in your current directory.")

            if self.create:
                os.makedirs(self.path)
            else:
                raise ValueError(f"The path {self.path} does not exist. Please provide a valid directory path. " +
                                 "If you want to create the directory, set the `create` parameter to True.")

        return self


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\FileMover.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field
import shutil
import os

class FileMover(BaseTool):
    """
    FileMover is a tool designed to move files from a source path to a destination path. If the destination directory does not exist, it will be created.
    """

    source_path: str = Field(
        ..., description="The full path of the file to move, including the file name and extension."
    )
    destination_path: str = Field(
        ..., description="The destination path where the file should be moved, including the new file name and extension if changing."
    )

    def run(self):
        """
        Executes the file moving operation from the source path to the destination path.
        It checks if the destination directory exists and creates it if necessary, then moves the file.
        """
        if not os.path.exists(self.source_path):
            return f"Source file does not exist at {self.source_path}"

        # Ensure the destination directory exists
        destination_dir = os.path.dirname(self.destination_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)

        # Move the file
        shutil.move(self.source_path, self.destination_path)

        return f"File moved successfully from {self.source_path} to {self.destination_path}"


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\FileReader.py
================================================
from agency_swarm.tools import BaseTool
from pydantic import Field, field_validator


class FileReader(BaseTool):
    """This tool reads a file and returns the contents along with line numbers on the left."""
    file_path: str = Field(
        ..., description="Path to the file to read with extension.",
        examples=["./file.txt", "./file.json", "../../file.py"]
    )

    def run(self):
        # read file
        with open(self.file_path, "r") as f:
            file_contents = f.readlines()

        # return file contents
        return "\n".join([f"{i + 1}. {line}" for i, line in enumerate(file_contents)])

    @field_validator("file_path", mode="after")
    @classmethod
    def validate_file_path(cls, v):
        if "file-" in v:
            raise ValueError("You tried to access an openai file with a wrong file reader tool. "
                             "Please use the `myfiles_browser` tool to access openai files instead."
                             "This tool is only for reading local files.")
        return v


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\FileWriter.py
================================================
from typing import List, Literal, Optional

import json

import os
from agency_swarm.util.validators import llm_validator

from agency_swarm import get_openai_client
from agency_swarm.tools import BaseTool
from pydantic import Field, field_validator
import re

from .util import format_file_deps

history = [
            {
                "role": "system",
                "content": "As a top-tier software engineer focused on developing programs incrementally, you are entrusted with the creation or modification of files based on user requirements. It's imperative to operate under the assumption that all necessary dependencies are pre-installed and accessible, and the file in question will be deployed in an appropriate environment. Furthermore, it is presumed that all other modules or files upon which this file relies are accurate and error-free. Your output should be encapsulated within a code block, without specifying the programming language. Prior to embarking on the coding process, you must outline a methodical, step-by-step plan to precisely fulfill the requirements — no more, no less. It is crucial to ensure that the final code block is a complete file, without any truncation. This file should embody a flawless, fully operational program, inclusive of all requisite imports and functions, devoid of any placeholders, unless specified otherwise by the user."
            },
        ]


class FileWriter(BaseTool):
    """This tools allows you to write new files or modify existing files according to specified requirements. In 'write' mode, it creates a new file or overwrites an existing one. In 'modify' mode, it modifies an existing file according to the provided requirements.
    Note: This tool does not have access to other files within the project. You must provide all necessary details to ensure that the generated file can be used in conjunction with other files in this project."""
    file_path: str = Field(
        ..., description="The path of the file to write or modify. Will create directories if they don't exist."
    )
    requirements: str = Field(
        ...,
        description="The comprehensive requirements explaining how the file should be written or modified. This should be a detailed description of what the file should contain, including example inputs, desired behaviour and ideal outputs. It must not contain any code or implementation details."
    )
    details: str = Field(
        None, description="Additional details like error messages, or class, function, and variable names from other files that this file depends on."
    )
    documentation: Optional[str] = Field(
        None, description="Relevant documentation extracted with the myfiles_browser tool. You must pass all the relevant code from the documentation, as this tool does not have access to those files."
    )
    mode: Literal["write", "modify"] = Field(
        ..., description="The mode of operation for the tool. 'write' is used to create a new file or overwrite an existing one. 'modify' is used to modify an existing file."
    )
    file_dependencies: List[str] = Field(
        [],
        description="Paths to other files that the file being written depends on.",
        examples=["/path/to/dependency1.py", "/path/to/dependency2.css", "/path/to/dependency3.js"]
        )
    library_dependencies: List[str] = Field(
        [],
        description="Any library dependencies required for the file to be written.",
        examples=["numpy", "pandas"]
    )
    
    class ToolConfig:
        one_call_at_a_time = True

    def run(self):
        client = get_openai_client()

        file_dependencies = format_file_deps(self.file_dependencies)

        library_dependencies = ", ".join(self.library_dependencies)

        filename = os.path.basename(self.file_path)

        if self.mode == "write":
            message = f"Please write {filename} file that meets the following requirements: '{self.requirements}'.\n"
        else:
            message = f"Please rewrite the {filename} file according to the following requirements: '{self.requirements}'.\n Only output the file content, without any other text."

        if file_dependencies:
            message += f"\nHere are the dependencies from other project files: {file_dependencies}."
        if library_dependencies:
            message += f"\nUse the following libraries: {library_dependencies}"
        if self.details:
            message += f"\nAdditional Details: {self.details}"
        if self.documentation:
            message += f"\nDocumentation: {self.documentation}"

        if self.mode == "modify":
            message += f"\nThe existing file content is as follows:"
        
            try:
                with open(self.file_path, 'r') as file:
                    file_content = file.read()
                    message += f"\n\n```{file_content}```"
            except Exception as e:
                return f'Error reading {self.file_path}: {e}'

        history.append({
                "role": "user",
                "content": message
            })

        messages = history.copy()

        # use the last 5 messages
        messages = messages[-5:]

        # add system message upfront
        messages.insert(0, history[0])

        n = 0
        error_message = ""
        while n < 3:
            if self.mode == "modify":
                resp = client.chat.completions.create(
                    messages=messages,
                    model="gpt-4o",
                    temperature=0,
                    prediction={
                        "type": "content",
                        "content": file_content
                    }
                )
            else:
                resp = client.chat.completions.create(
                    messages=messages,
                    model="gpt-4o",
                    temperature=0,
                )

            content = resp.choices[0].message.content

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            pattern = r"```(?:[a-zA-Z]+\n)?(.*?)```"
            match = re.findall(pattern, content, re.DOTALL)
            if match:
                code = match[-1].strip()
                try:
                    self.validate_content(code)

                    history.append(
                        {
                            "role": "assistant",
                            "content": content
                        }
                    )

                    break
                except Exception as e:
                    print(f"Error: {e}. Trying again.")
                    error_message = str(e)
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Error: {e}. Please try again."
                        }
                    )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: Could not find the code block in the response. Please try again."
                    }
                )

            n += 1

        if n == 3 or not code:
            history.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )
            history.append(
                {
                    "role": "user",
                    "content": error_message
                }
            )
            return "Error: Could not generate a valid file: " + error_message

        try:
            # create directories if they don't exist
            dir_path = os.path.dirname(self.file_path)
            if dir_path != "" and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            with open(self.file_path, 'w') as file:
                file.write(code)
            return f'Successfully wrote to file: {self.file_path}. Please make sure to now test the program. Below is the content of the file:\n\n```{content}```\n\nPlease now verify the integrity of the file and test it.'
        except Exception as e:
            return f'Error writing to file: {e}'

    @field_validator("file_dependencies", mode="after")
    @classmethod
    def validate_file_dependencies(cls, v):
        for file in v:
            if not os.path.exists(file):
                raise ValueError(f"File dependency '{file}' does not exist.")
        return v

    def validate_content(self, v):
        client = get_openai_client()

        llm_validator(
            statement="Check if the code is bug-free. Code should be considered in isolation, with the understanding that it is part of a larger, fully developed program that strictly adheres to these standards of completeness and correctness. All files, elements, components, functions, or modules referenced within this snippet are assumed to exist in other parts of the project and are also devoid of any errors, ensuring a cohesive and error-free integration across the entire software solution. Certain placeholders may be present.",
                      client=client,
                      model="gpt-4o",
                      temperature=0,
                      allow_override=False
                      )(v)

        return v

    @field_validator("requirements", mode="after")
    @classmethod
    def validate_requirements(cls, v):
        if "placeholder" in v:
            raise ValueError("Requirements contain placeholders. "
                             "Please never user placeholders. Instead, implement only the code that you are confident about.")

        # check if code is included in requirements
        pattern = r'(```)((.*\n){5,})(```)'
        if re.search(pattern, v):
            raise ValueError(
                "Requirements contain a code snippet. Please never include code snippets in requirements. "
                "Requirements must be a description of the complete file to be written. You can include specific class, function, and variable names, but not the actual code."
            )

        return v

    @field_validator("details", mode="after")
    @classmethod
    def validate_details(cls, v):
        if len(v) == 0:
            raise ValueError("Details are required. Remember: this tool does not have access to other files. Please provide additional details like relevant documentation, error messages, or class, function, and variable names from other files that this file depends on.")
        return v

    @field_validator("documentation", mode="after")
    @classmethod
    def validate_documentation(cls, v):
        # check if documentation contains code
        pattern = r'(```)((.*\n){5,})(```)'
        pattern2 = r'(`)(.*)(`)'
        if not (re.search(pattern, v) or re.search(pattern2, v)):
            raise ValueError(
                "Documentation does not contain a code snippet. Please provide relevant documentation extracted with the myfiles_browser tool. You must pass all the relevant code snippets information, as this tool does not have access to those files."
            )


if __name__ == "__main__":
    # Test case for 'write' mode
    tool_write = FileWriter(
        requirements="Write a program that takes a list of integers as input and returns the sum of all the integers in the list.",
        mode="write",
        file_path="test_write.py",
    )
    print(tool_write.run())

    # Test case for 'modify' mode
    tool_modify = FileWriter(
        requirements="Modify the program to also return the product of all the integers in the list.",
        mode="modify",
        file_path="test_write.py",
    )
    print(tool_modify.run())


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\ListDir.py
================================================
from pydantic import Field, field_validator

from agency_swarm import BaseTool
import os


class ListDir(BaseTool):
    """
    This tool returns the tree structure of the directory.
    """
    dir_path: str = Field(
        ..., description="Path of the directory to read.",
        examples=["./", "./test", "../../"]
    )

    def run(self):
        tree = []

        def list_directory_tree(path, indent=''):
            """Recursively list the contents of a directory in a tree-like format."""
            if not os.path.isdir(path):
                raise ValueError(f"The path {path} is not a valid directory")

            items = os.listdir(path)
            # exclude common hidden files and directories
            exclude = ['.git', '.idea', '__pycache__', 'node_modules', '.venv', '.gitignore', '.gitkeep',
                       '.DS_Store', '.vscode', '.next', 'dist', 'build', 'out', 'venv', 'env', 'logs', 'data']

            items = [item for item in items if item not in exclude]

            for i, item in enumerate(items):
                item_path = os.path.join(path, item)
                if i < len(items) - 1:
                    tree.append(indent + '├── ' + item)
                    if os.path.isdir(item_path):
                        list_directory_tree(item_path, indent + '│   ')
                else:
                    tree.append(indent + '└── ' + item)
                    if os.path.isdir(item_path):
                        list_directory_tree(item_path, indent + '    ')

        list_directory_tree(self.dir_path)

        return "\n".join(tree)

    @field_validator("dir_path", mode='after')
    @classmethod
    def validate_dir_path(cls, v):
        if "file-" in v:
            raise ValueError("You tried to access an openai file with a local directory reader tool. "
                             "Please use the `myfiles_browser` tool to access openai directories instead.")

        if not os.path.isdir(v):
            if "/mnt/data" in v:
                raise ValueError("You tried to access an openai file directory with a local directory reader tool. "
                                 "Please use the `myfiles_browser` tool to access openai files instead. "
                                 "You can work in your local directory by using the `FileReader` tool.")

            raise ValueError(f"The path {v} is not a valid directory")
        return v


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\util\format_file_deps.py
================================================
from pydantic import Field, BaseModel
from typing import List, Literal

from agency_swarm import get_openai_client


def format_file_deps(v):
    client = get_openai_client()
    result = ''
    for file in v:
        # extract dependencies from the file using openai
        with open(file, 'r') as f:
            content = f.read()

        class Dependency(BaseModel):
            type: Literal['class', 'function', 'import'] = Field(..., description="The type of the dependency.")
            name: str = Field(..., description="The name of the dependency, matching the import or definition.")

        class Dependencies(BaseModel):
            dependencies: List[Dependency] = Field([], description="The dependencies extracted from the file.")

            def append_dependencies(self):
                functions = [dep.name for dep in self.dependencies if dep.type == 'function']
                classes = [dep.name for dep in self.dependencies if dep.type == 'class']
                imports = [dep.name for dep in self.dependencies if dep.type == 'import']
                variables = [dep.name for dep in self.dependencies if dep.type == 'variable']
                nonlocal result
                result += f"File path: {file}\n"
                result += f"Functions: {functions}\nClasses: {classes}\nImports: {imports}\nVariables: {variables}\n\n"

        completion = client.beta.chat.completions.parse(
            messages=[
                {
                    "role": "system",
                    "content": "You are a world class dependency resolved. You must extract the dependencies from the file provided."
                },
                {
                    "role": "user",
                    "content": f"Extract the dependencies from the file '{file}'."
                }
            ],
            model="gpt-4o-mini",
            temperature=0,
            response_format=Dependencies
        )

        if completion.choices[0].message.refusal:
            raise ValueError(completion.choices[0].message.refusal)

        model = completion.choices[0].message.parsed

        model.append_dependencies()

    return result

================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\util\__init__.py
================================================
from .format_file_deps import format_file_deps

================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\tools\__init__.py
================================================


================================================
File: /agency-swarm-main\agency_swarm\agents\Devid\__init__.py
================================================
from .Devid import Devid

================================================
File: /agency-swarm-main\agency_swarm\agents\__init__.py
================================================
from .agent import Agent
from .BrowsingAgent import BrowsingAgent
from .Devid import Devid

================================================
File: /agency-swarm-main\agency_swarm\cli.py
================================================
import argparse
import os
from dotenv import load_dotenv
from agency_swarm.util.helpers import list_available_agents


def main():
    parser = argparse.ArgumentParser(description='Agency Swarm CLI.')

    subparsers = parser.add_subparsers(dest='command', help='Utility commands to simplify the agent creation process.')
    subparsers.required = True

    # create-agent-template
    create_parser = subparsers.add_parser('create-agent-template', help='Create agent template folder locally.')
    create_parser.add_argument('--path', type=str, default="./", help='Path to create agent folder.')
    create_parser.add_argument('--use_txt', action='store_true', default=False,
                               help='Use txt instead of md for instructions and manifesto.')
    create_parser.add_argument('--name', type=str, help='Name of agent.')
    create_parser.add_argument('--description', type=str, help='Description of agent.')

    # genesis-agency
    genesis_parser = subparsers.add_parser('genesis', help='Start genesis agency.')
    genesis_parser.add_argument('--openai_key', default=None, type=str, help='OpenAI API key.')
    genesis_parser.add_argument('--with_browsing', default=False, action='store_true',
                                help='Enable browsing agent.')

    # import-agent
    import_parser = subparsers.add_parser('import-agent', help='Import pre-made agent by name to a local directory.')
    available_agents = list_available_agents()
    import_parser.add_argument('--name', type=str, required=True, choices=available_agents, help='Name of the agent to import.')
    import_parser.add_argument('--destination', type=str, default="./", help='Destination path to copy the agent files.')

    args = parser.parse_args()

    if args.command == "create-agent-template":
        from agency_swarm.util import create_agent_template
        create_agent_template(args.name, args.description, args.path, args.use_txt)
    elif args.command == "genesis":
        load_dotenv()
        if not os.getenv('OPENAI_API_KEY') and not args.openai_key:
            print("OpenAI API key not set. "
                  "Please set it with --openai_key argument or by setting OPENAI_API_KEY environment variable.")
            return

        if args.openai_key:
            from agency_swarm import set_openai_key
            set_openai_key(args.openai_key)

        from agency_swarm.agency.genesis import GenesisAgency
        agency = GenesisAgency(with_browsing=args.with_browsing)
        agency.run_demo()
    elif args.command == "import-agent":
        from agency_swarm.util import import_agent
        import_agent(args.name, args.destination)


if __name__ == "__main__":
    main()


================================================
File: /agency-swarm-main\agency_swarm\messages\message_output.py
================================================
from typing import Literal
import hashlib
from rich.markdown import Markdown
from rich.console import Console, Group
from rich.live import Live

console = Console()

class MessageOutput:
    def __init__(self, msg_type: Literal["function", "function_output", "text", "system"], sender_name: str,
                 receiver_name: str, content, obj=None):
        """Initialize a message object with sender, receiver, content and type.

        Args:
            msg_type (Literal["function", "function_output", "text", "system"]): Type of message.
            sender_name (str): Name of the sender.
            receiver_name (str): Name of the receiver.
            content: Content of the message.
            obj: Optional OpenAI object that is causing the message.
        """
        self.msg_type = msg_type
        self.sender_name = str(sender_name)
        self.receiver_name = str(receiver_name)
        self.content = str(content)
        self.obj = obj

    def hash_names_to_color(self):
        if self.msg_type == "function" or self.msg_type == "function_output":
            return "dim"

        if self.msg_type == "system":
            return "red"

        combined_str = self.sender_name + self.receiver_name
        encoded_str = combined_str.encode()
        hash_obj = hashlib.md5(encoded_str)
        hash_int = int(hash_obj.hexdigest(), 16)
        colors = [
            'green', 'yellow', 'blue', 'magenta', 'cyan', 'bright_white',
        ]
        color_index = hash_int % len(colors)
        return colors[color_index]

    def cprint(self):
        console.rule()

        header_text = self.formatted_header
        md_content = Markdown(self.content)

        render_group = Group(header_text, md_content)

        console.print(render_group, end="")

    @property
    def formatted_header(self):
        return self.get_formatted_header()

    def get_formatted_header(self):
        if self.msg_type == "function":
            text = f"{self.sender_emoji} {self.sender_name} 🛠️ Executing Function"
            return text

        if self.msg_type == "function_output":
            text = f"{self.sender_name} ⚙️ Function Output"
            return text

        text = f"{self.sender_emoji} {self.sender_name} 🗣️ @{self.receiver_name}"

        return text

    def get_formatted_content(self):
        header = self.get_formatted_header()
        content = f"\n{self.content}\n"
        return header + content

    @property
    def sender_emoji(self):
        return self.get_sender_emoji()

    def get_sender_emoji(self):
        if self.msg_type == "system":
            return "🤖"

        sender_name = self.sender_name.lower()
        if self.msg_type == "function_output":
            sender_name = self.receiver_name.lower()

        if sender_name == "user":
            return "👤"

        if sender_name == "ceo":
            return "🤵"

        # output emoji based on hash of sender name
        encoded_str = sender_name.encode()
        hash_obj = hashlib.md5(encoded_str)
        hash_int = int(hash_obj.hexdigest(), 16)
        emojis = [
            '🐶', '🐱', '🐭', '🐹', '🐰', '🦊',
            '🐻', '🐼', '🐨', '🐯', '🦁', '🐮',
            '🐷', '🐸', '🐵', '🐔', '🐧', '🐦',
            '🐤']

        emoji_index = hash_int % len(emojis)

        return emojis[emoji_index]


class MessageOutputLive(MessageOutput):
    live_display = None

    def __init__(self, msg_type: Literal["function", "function_output", "text", "system"], sender_name: str,
                 receiver_name: str, content):
        super().__init__(msg_type, sender_name, receiver_name, content)
        # Initialize Live display if not already done
        self.live_display = Live(vertical_overflow="visible")
        self.live_display.start()

        console.rule()

    def __del__(self):
        if self.live_display:
            self.live_display.stop()
            self.live_display = None

    def cprint_update(self, snapshot):
        """
        Update the display with new snapshot content.
        """
        self.content = snapshot  # Update content with the latest snapshot

        header_text = self.formatted_header
        md_content = Markdown(self.content)

        # Creating a group of renderables for the live display
        render_group = Group(header_text, md_content)

        # Update the Live display
        self.live_display.update(render_group)


================================================
File: /agency-swarm-main\agency_swarm\messages\__init__.py
================================================
from .message_output import MessageOutput

================================================
File: /agency-swarm-main\agency_swarm\threads\thread.py
================================================
import asyncio
import inspect
import json
import os
import time
from typing import List, Optional, Type, Union

from openai import APIError, BadRequestError
from openai.types.beta import AssistantToolChoice
from openai.types.beta.threads.message import Attachment
from openai.types.beta.threads.run import TruncationStrategy

from agency_swarm.tools import FileSearch, CodeInterpreter
from agency_swarm.util.streaming import AgencyEventHandler
from agency_swarm.agents import Agent
from agency_swarm.messages import MessageOutput
from agency_swarm.user import User
from agency_swarm.util.oai import get_openai_client

from concurrent.futures import ThreadPoolExecutor, as_completed

import re

class Thread:
    async_mode: str = None
    max_workers: int = 4

    @property
    def thread_url(self):
        return f'https://platform.openai.com/playground/assistants?assistant={self.recipient_agent.id}&mode=assistant&thread={self.id}'
    
    @property
    def thread(self):
        self.init_thread()

        if not self._thread:
            print("retrieving thread", self.id)
            self._thread = self.client.beta.threads.retrieve(self.id)

        return self._thread

    def __init__(self, agent: Union[Agent, User], recipient_agent: Agent):
        self.agent = agent
        self.recipient_agent = recipient_agent

        self.client = get_openai_client()

        self.id = None
        self._thread = None
        self._run = None
        self._stream = None

        self._num_run_retries = 0
        # names of recepient agents that were called in SendMessage tool
        # needed to prevent agents calling the same recepient agent multiple times
        self._called_recepients = [] 

        self.terminal_states = ["cancelled", "completed", "failed", "expired", "incomplete"]

    def init_thread(self):
        self._called_recepients = []
        self._num_run_retries = 0

        if self.id:
            return
        
        self._thread = self.client.beta.threads.create()
        self.id = self._thread.id
        if self.recipient_agent.examples:
            for example in self.recipient_agent.examples:
                self.client.beta.threads.messages.create(
                    thread_id=self.id,
                    **example,
                )

    def get_completion_stream(self,
                              message: Union[str, List[dict], None],
                              event_handler: type(AgencyEventHandler),
                              message_files: List[str] = None,
                              attachments: Optional[List[Attachment]] = None,
                              recipient_agent:Agent=None,
                              additional_instructions: str = None,
                              tool_choice: AssistantToolChoice = None,
                              response_format: Optional[dict] = None):

        return self.get_completion(message,
                                   message_files,
                                   attachments,
                                   recipient_agent,
                                   additional_instructions,
                                   event_handler,
                                   tool_choice,
                                   yield_messages=False,
                                   response_format=response_format)

    def get_completion(self,
                       message: Union[str, List[dict], None],
                       message_files: List[str] = None,
                       attachments: Optional[List[dict]] = None,
                       recipient_agent: Union[Agent, None] = None,
                       additional_instructions: str = None,
                       event_handler: type(AgencyEventHandler) = None,
                       tool_choice: AssistantToolChoice = None,
                       yield_messages: bool = False,
                       response_format: Optional[dict] = None
                       ):
        self.init_thread()

        if not recipient_agent:
            recipient_agent = self.recipient_agent
        
        if not attachments:
            attachments = []

        if message_files:
            recipient_tools = []

            if FileSearch in recipient_agent.tools:
                recipient_tools.append({"type": "file_search"})
            if CodeInterpreter in recipient_agent.tools:
                recipient_tools.append({"type": "code_interpreter"})

            for file_id in message_files:
                attachments.append({"file_id": file_id,
                                    "tools": recipient_tools or [{"type": "file_search"}]})

        if event_handler:
            event_handler.set_agent(self.agent)
            event_handler.set_recipient_agent(recipient_agent)

        # Determine the sender's name based on the agent type
        sender_name = "user" if isinstance(self.agent, User) else self.agent.name
        print(f'THREAD:[ {sender_name} -> {recipient_agent.name} ]: URL {self.thread_url}')

        # send message
        if message:
            message_obj = self.create_message(
                message=message,
                role="user",
                attachments=attachments
            )

            if yield_messages:
                yield MessageOutput("text", self.agent.name, recipient_agent.name, message, message_obj)

        self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice, response_format=response_format)

        error_attempts = 0
        validation_attempts = 0
        full_message = ""
        while True:
            self._run_until_done()

            # function execution
            if self._run.status == "requires_action":
                self._called_recepients = []
                tool_calls = self._run.required_action.submit_tool_outputs.tool_calls
                tool_outputs_and_names = [] # list of tuples (name, tool_output)
                sync_tool_calls, async_tool_calls = self._get_sync_async_tool_calls(tool_calls, recipient_agent)

                def handle_output(tool_call, output):
                    if inspect.isgenerator(output):
                        try:
                            while True:
                                item = next(output)
                                if isinstance(item, MessageOutput) and yield_messages:
                                    yield item
                        except StopIteration as e:
                            output = e.value
                    else:
                        if yield_messages:
                            yield MessageOutput("function_output", tool_call.function.name, recipient_agent.name, output, tool_call)

                    for tool_output in tool_outputs_and_names:
                        if tool_output[1]["tool_call_id"] == tool_call.id:
                            tool_output[1]["output"] = output
                    
                    return output

                if len(async_tool_calls) > 0 and self.async_mode == "tools_threading":
                    max_workers = min(self.max_workers, os.cpu_count() or 1)  # Use at most 4 workers or the number of CPUs available
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {}
                        for tool_call in async_tool_calls:
                            if yield_messages:
                                yield MessageOutput("function", recipient_agent.name, self.agent.name, str(tool_call.function), tool_call)
                            futures[executor.submit(self.execute_tool, tool_call, recipient_agent, event_handler, tool_outputs_and_names)] = tool_call
                            tool_outputs_and_names.append((tool_call.function.name, {"tool_call_id": tool_call.id}))

                        for future in as_completed(futures):
                            tool_call = futures[future]
                            output, output_as_result = future.result()
                            output = yield from handle_output(tool_call, output)
                            if output_as_result:
                                self._cancel_run()
                                return output
                else:
                    sync_tool_calls += async_tool_calls

                # execute sync tool calls
                for tool_call in sync_tool_calls:
                    if yield_messages:
                        yield MessageOutput("function", recipient_agent.name, self.agent.name, str(tool_call.function), tool_call)
                    output, output_as_result = self.execute_tool(tool_call, recipient_agent, event_handler, tool_outputs_and_names)
                    tool_outputs_and_names.append((tool_call.function.name, {"tool_call_id": tool_call.id, "output": output}))
                    output = yield from handle_output(tool_call, output)
                    if output_as_result:
                        self._cancel_run()
                        return output

                # split names and outputs
                tool_outputs = [tool_output for _, tool_output in tool_outputs_and_names]
                tool_names = [name for name, _ in tool_outputs_and_names]

                # await coroutines
                tool_outputs = self._await_coroutines(tool_outputs)

                # convert all tool outputs to strings
                for tool_output in tool_outputs:
                    if not isinstance(tool_output["output"], str):
                        tool_output["output"] = str(tool_output["output"])

                # send message tools can change this in other threads
                if event_handler:
                    event_handler.set_agent(self.agent)
                    event_handler.set_recipient_agent(recipient_agent)
                    
                # submit tool outputs
                try:
                    self._submit_tool_outputs(tool_outputs, event_handler)
                except BadRequestError as e:
                    if 'Runs in status "expired"' in e.message:
                        self.create_message(
                            message="Previous request timed out. Please repeat the exact same tool calls in the exact same order with the same arguments.",
                            role="user"
                        )

                        self._create_run(recipient_agent, additional_instructions, event_handler, 'required', temperature=0)
                        self._run_until_done()

                        if self._run.status != "requires_action":
                            raise Exception("Run Failed. Error: ", self._run.last_error or self._run.incomplete_details)

                        # change tool call ids
                        tool_calls = self._run.required_action.submit_tool_outputs.tool_calls

                        if len(tool_calls) != len(tool_outputs):
                            tool_outputs = []
                            for i, tool_call in enumerate(tool_calls):
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": "Error: openai run timed out. You can try again one more time."})
                        else:
                            for i, tool_name in enumerate(tool_names):
                                for tool_call in tool_calls[:]:
                                    if tool_call.function.name == tool_name:
                                        tool_outputs[i]["tool_call_id"] = tool_call.id
                                        tool_calls.remove(tool_call)
                                        break

                        self._submit_tool_outputs(tool_outputs, event_handler)
                    else:
                        raise e
            # error
            elif self._run.status == "failed":
                full_message += self._get_last_message_text()
                common_errors = ["something went wrong", "the server had an error processing your request", "rate limit reached"]
                error_message = self._run.last_error.message.lower()

                if error_attempts < 3 and any(error in error_message for error in common_errors):
                    if error_attempts < 2:
                        time.sleep(1 + error_attempts)
                    else:
                        self.create_message(message="Continue.", role="user")
                    
                    self._create_run(recipient_agent, additional_instructions, event_handler, 
                                     tool_choice, response_format=response_format)
                    error_attempts += 1
                else:
                    raise Exception("OpenAI Run Failed. Error: ", self._run.last_error.message)
            elif self._run.status == "incomplete":
                raise Exception("OpenAI Run Incomplete. Details: ", self._run.incomplete_details)
            # return assistant message
            else:
                message_obj = self._get_last_assistant_message()
                last_message = message_obj.content[0].text.value
                full_message += last_message

                if yield_messages:
                    yield MessageOutput("text", recipient_agent.name, self.agent.name, last_message, message_obj)

                if recipient_agent.response_validator:
                    try:
                        if isinstance(recipient_agent, Agent):
                            # TODO: allow users to modify the last message from response validator and replace it on OpenAI
                            recipient_agent.response_validator(message=last_message)
                    except Exception as e:
                        if validation_attempts < recipient_agent.validation_attempts:
                            try:
                                evaluated_content = eval(str(e))
                                if isinstance(evaluated_content, list):
                                    content = evaluated_content
                                else:
                                    content = str(e)
                            except Exception as eval_exception:
                                content = str(e)

                            message_obj = self.create_message(
                                message=content,
                                role="user"
                            )

                            if yield_messages:
                                for content in message_obj.content:
                                    if hasattr(content, 'text') and hasattr(content.text, 'value'):
                                        yield MessageOutput("text", self.agent.name, recipient_agent.name,
                                                            content.text.value, message_obj)
                                        break

                            if event_handler:
                                handler = event_handler()
                                handler.on_message_created(message_obj)
                                handler.on_message_done(message_obj)

                            validation_attempts += 1

                            self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice, response_format=response_format)

                            continue

                return last_message

    def _create_run(self, recipient_agent, additional_instructions, event_handler, tool_choice, temperature=None, response_format: Optional[dict] = None):
        try:
            if event_handler:
                with self.client.beta.threads.runs.stream(
                        thread_id=self.id,
                        event_handler=event_handler(),
                        assistant_id=recipient_agent.id,
                        additional_instructions=additional_instructions,
                        tool_choice=tool_choice,
                        max_prompt_tokens=recipient_agent.max_prompt_tokens,
                        max_completion_tokens=recipient_agent.max_completion_tokens,
                        truncation_strategy=recipient_agent.truncation_strategy,
                        temperature=temperature,
                        extra_body={"parallel_tool_calls": recipient_agent.parallel_tool_calls},
                        response_format=response_format
                ) as stream:
                    stream.until_done()
                    self._run = stream.get_final_run()
            else:
                self._run = self.client.beta.threads.runs.create(
                    thread_id=self.id,
                    assistant_id=recipient_agent.id,
                    additional_instructions=additional_instructions,
                    tool_choice=tool_choice,
                    max_prompt_tokens=recipient_agent.max_prompt_tokens,
                    max_completion_tokens=recipient_agent.max_completion_tokens,
                    truncation_strategy=recipient_agent.truncation_strategy,
                    temperature=temperature,
                    parallel_tool_calls=recipient_agent.parallel_tool_calls,
                    response_format=response_format
                )
                self._run = self.client.beta.threads.runs.poll(
                    thread_id=self.id,
                    run_id=self._run.id,
                    # poll_interval_ms=500,
                )
        except APIError as e:
            match = re.search(r"Thread (\w+) already has an active run (\w+)", e.message)
            if match:
                self._cancel_run(thread_id=match.groups()[0], run_id=match.groups()[1], check_status=False)
            elif "The server had an error processing your request" in e.message and self._num_run_retries < 3:
                time.sleep(1)
                self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice, response_format=response_format)
                self._num_run_retries += 1
            else:
                raise e

    def _run_until_done(self):
        while self._run.status in ['queued', 'in_progress', "cancelling"]:
            time.sleep(0.5)
            self._run = self.client.beta.threads.runs.retrieve(
                thread_id=self.id,
                run_id=self._run.id
            )

    def _submit_tool_outputs(self, tool_outputs, event_handler=None, poll=True):
        if not poll:
            self._run = self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=self.id,
                run_id=self._run.id,
                tool_outputs=tool_outputs
            )
        else:
            if not event_handler:
                self._run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                    thread_id=self.id,
                    run_id=self._run.id,
                    tool_outputs=tool_outputs
                )
            else:
                with self.client.beta.threads.runs.submit_tool_outputs_stream(
                        thread_id=self.id,
                        run_id=self._run.id,
                        tool_outputs=tool_outputs,
                        event_handler=event_handler()
                ) as stream:
                    stream.until_done()
                    self._run = stream.get_final_run()

    def _cancel_run(self, thread_id=None, run_id=None, check_status=True):
        if check_status and self._run.status in self.terminal_states and not run_id:
            return
        
        try:
            self._run = self.client.beta.threads.runs.cancel(
                thread_id=self.id,
                run_id=self._run.id
            )
        except BadRequestError as e:
            if "Cannot cancel run with status" in e.message:
                self._run = self.client.beta.threads.runs.poll(
                    thread_id=thread_id or self.id,
                    run_id=run_id or self._run.id,
                    poll_interval_ms=500,
                )
            else:
                raise e

    def _get_last_message_text(self):
        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            limit=1
        )

        if len(messages.data) == 0 or len(messages.data[0].content) == 0:
            return ""

        return messages.data[0].content[0].text.value

    def _get_last_assistant_message(self):
        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            limit=1
        )

        if len(messages.data) == 0 or len(messages.data[0].content) == 0:
            raise Exception("No messages found in the thread")

        message = messages.data[0]

        if message.role == "assistant":
            return message

        raise Exception("No assistant message found in the thread")   

    def create_message(self, message: str, role: str = "user", attachments: List[dict] = None):
        try:
            return self.client.beta.threads.messages.create(
                thread_id=self.id,
                role=role,
                content=message,
                attachments=attachments
            )
        except BadRequestError as e:
            regex = re.compile(
                r"Can't add messages to thread_([a-zA-Z0-9]+) while a run run_([a-zA-Z0-9]+) is active\."
            )
            match = regex.search(str(e))
            
            if match:
                thread_id, run_id = match.groups()
                thread_id = f"thread_{thread_id}"
                run_id = f"run_{run_id}"
                
                self._cancel_run(thread_id=thread_id, run_id=run_id)

                return self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role=role,
                    content=message,
                    attachments=attachments
                )
            else:
                raise e

    def execute_tool(self, tool_call, recipient_agent=None, event_handler=None, tool_outputs_and_names={}):
        if not recipient_agent:
            recipient_agent = self.recipient_agent

        tool_name = tool_call.function.name
        funcs = recipient_agent.functions
        tool = next((func for func in funcs if func.__name__ == tool_name), None)

        if not tool:
            return f"Error: Function {tool_call.function.name} not found. Available functions: {[func.__name__ for func in funcs]}", False

        try:
            # init tool
            args = tool_call.function.arguments
            args = json.loads(args) if args else {}
            tool = tool(**args)

            # check if the tool is already called
            for tool_name in [name for name, _ in tool_outputs_and_names]:
                if tool_name == tool_name and (
                        hasattr(tool, "ToolConfig") and hasattr(tool.ToolConfig, "one_call_at_a_time") and tool.ToolConfig.one_call_at_a_time):
                    return f"Error: Function {tool_name} is already called. You can only call this function once at a time. Please wait for the previous call to finish before calling it again.", False
            
            # for send message tools, don't allow calling the same recepient agent multiple times
            if tool_name.startswith("SendMessage"):
                if tool.recipient.value in self._called_recepients:
                    return f"Error: Agent {tool.recipient.value} has already been called. You can only call each agent once at a time. Please wait for the previous call to finish before calling it again.", False
                self._called_recepients.append(tool.recipient.value)

            tool._caller_agent = recipient_agent
            tool._event_handler = event_handler
            tool._tool_call = tool_call

            return tool.run(), tool.ToolConfig.output_as_result
        except Exception as e:
            error_message = f"Error: {e}"
            if "For further information visit" in error_message:
                error_message = error_message.split("For further information visit")[0]
            return error_message, False
        
    def _await_coroutines(self, tool_outputs):
        async_tool_calls = []
        for tool_output in tool_outputs:
            if inspect.iscoroutine(tool_output["output"]):
                async_tool_calls.append(tool_output)

        if async_tool_calls:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop = asyncio.get_event_loop()

            results = loop.run_until_complete(asyncio.gather(*[call["output"] for call in async_tool_calls]))
            
            for tool_output, result in zip(async_tool_calls, results):
                tool_output["output"] = str(result)
        
        return tool_outputs
    
    def _get_sync_async_tool_calls(self, tool_calls, recipient_agent):
        async_tool_calls = []
        sync_tool_calls = []
        for tool_call in tool_calls:
            if tool_call.function.name.startswith("SendMessage"):
                sync_tool_calls.append(tool_call)
                continue

            tool = next((func for func in recipient_agent.functions if func.__name__ == tool_call.function.name), None)

            if (hasattr(tool.ToolConfig, "async_mode") and tool.ToolConfig.async_mode) or self.async_mode == "tools_threading":
                async_tool_calls.append(tool_call)
            else:
                sync_tool_calls.append(tool_call)

        return sync_tool_calls, async_tool_calls
    
    def get_messages(self, limit=None):
        all_messages = []
        after = None
        while True:
            response = self.client.beta.threads.messages.list(thread_id=self.id, limit=100, after=after)
            messages = response.data
            if not messages:
                break
            all_messages.extend(messages)
            after = messages[-1].id  # Set the 'after' cursor to the ID of the last message

            if limit and len(all_messages) >= limit:
                break

        return all_messages












================================================
File: /agency-swarm-main\agency_swarm\threads\thread_async.py
================================================
import threading
from typing import Union, Optional, List

from openai.types.beta import AssistantToolChoice

from agency_swarm.agents import Agent
from agency_swarm.threads import Thread
from agency_swarm.user import User


class ThreadAsync(Thread):
    def __init__(self, agent: Union[Agent, User], recipient_agent: Agent):
        super().__init__(agent, recipient_agent)
        self.pythread = None
        self.response = None
        self.async_mode = False 

    def worker(self,
               message: str,
               message_files: List[str] = None,
               attachments: Optional[List[dict]] = None,
               recipient_agent=None,
               additional_instructions: str = None,
               tool_choice: AssistantToolChoice = None
               ):
        self.async_mode = False 

        gen = self.get_completion(message=message,
                                    message_files=message_files,
                                    attachments=attachments,
                                    recipient_agent=recipient_agent,
                                    additional_instructions=additional_instructions,
                                    tool_choice=tool_choice)

        while True:
            try:
                next(gen)
            except StopIteration as e:
                self.response = f"""{self.recipient_agent.name}'s Response: '{e.value}'"""
                break

        return

    def get_completion_async(self,
                             message: str,
                             message_files: List[str] = None,
                             attachments: Optional[List[dict]] = None,
                             recipient_agent=None,
                             additional_instructions: str = None,
                             tool_choice: AssistantToolChoice = None,
                             ):
        if self.pythread and self.pythread.is_alive():
            return "System Notification: 'Agent is busy, so your message was not received. Please always use 'GetResponse' tool to check for status first, before using 'SendMessage' tool again for the same agent.'"
        elif self.pythread and not self.pythread.is_alive():
            self.pythread.join()
            self.pythread = None
            self.response = None

        run = self.get_last_run()

        if run and run.status in ['queued', 'in_progress', 'requires_action']:
            return "System Notification: 'Agent is busy, so your message was not received. Please always use 'GetResponse' tool to check for status first, before using 'SendMessage' tool again for the same agent.'"

        self.pythread = threading.Thread(target=self.worker,
                                         args=(message, message_files, attachments, recipient_agent, additional_instructions, tool_choice))

        self.pythread.start()

        return "System Notification: 'Task has started. Please notify the user that they can tell you to check the status later. You can do this with the 'GetResponse' tool, after you have been instructed to do so. Don't mention the tool itself to the user. "

    def check_status(self, run=None):
        if not run:
            run = self.get_last_run()

        if not run:
            return "System Notification: 'Agent is ready to receive a message. Please send a message with the 'SendMessage' tool.'"

        # check run status
        if run.status in ['queued', 'in_progress', 'requires_action']:
            return "System Notification: 'Task is not completed yet. Please tell the user to wait and try again later.'"

        if run.status == "failed":
            return f"System Notification: 'Agent run failed with error: {run.last_error.message}. You may send another message with the 'SendMessage' tool.'"

        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            order="desc",
        )

        return f"""{self.recipient_agent.name}'s Response: '{messages.data[0].content[0].text.value}'"""

    def get_last_run(self):
        self.init_thread()

        runs = self.client.beta.threads.runs.list(
            thread_id=self.id,
            order="desc",
        )

        if len(runs.data) == 0:
            return None

        run = runs.data[0]

        return run


================================================
File: /agency-swarm-main\agency_swarm\threads\__init__.py
================================================
from .thread import Thread


================================================
File: /agency-swarm-main\agency_swarm\tools\BaseTool.py
================================================
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal, Union

from docstring_parser import parse

from pydantic import BaseModel
from agency_swarm.util.shared_state import SharedState


class BaseTool(BaseModel, ABC):
    _shared_state: ClassVar[SharedState] = None
    _caller_agent: Any = None
    _event_handler: Any = None
    _tool_call: Any = None

    def __init__(self, **kwargs):
        if not self.__class__._shared_state:
            self.__class__._shared_state = SharedState()
        super().__init__(**kwargs)
        
        # Ensure all ToolConfig variables are initialized
        config_defaults = {
            'strict': False,
            'one_call_at_a_time': False,
            'output_as_result': False,
            'async_mode': None
        }
        
        for key, value in config_defaults.items():
            if not hasattr(self.ToolConfig, key):
                setattr(self.ToolConfig, key, value)

    class ToolConfig:
        strict: bool = False
        one_call_at_a_time: bool = False
        # return the tool output as assistant message
        output_as_result: bool = False
        async_mode: Union[Literal["threading"], None] = None

    @classmethod
    @property
    def openai_schema(cls):
        """
        Return the schema in the format of OpenAI's schema as jsonschema

        Note:
            Its important to add a docstring to describe how to best use this class, it will be included in the description attribute and be part of the prompt.

        Returns:
            model_json_schema (dict): A dictionary in the format of OpenAI's schema as jsonschema
        """
        schema = cls.model_json_schema()
        docstring = parse(cls.__doc__ or "")
        parameters = {
            k: v for k, v in schema.items() if k not in ("title", "description")
        }
        for param in docstring.params:
            if (name := param.arg_name) in parameters["properties"] and (
                description := param.description
            ):
                if "description" not in parameters["properties"][name]:
                    parameters["properties"][name]["description"] = description

        parameters["required"] = sorted(
            k for k, v in parameters["properties"].items() if "default" not in v
        )

        if "description" not in schema:
            if docstring.short_description:
                schema["description"] = docstring.short_description
            else:
                schema["description"] = (
                    f"Correctly extracted `{cls.__name__}` with all "
                    f"the required parameters with correct types"
                )

        schema = {
            "name": schema["title"],
            "description": schema["description"],
            "parameters": parameters,
        }

        strict = getattr(cls.ToolConfig, "strict", False)
        if strict:
            schema["strict"] = True
            schema["parameters"]["additionalProperties"] = False
            # iterate through defs and set additionalProperties to false
            if "$defs" in schema["parameters"]:
                for def_ in schema["parameters"]["$defs"].values():
                    def_["additionalProperties"] = False
            
        return schema

    @abstractmethod
    def run(self):
        pass


================================================
File: /agency-swarm-main\agency_swarm\tools\oai\CodeInterpreter.py
================================================
from pydantic import BaseModel


class CodeInterpreter(BaseModel):
    type: str = "code_interpreter"


================================================
File: /agency-swarm-main\agency_swarm\tools\oai\FileSearch.py
================================================
from openai.types.beta.file_search_tool import FileSearchTool
from openai.types.beta.file_search_tool import FileSearch as OpenAIFileSearch

class FileSearchConfig(OpenAIFileSearch):
    pass

class FileSearch(FileSearchTool):
    type: str = "file_search"

================================================
File: /agency-swarm-main\agency_swarm\tools\oai\Retrieval.py
================================================
from pydantic import BaseModel


class Retrieval(BaseModel):
    type: str = "file_search"

================================================
File: /agency-swarm-main\agency_swarm\tools\oai\__init__.py
================================================
from .CodeInterpreter import CodeInterpreter
from .FileSearch import FileSearch
from .Retrieval import Retrieval


================================================
File: /agency-swarm-main\agency_swarm\tools\send_message\SendMessage.py
================================================
from typing import Optional, List
from pydantic import Field, field_validator, model_validator
from .SendMessageBase import SendMessageBase

class SendMessage(SendMessageBase):
    """Use this tool to facilitate direct, synchronous communication between specialized agents within your agency. When you send a message using this tool, you receive a response exclusively from the designated recipient agent. To continue the dialogue, invoke this tool again with the desired recipient agent and your follow-up message. Remember, communication here is synchronous; the recipient agent won't perform any tasks post-response. You are responsible for relaying the recipient agent's responses back to the user, as the user does not have direct access to these replies. Keep engaging with the tool for continuous interaction until the task is fully resolved. Do not send more than 1 message to the same recipient agent at the same time."""
    my_primary_instructions: str = Field(
        ..., 
        description=(
            "Please repeat your primary instructions step-by-step, including both completed "
            "and the following next steps that you need to perform. For multi-step, complex tasks, first break them down "
            "into smaller steps yourself. Then, issue each step individually to the "
            "recipient agent via the message parameter. Each identified step should be "
            "sent in a separate message. Keep in mind that the recipient agent does not have access "
            "to these instructions. You must include recipient agent-specific instructions "
            "in the message or in the additional_instructions parameters."
        )
    )
    message: str = Field(
        ..., 
        description="Specify the task required for the recipient agent to complete. Focus on clarifying what the task entails, rather than providing exact instructions. Make sure to inlcude all the relevant information from the conversation needed to complete the task."
    )
    message_files: Optional[List[str]] = Field(
        default=None,
        description="A list of file IDs to be sent as attachments to this message. Only use this if you have the file ID that starts with 'file-'.",
        examples=["file-1234", "file-5678"]
    )
    additional_instructions: Optional[str] = Field(
        default=None,
        description="Additional context or instructions from the conversation needed by the recipient agent to complete the task."
    )

    @model_validator(mode='after')
    def validate_files(self):
        # prevent hallucinations with agents sending file IDs into incorrect fields
        if "file-" in self.message or (self.additional_instructions and "file-" in self.additional_instructions):
            if not self.message_files:
                raise ValueError("You must include file IDs in message_files parameter.")
        return self
    
    def run(self):
        return self._get_completion(message=self.message,
                                    message_files=self.message_files,
                                    additional_instructions=self.additional_instructions)

================================================
File: /agency-swarm-main\agency_swarm\tools\send_message\SendMessageAsyncThreading.py
================================================
from typing import ClassVar, Type
from agency_swarm.threads.thread_async import ThreadAsync
from .SendMessage import SendMessage

class SendMessageAsyncThreading(SendMessage):
    """Use this tool for asynchronous communication with other agents within your agency. Initiate tasks by messaging, and check status and responses later with the 'GetResponse' tool. Relay responses to the user, who instructs on status checks. Continue until task completion."""
    class ToolConfig:
        async_mode = "threading"

================================================
File: /agency-swarm-main\agency_swarm\tools\send_message\SendMessageBase.py
================================================
from agency_swarm.agents.agent import Agent
from agency_swarm.threads.thread import Thread
from typing import ClassVar, Union
from pydantic import Field, field_validator
from agency_swarm.threads.thread_async import ThreadAsync
from agency_swarm.tools import BaseTool
from abc import ABC

class SendMessageBase(BaseTool, ABC):
    recipient: str = Field(..., description="Recipient agent that you want to send the message to. This field will be overriden inside the agency class.")
    
    _agents_and_threads: ClassVar = None

    @field_validator('additional_instructions', mode='before', check_fields=False)
    @classmethod
    def validate_additional_instructions(cls, value):
        # previously the parameter was a list, now it's a string
        # add compatibility for old code
        if isinstance(value, list):
            return "\n".join(value)
        return value
        
    def _get_thread(self) -> Thread | ThreadAsync:
        return self._agents_and_threads[self._caller_agent.name][self.recipient.value]
    
    def _get_main_thread(self) -> Thread | ThreadAsync:
        return self._agents_and_threads["main_thread"]
    
    def _get_recipient_agent(self) -> Agent:
        return self._agents_and_threads[self._caller_agent.name][self.recipient.value].recipient_agent
    
    def _get_completion(self, message: Union[str, None] = None, **kwargs):
        thread = self._get_thread()

        if self.ToolConfig.async_mode == "threading":
            return thread.get_completion_async(message=message, **kwargs)
        else:
            return thread.get_completion(message=message, 
                                        event_handler=self._event_handler,
                                        yield_messages=not self._event_handler,
                                        **kwargs)

================================================
File: /agency-swarm-main\agency_swarm\tools\send_message\SendMessageQuick.py
================================================
from agency_swarm.threads.thread import Thread
from typing import ClassVar, Optional, List, Type
from pydantic import Field, field_validator, model_validator
from .SendMessageBase import SendMessageBase

class SendMessageQuick(SendMessageBase):
    """Use this tool to facilitate direct, synchronous communication between specialized agents within your agency. When you send a message using this tool, you receive a response exclusively from the designated recipient agent. To continue the dialogue, invoke this tool again with the desired recipient agent and your follow-up message. Remember, communication here is synchronous; the recipient agent won't perform any tasks post-response. You are responsible for relaying the recipient agent's responses back to the user, as the user does not have direct access to these replies. Keep engaging with the tool for continuous interaction until the task is fully resolved. Do not send more than 1 message to the same recipient agent at the same time."""
    message: str = Field(
        ..., 
        description="Specify the task required for the recipient agent to complete. Focus on clarifying what the task entails, rather than providing exact instructions. Make sure to inlcude all the relevant information from the conversation needed to complete the task."
    )
    
    def run(self):
        return self._get_completion(message=self.message)

================================================
File: /agency-swarm-main\agency_swarm\tools\send_message\SendMessageSwarm.py
================================================
from openai import BadRequestError
from agency_swarm.threads.thread import Thread
from .SendMessage import SendMessageBase

class SendMessageSwarm(SendMessageBase):
    """Use this tool to route messages to other agents within your agency. After using this tool, you will be switched to the recipient agent. This tool can only be used once per message. Do not use any other tools together with this tool."""

    class ToolConfig:
        # set output as result because the communication will be finished after this tool is called
        output_as_result
