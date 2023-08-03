#dc-bot  
This is a bot that uses the GPT-3.5 model from OpenAI to respond to user messages in a conversational manner. Depending on the initial prompt it can be used to fake interactions with scammers, and provide faked PayPal receipts.     
If You want to use it for this application, DM me on discord (@caesarlp) or here.  

**Available Commands:**  
  
- `!delete_conv`: Deletes the conversation from bot memory.  
- `!load_conv "user" ["number"]`: Loads a specific conversation.  
- `!list_conv`: Lists available conversations.  
- `!get_config`: Returns the current configuration.  
- `!repeat_conv`: Repeats the current conversation.  
- `!toggle_testmode`: Toggles test mode for shorter response time.  
- `!set_temperature value`: Changes the temperature.  
- `!set_max_token value`: Sets the maximal amount of tokens used.  
- `!set_delay value`: Sets the minimum reply delay.  
- `!toggle_test_prompt`: Toggles usage of a test prompt.  
- `!get_init_prompt`: Returns the initial prompt of this conversation.  
- `!command_help`: Returns all available commands.  
- `!disable_commands passwort`: Disables all commands until restart (password required).  
- `!del_specific "user"`: Deletes the conversation log of a specific user from memory.  
- `!shutdown`: Shuts down the bot.  
- `!save_all`: Saves all ongoing conversations.  
- `!get_msg_log user_id`: Returns all DMs by a user.  
- `!force_resend "name" ["message"]`: Tries to send the last message or a specified message.  
- `!load_author user_id`: Tries to load an author by ID (load the conversation first!).  
- `!clear_memory`: Clears conversations from memory.  
- `!ban user_id`: Bans a user from interacting with the bot.  
- `!unban user_id`: Unbans a user from interacting with the bot.  
- `!whitelist "user" "value"`: Whitelists a user with a permission value (1-15).  
- `!reload_whitelist`: Reloads the whitelist from disk.  
- `!reload_blacklist`: Reloads the blacklist from disk.  
- `!init_conv "user" "id" "message"`: Initializes a conversation with a message to a user with ID.  
- `!fake_receipt "user" "id" "store name" "amount"`: Fakes a PayPal receipt for a given store name and amount (currently only in German).  

##TODO:  
- Generate Fake receipts automatically.  
- Fine tune init_prompt for better stability.   
- Improve usability through accepting commands in Threads  

## ConversationHandler class    
  
### Methods    
  
**\_\_init\_\_(self, user, bot_name, init_prompt=None, conversation=None, author=None):** Initializes a ConversationHandler object. Parameters:  
- *user* (str): The name of the user associated with the conversation.  
- *bot_name* (str): The name of the bot.  
- *init_prompt* (str, optional): The initial prompt for the conversation. Defaults to None.  
- *conversation* (list, optional): A list representing the conversation history. Defaults to None.  
- *author* (discord.Author, optional): The author of the conversation. Defaults to None.  
  
**awaitingResponse(self):** Checks if the conversation is currently awaiting a response from the user. Returns True if the last role in the conversation is "user", False otherwise.  
  
**updateGPT(self, message):** Adds a message from the GPT model to the conversation. Parameters:  
- *message* (str): The message from the GPT model.  
  
**updateUser(self, message):** Adds a message from the user to the conversation. Parameters:  
- *message* (str): The message from the user.  
  
**appendUserMessage(self, message:str):** Appends a message to the last user message in the conversation. Parameters:  
- *message* (str): The message to append.  
  
**checkDir(self):** Checks if the directory for conversation files exists. If not, the directory is created.  
  
**writeConversation(self):** Writes the conversation to a JSON file.  
  
**saveConversation(self):** Saves the conversation to a numbered JSON file. If a numbered file already exists, the conversation is saved with an incremented number.  
  
**fetchConversation(self):** Retrieves the conversation from a JSON file.  
  
**deleteConversation(self):** Saves the conversation and deletes the JSON file.  
  
**listConversations(bot_name: str):** Returns a list of all conversation files in the directory.  
  
**loadConversation(name: str, number, bot_name):** Loads a specific conversation from a JSON file. Parameters:  
- *name* (str): The name associated with the conversation.  
- *number* (int): The number of the conversation file. If None, the latest conversation file is loaded.  
- *bot_name* (str): The name of the bot.  
  
**saveMedia(name: str, medias):** Saves media attached to a message. Parameters:  
- *name* (str): The name associated with the conversation.  
- *medias*: The list of attached media.  
  
**QueueItem class:** Represents an item in the asyncio Queue. Contains a message and a timestamp.  
  
### Attributes  
  
- *user* (str): The name of the user associated with the conversation.  
- *bot_name* (str): The name of the bot.  
- *dir_path* (str): The path of the directory containing conversation files.  
- *file_path* (str): The path of the conversation file.  
- *init_prompt* (str): The initial prompt for the conversation.  
- *author* (discord.Author): The author of the conversation.  
- *base_prompt* (dict): The base prompt for the conversation.  
- *conversation* (list): The list representing the conversation history.  