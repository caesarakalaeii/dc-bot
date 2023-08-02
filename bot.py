import asyncio
import random
import time
import discord
from discord.ext import commands
import json
import os
import openai
import requests

from promt_creation import get_prompt, get_art_styles
from receipt_creation import image_creation
from api_secrets import *
from logger import Logger

class ConversationHandler():
    
    
    def __init__(self, user, bot_name , init_prompt = None, conversation = None, author = None):
        self.user = user
        self.bot_name = bot_name
        self.dir_path = f"{self.bot_name}_conversations"
        self.file_path = os.path.join(self.dir_path, f"{self.user}.json")
        self.init_prompt = init_prompt
        self.author = author
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
        if number == None:
            if os.path.exists(os.path.join(dir_path, f"{name}.json")):
                with open(os.path.join(dir_path, f"{name}.json"), "r") as f:
                    return json.loads(f.read())
            else: 
                raise FileNotFoundError
        else:
            if os.path.exists(os.path.join(dir_path, f"{name}_{number}.json")):
                with open(os.path.join(dir_path, f"{name}_{number}.json"), "r") as f:
                    return json.loads(f.read())
            else: 
                raise FileNotFoundError
            
    def saveMedia(name : str, medias):
        dir_path = f"{name}_media"
        try:
            os.makedirs(dir_path, exist_ok=True)  # Create directory if it doesn't exist
        except OSError as e:
            print(f"Error creating directory: {e}")
            return

        for media in medias:
            file_path = os.path.join(dir_path, media.filename)
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
                    file_path = os.path.join(dir_path, new_name)
                    if not os.path.exists(file_path):
                        try:
                            r = requests.get(media.url, allow_redirects=True)
                            with open(file_path, 'wb') as file:
                                file.write(r.content)
                            break
                        except Exception as e:
                            print(f"Error saving media: {e}")
                            break
                    i+=1
        

class QueueItem():
    message : discord.Message
    timestamp : float
    
    def __init__(self, message: discord.Message) -> None:
        self.message = message
        self.timestamp = time.time()

