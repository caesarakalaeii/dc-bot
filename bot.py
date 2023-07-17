import asyncio
import random
import discord
from discord.ext import commands
import json
import os
import openai
import requests

from promt_creation import get_prompt, get_art_styles
from api_secrets import *
from logger import Logger
from whitelist import whitelist

class ConversationHandler():
    
    
    def __init__(self, user, bot_name , init_prompt = None, conversation = None):
        self.user = user
        self.bot_name = bot_name
        self.dir_path = f"{self.bot_name}_conversations"
        self.file_path = os.path.join(self.dir_path, f"{self.user}.json")
        self.init_prompt = init_prompt
        self.base_prompt = {"role": "system", "content": self.init_prompt}
        if not conversation is None:
            self.conversation = conversation
        else:
            try:
                self.checkDir()
                self.fetchConversation()
            except FileNotFoundError:
                self.conversation = [self.base_prompt]
    
        
    def awaitingResponse(self):
        return self.conversation[-1]["role"] == "user"
    
    def updateGPT(self, message):
        self.conversation.append({"role": "assistant", "content": message})
        
    def updateUser(self, message):
        self.conversation.append({"role": "user", "content": message})
        
    def appendUserMessage(self, message:str):
        self.conversation[-1]["content"] + "\n" + message
        
    def checkDir(self):
        try:
            os.mkdir(self.dir_path)
        except FileExistsError:
            return
        
        
    def writeConversation(self):
        with open(self.file_path, "w") as f:
            f.write(json.dumps(self.conversation))
    
    def saveConversation(self):
        for i in range(100):
            if os.path.exists(os.path.join(self.dir_path, f"{self.user}_{i}.json")):
                continue
            else:
                with open(os.path.join(self.dir_path, f"{self.user}_{i}.json"), "w") as f:
                    f.write(json.dumps(self.conversation))
                break
                
    def fetchConversation(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                self.conversation = json.loads(f.read())
        else: 
            raise FileNotFoundError

    def deleteConversation(self):
        self.saveConversation()
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        else: raise FileNotFoundError
        
    def listConversations(bot_name : str):
        return os.listdir(f"{bot_name}_conversations")

    def loadConversation(name : str, number, bot_name):
        dir_path = f"{bot_name}_conversations"
        if os.path.exists(os.path.join(dir_path, f"{name}_{number}.json")):
            with open(os.path.join(dir_path, f"{name}_{number}.json"), "r") as f:
                return json.loads(f.read())
        else: 
            raise FileNotFoundError
        
    def saveMedia(name : str, medias):
        try:
            os.makedirs(f"{name}_media", exist_ok=True)  # Create directory if it doesn't exist
        except OSError as e:
            print(f"Error creating directory: {e}")
            return

        for media in medias:
            file_path = os.path.join(name, media.filename)
            if not os.path.exists(file_path):
                try:
                    r = requests.get(media.url, allow_redirects=True)
                    with open(file_path, 'wb') as file:
                        file.write(r.content)
                except Exception as e:
                    print(f"Error saving media: {e}")
            else:
                i = 0
                while True:
                    filename :str = media.filename
                    filename_split = filename.split(".")
                    new_name = ""
                    for j in range(len(filename_split)-1):
                        new_name += filename_split[j]
                    new_name += f"_{i}.{filename_split[-1]}"
                    file_path = os.path.join(name, new_name)
                    if not os.path.exists(file_path):
                        try:
                            r = requests.get(media.url, allow_redirects=True)
                            with open(file_path, 'wb') as file:
                                file.write(r.content)
                            break
                        except Exception as e:
                            print(f"Error saving media: {e}")
                            break
                    i+=i
        

class GPTBot():
    
    
    def __init__(self, bot_token, gpt_api_key, bot_name, 
                 streamer_name, timer_duration = 300, art_styles = None, 
                 test_mode = False, temperature = 0.7, max_tokens = 256, 
                 use_test_prompt = False, commands_enabled = True, admin_pw = None,
                 stream_link = None):
        self.conversations = []
        self.commands_enabled = commands_enabled
        self.__admin_pw = admin_pw
        self.commands = {
            "!delete_conv": {
                "perm": 5,
                "help": "!delete_conv: Deletes this Conversation from bot Memory",
                "value_type": None,
                "func": self.del_conv
                },
            "!load_conv": {
                "perm": 10,
                "help": "!load_conv user number: Loads specific Conversation",
                "value_type": [str,int],
                "func": self.load_conv
                },
            "!list_conv": {
                "perm": 10,
                "help": "!list_conv: Lists availabe conversations",
                "value_type": None,
                "func": self.list_conv
                },
            "!get_config": {
                "perm": 5,
                "help": "!get_config: returns current configuration",
                "value_type": None,
                "func": self.get_config
                },
            "!repeat_conv": {
                "perm": 5,
                "help": "!repeat_conv: repeats current conversation WARNING: might be a lot! will return nothing when conversation is not in memory",
                "value_type": None,
                "func": self.repeat_conv
                },
            "!toggle_testmode":{
                "perm": 10,
                "help": "!toggle_testmode: toggles testmode for shorter response time.",
                "value_type": None,
                "func": self.toggle_test_mode
                },  
            "!set_temperature": {
                "perm": 10,
                "help": "!set_temperature value: Changes temperature",
                "value_type": float,
                "func": self.set_temp
                },
            "!set_max_token": {
                "perm": 10,
                "help": "!set_max_token value: sets the maximal Amount of Tokens used",
                "value_type": int,
                "func": self.set_max_tokens
                },
            "!set_delay": {
                "perm": 10,
                "help": "!set_delay value: will set minimum reply delay",
                "value_type": int,
                "func": self.set_delay
                },
            "!toggle_test_prompt": {
                "perm": 10,
                "help": "!toggle_test_prompt: toggles usage of a test prompt",
                "value_type": None,
                "func": self.toggle_test_prompt
                },
            "!get_init_prompt": {
                "perm": 15,
                "help": "!get_init_prompt: returns initial prompt of this conversation",
                "value_type": None,
                "func": self.get_init_prompt
                },
            "!command_help":{
                "perm": 1,
                "help": "!command_help: returns all available commands",
                "value_type": None,
                "func": self.help
                },
            "!disable_commands":{
                "perm": 15,
                "help": "!disable_commands passwort: disables all commands until restart, passwort is set in api_secrets.py",
                "value_type": str,
                "func": self.disable_commands
                },
            "!force_load":{
                "perm":5,
                "help":"!force_load: loads latest conversation, if available",
                "value_type": None,
                "func": self.force_load
                },
            "!del_specific":{
                "perm":10,
                "help":"!del_specific user: deletes conversation log of specific user from memory",
                "value_type": str,
                "func": self.del_specific_conv
                },
            "!shutdown":{
                "perm":15,
                "help":"!shutdown: shutsdown this bot",
                "value_type": None,
                "func": self.shutdown
                },
            "!save_all":{
                "perm":10,
                "help":"!save_all: saves all on going conversations",
                "value_type": None,
                "func": self.save_all
                }
            
            
        }
        self.__bot_token = bot_token
        self.logger = Logger(True, True)
        if self.__admin_pw == None:
            self.logger.error("No admin password provided, you will not be able to disable commands!")
        openai.api_key = gpt_api_key
        self.MODEL_NAME = "gpt-3.5-turbo"
        self.use_test_prompt = use_test_prompt        
        self.streamer_name = streamer_name
        if art_styles == None:
            art_styles = get_art_styles()
        self.art_styles = art_styles
        self.init_prompt = get_prompt(bot_name, streamer_name, self.art_styles, use_test_prompt, stream_link)
        
        self.test_mode = test_mode       
        self.temperature = temperature    
        self.max_tokens = max_tokens
        self.bot_name = bot_name
        self.timer_duration = timer_duration
        
        self.tasks = {}   
        
    def collectMessage(self,message, user, sender):
        for conversation in self.conversations:
            if conversation.user == user:
                if sender == "gpt":
                    self.logger.chatReply(user, self.bot_name, message)
                    conversation.updateGPT(message)
                    conversation.writeConversation()
                    return
                else:
                    self.logger.userReply(user, message)
                    conversation.updateUser(message)
                    conversation.writeConversation()
                    return
        newConv = ConversationHandler(user, self.bot_name, init_prompt=self.init_prompt)
        newConv.updateUser(message)
        newConv.writeConversation()
        self.conversations.append(newConv)
        self.logger.userReply(user, message)
        
    async def check_command(self, message: str, author):
        if not self.commands_enabled:
            return False
        reply = None
        for command, value in self.commands.items():
            if message.startswith(command) and whitelist[author.name] >= value["perm"]:
                reply = await value["func"](author, message)
            elif message.startswith(command) and whitelist[author.name] < value["perm"]:
                reply = f"I'm sorry {author.name}. I'm afraid can't do that."
                
        if message.startswith("!") and reply == None:
            reply = "Unknown Command."
            
        if not reply == None:
            await author.send(reply)
            return True
        
        
        return False
    
    async def del_conv(self, author, message):
        reply = None
        found_conv = False
        for conversation in self.conversations:
            if conversation.user == author.name:
                found_conv = True
                self.logger.warning(f"Clearing Message Log for {author.name}")
                conversation.deleteConversation()
                del self.conversations[self.conversations.index(conversation)]
                reply = "Conversation deleted"
                break
        if not found_conv:
            conversation = ConversationHandler(author.name, self.bot_name, init_prompt=self.init_prompt)    
            self.logger.warning(f"Clearing Message Log for {author.name}")
            try :
                conversation.deleteConversation()
                reply = "Conversation deleted"
            except FileNotFoundError:
                reply = "Conversation does not exist"
        self.logger.info(reply)
        return reply
    
    async def del_specific_conv(self, author, message):
        reply = None
        found_conv = False
        parts = message.split(sep=" ")
        name = parts[1]
        for conversation in self.conversations:
            if conversation.user == name:
                found_conv = True
                self.logger.warning(f"Clearing Message Log for {name}, requested by: {author.name}")
                conversation.deleteConversation()
                del self.conversations[self.conversations.index(conversation)]
                reply = "Conversation deleted"
                break
        if not found_conv:
            conversation = ConversationHandler(name, self.bot_name, init_prompt=self.init_prompt)    
            self.logger.warning(f"Clearing Message Log for {name}, requested by: {author.name}")
            try:
                conversation.deleteConversation()
                reply = "Conversation deleted"
            except FileNotFoundError:
                reply = "Conversation does not exist"
        self.logger.info(reply)
        return reply
            
    async def load_conv(self, author, message):
        reply = None
        parts = message.split(sep=" ")
        if len(parts) == 2 and whitelist[author.name] >= self.commands["!load_conv"]["perm"]:
            self.logger.warning(f"{author.name} loading conversation {parts[1]}")
            try:
                for conversation in self.conversations:
                    if conversation.user == author.name:
                        conversation.saveConversation()
                        del self.conversations[self.conversations.index(conversation)]
                loadedConv = ConversationHandler.loadConversation(parts[1], parts[2], self.bot_name)
                newConv = ConversationHandler(author.name, self.bot_name, conversation = loadedConv)
                self.conversations.append(newConv)
                reply = "Loaded conversation"
            except FileNotFoundError:
                reply = f"Conversation {parts[1]} not found"
        elif len(parts) == 2 and whitelist[author.name] < self.commands["!load_conv"]["perm"]:
            self.logger.warning(f"{author.name} tried loading conversation {parts[1]}, without neccessary permission")
            reply = f"Please provide a conversation number."
        elif len(parts) > 2:
            self.logger.warning(f"{author.name} loading conversation {parts[1]}_{parts[2]}")
            try:
                for conversation in self.conversations:
                    if conversation.user == author.name:
                        conversation.saveConversation()
                        del self.conversations[self.conversations.index(conversation)]
                loadedConv = ConversationHandler.loadConversation(parts[1], parts[2], self.bot_name)
                newConv = ConversationHandler(author.name, self.bot_name, conversation = loadedConv)
                self.conversations.append(newConv)
                reply = "Loaded conversation"
            except FileNotFoundError:
                reply = f"Conversation {parts[1]}_{parts[2]} not found"
                
        else:
            reply = "Command usage is !load_conv user number"
        self.logger.info(reply)
        
        return reply
                    
    async def list_conv(self, author, message):
        reply = None
        self.logger.warning(f"{author.name} listed all conversations")
        reply = ConversationHandler.listConversations(self.bot_name)
        if reply is None:
            reply = "No conversations Found"
        self.logger.info(reply)
        return reply
                    
    async def toggle_test_mode(self, author, message):
        reply = None
        self.logger.warning(f"{author.name} toggled test_mode")
        self.test_mode= not self.test_mode
        reply = f"Test Mode is now: {self.test_mode}"
        self.logger.info(reply)
        return reply
        
    async def toggle_test_prompt(self, author, message):
        reply = None
        self.logger.warning(f"{author.name} toggled test_test_prompt")
        self.use_test_prompt= not self.use_test_prompt
        self.init_prompt = get_prompt(self.bot_name, self.streamer_name, self.art_styles, self.use_test_prompt)
        reply = f"use_test_prompt is now: {self.use_test_prompt}"
        self.logger.info(reply)
        return reply

    async def set_temp(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning(f"{author.name} changed Temperature")
        self.temperature = parts[1]
        reply = f"Temparature is now: {self.temperature}"
        self.logger.info(reply)
        return reply
        
    async def set_max_tokens(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning(f"{author.name} changed Max Tokens")
        self.max_tokens = parts[1]
        reply = f"Max_tokends is now: {self.max_tokens}"
        self.logger.info(reply)
        return reply
        
    async def set_delay(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning(f"{author.name} changed delay")
        self.timer_duration = parts[1]
        reply = f"Minimum delay is now: {self.timer_duration}"
        self.logger.info(reply)
        return reply
        
    async def get_config(self, author, message):
        reply = None
        self.logger.warning(f"{author.name} requested settings")
        replys = []
        replys.append(f"Bot Name is: {self.bot_name}")
        replys.append(f"Model name is: {self.MODEL_NAME}")
        replys.append(f"Streamer name is: {self.streamer_name}")
        replys.append(f"Art Styles are: {self.art_styles}")
        replys.append(f"Temparature is: {self.temperature}")
        replys.append(f"min Delay is: {self.timer_duration}s")
        replys.append(f"Max Tokens is: {self.max_tokens}")
        replys.append(f"Test Mode is: {self.test_mode}")
        replys.append(f"use_test_prompt is: {self.use_test_prompt}")
        for r in replys[:-1]:
            self.logger.info(r)
            await author.send(r)
        reply = replys[-1]
        self.logger.info(reply)
        return reply
        
    async def repeat_conv(self, author, message):
        reply = None
        for conv in self.conversations:
            self.logger.warning(f"{author.name} asked to get the conversation.")
            if conv.user == author.name:
                replys = []
                for c in conv.conversation:
                    if c["role"] == "system":
                        continue
                    elif c["role"] == "user":
                        replys.append(f"{author.name}: {c['content']}")
                    else:
                        replys.append(f"{self.bot_name}: {c['content']}")
                for r in replys[:-1]:
                    self.logger.info(r)
                    await author.send(r)
                reply = replys[-1]
                self.logger.info(reply)
        if reply == "":
            reply = "Found trailing data, report to Admin"
            self.logger.error(reply)
        if reply == None:
            reply = "No conversation found"
            self.logger.warning(reply)
        return reply
    
    async def help(self, author, message):
        self.logger.warning(f"{author.name} asked for help.")
        reply = "Available Commands: \n"
        for command, value in self.commands.items():
            if whitelist[author.name] >= value["perm"]:
                reply += value["help"] + "\n"
        self.logger.info(reply)
        return reply
    
    async def get_init_prompt(self, author, message):
        reply = None	
        self.logger.warning(f"{author.name} asked for the prompt.")
        for conv in self.conversations:
            if conv.user == author.name:
                prompt = conv.init_prompt
                splits = prompt.split("\n")
                for l in splits[:-1]:
                    self.logger.info(l)
                    await author.send(l)
            reply = splits[-1]
        if reply == None:
            reply = "No prompt found"
        self.logger.info(reply)
        return reply
    
    async def disable_commands(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        
        if len(parts) > 0:
            if parts[1] == self.__admin_pw:
                reply = "DISABLED COMMANDS; THIS CAN NOT BE REVERTED WITHOUT A RESTART"
                self.logger.error(reply)
                self.commands_enabled = False
            else:
                reply = "The Password provided does not match, this event will be reported!"
                self.logger.error(reply)
        else:
            reply = "No Password provided, this event will be reported!"
            self.logger.error(reply)
        return reply

    async def force_load(self, author, message):
        reply = None
        try:
            await self.del_conv(author, message)
            self.conversations.append(ConversationHandler(author.name, self.bot_name, self.init_prompt))
            reply = f"Loaded conversation with {author.name} into memory"
        except FileNotFoundError:
            reply = f"Conversation with {author.name} couldn't be found"
        self.logger.info(reply)
        return reply
    
    async def save_all(self, author, message):
        for c in self.conversations:
            c.saveConversation()
            
    async def shutdown(self, author, message):
        
        await self.save_all(author, message)
        
        exit()
    
    async def messageHandler(self, message):
        user_prompt = message.content
        name = message.author.name
        if await self.check_command(user_prompt, message.author):
            return
        media = message.attachments
        media_amount = len(media)
        if media_amount > 0:
            ConversationHandler.saveMedia(name, media)
            filenames = ""
            for m in media:
                filenames += m.filename +", "
            user_prompt = f"[{media_amount} amazing Media Attachements, namely:{filenames}]\n" + user_prompt
        self.collectMessage(user_prompt, name, "user")
        if len(self.tasks) > 0 and name in self.tasks.keys():
            for task in self.tasks.values():
                if task is not None:
                    for conversation in self.conversations:
                        conversation.appendUserMessage(user_prompt)
                        task.cancel()
           
        self.tasks[name] = asyncio.create_task(self.gpt_sending(message.author, len(message.content)))
        await self.tasks[name]
        
    async def gpt_sending(self,author, message_lenght):
        user = author.name
        if not self.test_mode:
            await asyncio.sleep(random.randint(self.timer_duration ,self.timer_duration + message_lenght)) #wait for further messages
        else: 
            await asyncio.sleep(5)
        for conversation in self.conversations:
            if conversation.user == user:
                if not conversation.awaitingResponse():
                    return
                
                response = openai.ChatCompletion.create(
                    model=self.MODEL_NAME,
                    messages= conversation.conversation,
                    max_tokens=256,  # maximal amout of tokens, one token roughly equates to 4 chars
                    temperature=0.3,  # control over creativity
                    n=1, # amount of answers
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0  
                )

                # Die Antwort aus der response extrahieren
                response_message = response['choices'][0]['message']
                reply = response_message['content']
                # Die Antwort an den Absender der DM zurückschicken
                self.collectMessage(reply,user ,"gpt")
                await author.send(reply)
        
    def runBot(self):
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix='!', intents=intents) 
        
        
        @bot.event
        async def on_ready():
            self.logger.passing(f"Logged in as {bot.user.name}, given name: {self.bot_name}")

        @bot.event
        async def on_message(message):
            if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
                await self.messageHandler(message)
        bot.run(self.__bot_token)
            
    
def test_all(bot : GPTBot):
    l = Logger(True, False)
    message = discord.Message()
    message.author = "Test"
    message.content = ""
    message.channel = discord.DMChannel
    
    for c,v in bot.commands.items():
        message.content = c
        if not v["value_type"] == None:
            if v["value_type"] is str:
                bot.runBot().on_message(message)
                message.content += ADMIN_PASSWORT
                l.info(message.content)
                bot.runBot().on_message(message)
                message.content = c
                message.content += "justsomerandomshit"
            if v["value_type"] is [str,int]:
                message.content += " caesar 0"
                l.info(message.content)
                bot.runBot().on_message(message)
                message.content = c
                message.content += " caesar 100"
                l.info(message.content)
                bot.runBot().on_message(message)
            if v["value_type"] is int:
                l.info(message.content)
                bot.runBot().on_message(message)
                message.content += f" {random.randint(1,20)}"
                l.info(message.content)
                bot.runBot().on_message(message)
            if v["value_type"] is float:
                l.info(message.content)
                bot.runBot().on_message(message)
                message.content += f" {random.random()}"
                l.info(message.content)
                bot.runBot().on_message(message)
        else: 
            l.info(message.content)
            bot.runBot().on_message(message)
    
if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_ALEX, OPENAI_API_KEY, "Alex", "Caesar", test_mode=True, admin_pw=ADMIN_PASSWORT)
    
    bot.runBot()