class GPTBot():
    'TODO get type defs going'
    queue: asyncio.Queue
    
    
    def __init__(self, bot_token = None, gpt_api_key = None, bot_name = None,
                 channel_id = None, guild_id = None,
                 streamer_name = None, timer_duration = 300, art_styles = None, 
                 test_mode = False, temperature = 0.7, max_tokens = 256, 
                 use_test_prompt = False, commands_enabled = True, admin_pw = None,
                 stream_link = None, debug = False):
        self.conversations = []
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.commands_enabled = commands_enabled
        self.__admin_pw = admin_pw
        self.bot = None
        self.debug = debug
        self.commands = {
            "!delete_conv": {
                "perm": 5,
                "help": "!delete_conv: Deletes this Conversation from bot Memory",
                "value_type": None,
                "func": self.del_conv
                },
            "!load_conv": {
                "perm": 10,
                "help": '!load_conv "user" ["number"]: Loads specific Conversation',
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
            "!del_specific":{
                "perm":10,
                "help":'!del_specific "user": deletes conversation log of specific user from memory',
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
                },
            "!get_msg_log":{
                "perm": 10,
                "help": "!get_msg_log user_id: Returns all DMs by user",
                "value_type": int,
                "func": self.getMessageLog
            },
            "!force_resend":{
                "perm": 10,
                "help": '!force_resend "name" ["message"]: Tries to send last message or specified message',
                "value_type": str,
                "func": self.resendMsg
            },
            "!load_author":{
                "perm": 10,
                "help": "!load_author user_id: Tries to load author by ID, load conversation first!",
                "value_type": int,
                "func": self.loadAuthor
            },
            "!clear_memory":{
                "perm": 10,
                "help": "!clear_memory: clears conversations from memory, while retaining .jsons unchanged",
                "value_type": None,
                "func": self.clearMemory
            },
            "!ban":{
                "perm": 15,
                "help": "!ban user_id: Bans user_id from interacting with bot",
                "value_type": int,
                "func": self.ban
            },
            "!unban":{
                "perm": 15,
                "help": "!unban user_id: Unbans user_id from interacting with bot",
                "value_type": int,
                "func": self.unban
            },
            "!whitelist":{
                "perm": 15,
                "help": '!whitelist "user" "value": whitelists user with permission value 1-15, to deactivate commands set value to 0',
                "value_type": [str, int],
                "func": self.whitelist
            },
            "!reload_whitelist":{
                "perm": 15,
                "help": "!reload_whitelist: reloads whitelist from disk",
                "value_type": None,
                "func": self.reload_whitelist
            },
            "!reload_blacklist":{
                "perm": 15,
                "help": "!reload_blacklist: reloads blacklist from disk",
                "value_type": None,
                "func": self.reload_blacklist
            },
            "!init_conv":{
                "perm": 10,
                "help": '!init_conv "user" "id" "message": Initializes conversation with message to user with id',
                "value_type": [str, int, str],
                "func": self.init_conv
            },
            "!fake_receipt":{
                "perm": 10,
                "help": '!fake_receipt "user" "id" "store name" "amount": Fakes a PayPal receipt for the given Store name and Amount (Currently only in german)',
                "value_type": [str, int, str, int],
                "func": self.fake_receipt
            }
            
            
        }
        self.__bot_token = bot_token
        self.authors = []
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
        self.conv_data = "something"
        self.test_mode = test_mode       
        self.temperature = temperature    
        self.max_tokens = max_tokens
        self.bot_name = bot_name
        self.timer_duration = timer_duration
        loaded_black = self.load_blacklist()
        self.black_list = loaded_black
        loaded_white = self.load_whitelist()
        self.white_list = loaded_white
        self.threads = self.loadThreads()
        self.tasks = {}   
        self.queue = asyncio.Queue()
    
    '''Utility methods'''
        
    async def collectMessage(self,message, author, sender, files = None):
        user = author.name
        for conversation in self.conversations:
            if conversation.user == user:
                if conversation.author == None:
                    conversation.author == author
                if sender == "gpt":
                    self.logger.chatReply(user, self.bot_name, message)
                    for thread in self.threads:
                        if user in thread.keys():
                            await self.replyToThread(thread[user]["thread_id"], message, files, sender)
                    conversation.updateGPT(message)
                    conversation.writeConversation()
                    return
                else:
                    self.logger.userReply(user, message)
                    for thread in self.threads:
                        if user in thread.keys():
                            await self.replyToThread(thread[user]["thread_id"], message, files, author)
                    conversation.updateUser(message)
                    conversation.writeConversation()
                    return
        newConv = ConversationHandler(user, self.bot_name, init_prompt=self.init_prompt, author = author)
        newConv.updateUser(message)
        newConv.writeConversation()
        thread_id = None
        self.conversations.append(newConv)
        self.logger.userReply(user, message)
        for thread in self.threads:
            if user in thread.keys():
                thread_id = thread[user]["thread_id"]
        if thread_id is None:       
            thread = await self.createThread(author)
            thread_id = thread.id
        await self.replyToThread(thread_id, message, files, author)
    
    async def messageHandler(self, message):
        user_prompt, author, files = await self.unpackMessage(message)
        name = author.name
        if f"{author.id}" in self.black_list:
            await author.send("You have no power here!")
            return
        if await self.check_command(message):
            return
        media_amount = len(files)
        if media_amount > 0:
            ConversationHandler.saveMedia(name,message.attachments)
            filenames = ""
            for m in files:
                filenames += m.filename +", "
            user_prompt = f"[{media_amount} amazing Media Attachements, namely:{filenames}]\n" + user_prompt
        await self.collectMessage(user_prompt, author, "user", files)
        for conversation in self.conversations:
            if conversation.user == name:
                conversation.appendUserMessage(user_prompt)

        await self.queue.put(QueueItem(message))
        await self.gpt_sending()

    async def gpt_sending(self):
        
        q= await self.queue.get()
        author = q.message.author
        for conversation in self.conversations:
            if conversation.user == author.name:
                if not conversation.awaitingResponse():
                    return
                messages = [] #Kinda useless but also nice
                message = ""
                
                reversed_conv = conversation.conversation.copy()
                reversed_conv.reverse()
                for c in reversed_conv:
                    if c["role"] == "user":
                        messages.append(c["content"])
                    else:
                        break
                messages.reverse()
                for m in messages:
                    message += f"\n{m}"
                message_lenght = len(message)
                age = int(time.time()-q.timestamp)
                
                    
                if not self.test_mode:
                    async with author.typing():
                        if not age > self.timer_duration:
                            await asyncio.sleep(random.randint(self.timer_duration - age,self.timer_duration + message_lenght - age)) #wait for further messages
                        else:
                            async with author.typing():
                                await asyncio.sleep(5)
                else: 
                    async with author.typing():
                        await asyncio.sleep(5)
                messages= conversation.conversation
                if len(messages) > 20:
                    old = messages
                    messages = [old[0]]
                    for m in old[-20:]:
                        messages.append(m)
                
                response = openai.ChatCompletion.create(
                    model=self.MODEL_NAME,
                    messages= messages,
                    max_tokens=self.max_tokens,  # maximal amout of tokens, one token roughly equates to 4 chars
                    temperature=self.temperature,  # control over creativity
                    n=1, # amount of answers
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0  
                )

                # Die Antwort aus der response extrahieren
                response_message = response['choices'][0]['message']
                reply = response_message['content']
                # Die Antwort an den Absender der DM zurückschicken
                await self.collectMessage(reply,author ,"gpt")
                if self.debug:
                    self.logger.info(f"Reply: {reply}")
                else:
                    await author.send(reply)
                self.queue.task_done()
       
    async def gpt_sending_user(self,author):
        user = author.name
        for conversation in self.conversations:
            if conversation.user == user:
                if not conversation.awaitingResponse():
                    return
                messages= conversation.conversation
                if len(messages) > 20:
                    old = messages
                    messages = [old[0]]
                    for m in old[-20:]:
                        messages.append(m)
                
                response = openai.ChatCompletion.create(
                    model=self.MODEL_NAME,
                    messages= messages,
                    max_tokens=self.max_tokens,  # maximal amout of tokens, one token roughly equates to 4 chars
                    temperature=self.temperature,  # control over creativity
                    n=1, # amount of answers
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0  
                ) 
                # Die Antwort aus der response extrahieren
                response_message = response['choices'][0]['message']
                reply = response_message['content']
                # Die Antwort an den Absender der DM zurückschicken
                await self.collectMessage(reply,author ,"gpt")
                if self.debug:
                    self.logger.info(f"Reply: {reply}")
                else:
                    await author.send(reply)
              
        
    async def replyToThread(self, thread_id, message, files = None, sender = None):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            thread = None
            for existing_thread in channel.threads:
                if existing_thread.id == thread_id:
                    thread = existing_thread
                    break

            if thread:
                reply = ""
                if sender == "gpt":
                    reply = f"{self.bot_name} replys: {message}"
                else:
                    reply = f"{sender.name} says: {message}"
                if files is None:
                    len_files = 0
                else:
                    len_files = len(files)
                self.logger.passing(f'Send reply: "{reply}" with {len_files} files')
                await thread.send(reply, files= files)
            else:
                self.logger.fail(f"Thread with {thread_id} not found in channel {self.channel_id} of guild {self.guild_id}")
       
    async def check_command(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        
        if not self.commands_enabled:
            return False
        reply = None
        try:
            for command, value in self.commands.items():
                if message.startswith(command) and int(self.white_list[author.name]) > 15:
                    self.logger.warning(f"{author.name} invoked {command} with too much permissions")
                    reply = "Bruh"
                elif message.startswith(command) and int(self.white_list[author.name]) >= value["perm"]:
                    reply = await value["func"](message_object)
                elif message.startswith(command) and int(self.white_list[author.name]) < value["perm"]:
                    reply = f"I'm sorry {author.name}. I'm afraid can't do that."
                    self.logger.warning(f"{author.name} invoked {command} without neccessary permissions")
                elif self.white_list[author.name] == "0":
                    self.logger.warning(f"{author.name} invoked {command} with 0 permissions")
                    return True
            if message.startswith("!") and reply == None:
                reply = "Unknown Command."
        except KeyError:
            return False
        if not reply == None:
            await author.send(reply)
            return True
        
        
        return False
        
    def handleArgs(self, message:str):
        message_splits = message.split(sep=" ")
        handling_name = False
        handling_value = False
        name = ""
        value = ""
        values = []
        for s in message_splits:
            if s.endswith('"') and handling_value:
                value +=" " + s.replace('"', '')
                values.append(value)
                value = ""
                continue
            elif s.startswith('"') and handling_name:
                handling_value = True
                value += s.replace('"', '')
                if s.endswith('"'):
                    values.append(value)
                    value = ""
                continue
            elif handling_value:
                value += " "+s
            elif handling_name:
                if s.endswith('"'):
                    name +=" " + s.replace('"', '')
                    continue
                name += " "+s
            elif s.startswith('"') and not handling_value:
                handling_name = True
                if s.endswith('"'):
                    name = s.replace('"', '')
                    continue
                name += s.replace('"', '')
            continue
            
                
        return name, values
        
    def load_blacklist(self):
        if os.path.exists("blacklist.json"):
            with open("blacklist.json", "r") as f:
                return json.loads(f.read())
        else: 
            return []
    
    def write_blacklist(self):
        if os.path.exists("blacklist.json"):
            with open("blacklist.json", "w") as f:
                f.write(json.dumps(self.black_list))
        else: 
            raise FileNotFoundError
       
    def load_whitelist(self):
        if os.path.exists("whitelist.json"):
            with open("whitelist.json", "r") as f:
                return json.loads(f.read())
        else: 
            return []
        
    def write_whitelist(self):
    
        if os.path.exists("whitelist.json"):
            with open("whitelist.json", "w") as f:
                f.write(json.dumps(self.white_list))
        else: 
            raise FileNotFoundError
      
    def clcMem(self):
        for c in self.conversations:
            del self.conversations[self.conversations.index(c)]
        self.logger.error("Memory cleared") 
       
    def loadThreads(self):
        if os.path.exists("threads.json"):
            with open("threads.json", "r") as f:
                return json.loads(f.read())
        else: 
            return []
    
    def writeThreads(self):
        with open("threads.json", "w") as f:
            f.write(json.dumps(self.threads))
      
    def runBot(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        bot = discord.Client(intents=intents) 
        
        self.bot = bot
        
        @bot.event
        async def on_ready():
            self.logger.passing(f"Logged in as {bot.user.name}, given name: {self.bot_name}")

        @bot.event
        async def on_message(message):
            if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
                await self.messageHandler(message)
        bot.run(self.__bot_token)
        
    async def createThread(self, author):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            name = author.name
            id  = author.id
            thread = await channel.create_thread(name=f"{name} ({id})")
            self.threads.append({
                name : {
                    "author_id":id,
                    "thread_id":thread.id
                }
            })
            self.writeThreads()
            return thread   
         
    '''Command Methods'''
    
    
    async def help(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        self.logger.warning(f"{author.name} asked for help.")
        reply = "Available Commands: \n"
        for command, value in self.commands.items():
            if int(self.white_list[author.name]) >= value["perm"]:
                reply += value["help"] + "\n"
        self.logger.info(reply)
        return reply
  
    
    async def ban(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        splits = message.split(" ")
        if len(splits) <2:
            reply = "no user_id provided"
        else:
            self.black_list.append(splits[1])
            self.write_blacklist()
            self.logger.warning(f"{author.name} banned user with id {splits[1]}")
            reply = f"user with id {splits[1]} is now banned"
        
        return reply
    
    async def unban(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        splits = message.split(" ")
        if len(splits) <2:
            reply = "no user_id provided"
        else:
            del self.black_list[self.black_list.index(splits[1])]
            self.write_blacklist()
            self.logger.warning(f"{author.name} unbanned user with id {splits[1]}")
            reply = f"user with id {splits[1]} is now unbanned"
        
        return reply
    
    async def reload_blacklist(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        
        self.black_list = self.load_blacklist()
        self.logger.warning(f"{author.name} reloaded blacklist with values {self.black_list}")
        return f"Blacklist loaded with values {self.black_list}"
    
    
    async def whitelist(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        splits = message.split(" ")
        if len(splits) <3:
            reply = "no user and/or value provided"
        else:
            name, value = self.handleArgs(message)
            self.white_list.update({name: int(value[0])})
            self.write_whitelist()
            self.logger.warning(f"{author.name} whitelisted {name} with {value}")
            reply = f"{name} is now whitelisted with {value}"

        
        return reply
    
    async def reload_whitelist(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        
        self.black_list = self.load_whitelist()
        self.logger.warning(f"{author.name} reloaded whitelist with values {self.white_list}")
        return f"Whitelist loaded with values {self.white_list}"
   
    
    async def init_conv(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        name, values = self.handleArgs(message)
        self.logger.warning(f"{author.name} tries to initialze conversation")
        
        if len(values) >= 2:
            await self.load_conv(message_object, force=True)
            await self.loadAuthor(message_object, id = values[0])
            send = values[1]
            await self.resendMsg(message_object)
            reply = f"Initialized conversation with {name} with id {values[0]}.\nMessage is: {send}"
        else:
            reply = "Too little information to initialize conversation"
        self.logger.info(reply)
        return reply
    
    async def del_conv(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        found_conv = False
        for conversation in self.conversations:
            if conversation.user == author.name:
                found_conv = True
                self.logger.warning(f"Clearing Message Log for {author.name}")
                conversation.saveConversation()
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
   
    async def del_specific_conv(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        found_conv = False
        name, values = self.handleArgs(message)
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
            
    async def load_conv(self, message_object, force = False):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        name, values = self.handleArgs(message)
        if len(values) >= 0 and int(self.white_list[author.name]) >= self.commands["!load_conv"]["perm"]:
            self.logger.warning(f"{author.name} loading conversation {name}")
            try:
                for conversation in self.conversations:
                    if conversation.user == name:
                        conversation.saveConversation()
                        del self.conversations[self.conversations.index(conversation)]
                loadedConv = ConversationHandler.loadConversation(name, None, self.bot_name)
                newConv = ConversationHandler(author.name, self.bot_name, conversation = loadedConv)
                self.conversations.append(newConv)
                loadedConv = ConversationHandler(name, self.bot_name, conversation = loadedConv)
                self.conversations.append(loadedConv)
                reply = "Loaded conversation"
            except FileNotFoundError:
                if force:
                    loadedConv = ConversationHandler(name, self.bot_name, init_prompt=self.init_prompt)
                    self.conversations.append(loadedConv)
                    reply = f"Fake loaded conversation {name}"
                else:
                    reply = f"Conversation {name} not found"
        elif len(values) == 0 and int(self.white_list[author.name]) < self.commands["!load_conv"]["perm"]:
            self.logger.warning(f"{author.name} tried loading conversation {name}, without neccessary permission")
            reply = f"Please provide a conversation number."
        elif len(values) > 1:
            self.logger.warning(f"{author.name} loading conversation {name}_{values[0]}")
            try:
                for conversation in self.conversations:
                    if conversation.user == author.name:
                        conversation.saveConversation()
                        del self.conversations[self.conversations.index(conversation)]
                loadedConv = ConversationHandler.loadConversation(name, values[0], self.bot_name)
                newConv = ConversationHandler(author.name, self.bot_name, conversation = loadedConv)
                self.conversations.append(newConv)
                loadedConv = ConversationHandler(name, self.bot_name, conversation = loadedConv)
                self.conversations.append(loadedConv)
                reply = "Loaded conversation"
            except FileNotFoundError:
                reply = f"Conversation {name}_{values[0]} not found"
                
        else:
            reply = 'Command usage is !load_conv "user" "number"'
        self.logger.info(reply)
        
        return reply
                    
    async def list_conv(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        self.logger.warning(f"{author.name} listed all conversations")
        reply = ConversationHandler.listConversations(self.bot_name)
        if reply is None:
            reply = "No conversations Found"
        self.logger.info(reply)
        return reply
   
    async def repeat_conv(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        splits = message.split(" ")
        name = author.name
        if len(splits) >= 2:
            name = splits[1]
        for conv in self.conversations:
            self.logger.warning(f"{author.name} asked to get the conversation.")
            if conv.user == author.name:
                replys = []
                for c in conv.conversation:
                    if c["role"] == "system":
                        continue
                    elif c["role"] == "user":
                        replys.append(f"{name}: {c['content']}")
                    else:
                        replys.append(f"{self.bot_name}: {c['content']}")
                for r in replys[:-1]:
                    self.logger.info(r)
                    await author.send(r)
                    asyncio.sleep(1)
                reply = replys[-1]
                self.logger.info(reply)
        if reply == "":
            reply = "Found trailing data, report to Admin"
            self.logger.error(reply)
        if reply == None:
            reply = "No conversation found"
            self.logger.warning(reply)
        return reply
    
    async def loadAuthor(self, message_object, id = None):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        found_author = False
        parts = message.split(" ")
        if not id is None:
            parts[1] = id
        if len(parts) >= 2:
            self.logger.warning(f"{author.name} requested to load author with ID {parts[1]}")
            target_user = await self.bot.fetch_user(int(parts[1]))
            if target_user == None:
                reply = f"Loading author failed"
            else:
                for c in self.conversations:
                    if c.user == target_user.name:
                        c.author = target_user
                        found_author = True
                        break
                if not found_author:
                    reply = "Author not found/Conversation not found"
                else: reply = "Author found and loaded"
                
        elif len(parts) < 2:
            reply = "No ID provided"
        self.logger.warning(reply)
        return reply
    
                    
    async def toggle_test_mode(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        self.logger.warning(f"{author.name} toggled test_mode")
        self.test_mode= not self.test_mode
        reply = f"Test Mode is now: {self.test_mode}"
        self.logger.info(reply)
        return reply
        
    async def toggle_test_prompt(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        self.logger.warning(f"{author.name} toggled test_test_prompt")
        self.use_test_prompt= not self.use_test_prompt
        self.init_prompt = get_prompt(self.bot_name, self.streamer_name, self.art_styles, self.use_test_prompt)
        reply = f"use_test_prompt is now: {self.use_test_prompt}"
        self.logger.info(reply)
        return reply

    async def set_temp(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning(f"{author.name} changed Temperature")
        self.temperature = float(parts[1])
        reply = f"Temparature is now: {self.temperature}"
        self.logger.info(reply)
        return reply
        
    async def set_max_tokens(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning(f"{author.name} changed Max Tokens")
        self.max_tokens = int(parts[1])
        reply = f"Max_tokends is now: {self.max_tokens}"
        self.logger.info(reply)
        return reply
        
    async def set_delay(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning(f"{author.name} changed delay")
        self.timer_duration = int(parts[1])
        reply = f"Minimum delay is now: {self.timer_duration}"
        self.logger.info(reply)
        return reply
        
    async def get_config(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
  
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
        
    async def clearMemory(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = f"{author.name} cleared memory"
        self.logger.warning(f"{author.name} cleared memory")
        self.clcMem()
        return reply
    
    async def get_init_prompt(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
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
    
    async def disable_commands(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
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
    
    async def save_all(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        self.logger.warning(f"{author.name} requested to save all conversations.")
        if len(self.conversations) > 0:
            for c in self.conversations:
                c.saveConversation()
            reply = "Saved all conversations"
        else:
            reply = "No conversations in memory"
        self.logger.info(reply)
        return reply
            
    async def shutdown(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        self.logger.error(f"{author.name} initiated shutdown, saving conversations.")
        await self.save_all(message_object)
        self.logger.error("Saved conversations.\nShutting down.")
    
        exit()
    
    async def getMessageLog(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        reply = None
        splits = message.split(" ")
        if not bot == None:
            
            target_user = self.bot.get_user(int(splits[1]))
            if target_user:
                self.logger.warning(f'Fetching DMs from {target_user.name} ({target_user.id}), requested by {author.name}')
                self.logger.info('------')
                # Fetch the DM channel between the bot and the target user
                dm_channel = target_user.dm_channel or await target_user.create_dm()
                # Fetch all messages from the DM channel
                messages = []
                async for message in dm_channel.history(limit=None):
                    messages.append(message)
                for m in messages:
                    reply = (f"{m.author.name} ({m.author.id}): {m.content}")
                    self.logger.info(reply)
                    await author.send(reply)
            else:
                reply = f'Unable to find user with ID {splits[1]}'
                self.logger.warning(reply)
        if reply == None:
            reply = "Bot not initialized, How did we get here?"
            self.logger.warning(reply)
        return reply
    
    async def resendMsg(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        if len(files) == 0:
            files = None
        fetch_last_message = False
        name, values = self.handleArgs(message)
        reply = None
        if len(values) > 0:
            reply = ""
            self.logger.warning("Sending User defined Message")
            if len(values) >1:
                reply = values[1]
            else:
                reply = values[0]
            for c in self.conversations:
                if c.user == name:
                    await self.collectMessage(reply, c.author, "gpt", files)
                    await c.author.send(reply, files=files)
                    return "Sending User defined Message"
        elif len(values) == 0:
            fetch_last_message = True
        else:
            reply = "No Arguments given!"
            return reply
        self.logger.warning(f"{author.name} requested resend to {name}")
        for c in self.conversations:
            if c.user == name:
                if fetch_last_message:
                    last_conv = c.conversation[-1]
                    if last_conv["role"] == "user":
                        self.gpt_sending_user(c.author)
                        return "Requested new Message from GPT"
                    else:
                        reply = last_conv["content"]
                        
                        
                if not c.author == None:
                    self.logger.warning("Resending Message")
                    await self.collectMessage(reply, c.author, "user")
                    await c.author.send(reply)
                    for u,t in self.tasks.items():
                        t.cancel()
                    return "Resending Message"
                    
                if c.author == None:
                    reply = "User has no Author."
                    self.logger.warning(reply)
                    return reply
        reply = "Conversation not found."
        self.logger.warning(reply)
        return reply
  
    async def unpackMessage(self, message_object):
        files = []
        attachments = message_object.attachments
        
        for a in attachments:
            files.append(await a.to_file())
        return message_object.content, message_object.author, files
    
    async def fake_receipt(self, message_object):
        message, author, files = await self.unpackMessage(message_object)
        name, values = self.handleArgs(message)
        user_id = values[0]
        store_name = values[1]
        amount = values[2]
        target_user = await self.bot.fetch_user(user_id)
        file = image_creation(amount,store_name)
        file_size=file.fp.__sizeof__()
        self.logger.warning(f"Sending Fake receipt to {name}\n store name: {store_name}, amount: {amount}, file_size: {file_size}")
        chat_reply = "Here is the PayPal receipt:"
        await self.collectMessage(chat_reply, target_user, "gpt", [file])
        await target_user.send(chat_reply, files=[file])
        return "Send faked receipt"

   
        
    
#Not actually Used    
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
    bot = GPTBot(bot_token=DISCORD_TOKEN_ALEX, gpt_api_key=OPENAI_API_KEY, bot_name="Alex", channel_id=1129125304993067191,guild_id=877203185700339742, streamer_name="Caesar", test_mode=True, admin_pw=ADMIN_PASSWORT, debug=True)
    
    bot.runBot()