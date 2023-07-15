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
from queue import Queue
from whitelist import whitelist

class ConversationHandler():
    
    
    def __init__(self, user, bot_name , init_prompt = None, conversation = None):
        self.user = user
        self.bot_name = bot_name
        self.dir_path = "{}_conversations".format(self.bot_name)
        self.file_path = os.path.join(self.dir_path, "{}.json".format(self.user))
        if not conversation is None:
            self.conversation = conversation
        else:
            try:
                self.checkDir()
                self.fetchConversation()
            except FileNotFoundError:
                self.conversation = [init_prompt]
    
        
    def awaitingResponse(self):
        return self.conversation[-1]["role"] == "user"
    
    def updateGPT(self, message):
        self.conversation.append({"role": "assistant", "content": message})
        
    def updateUser(self, message):
        self.conversation.append({"role": "user", "content": message})
        
    def appendUserMessage(self, message):
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
            if os.path.exists(os.path.join(self.dir_path, "{}_".format(self.user)+ "{}.json".format(i))):
                continue
            else:
                with open(os.path.join(self.dir_path, "{}_".format(self.user)+ "{}.json".format(i)), "w") as f:
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
        return os.listdir("{}_conversations".format(bot_name))

    def loadConversation(name : str, number, bot_name):
        dir_path = "{}_conversations".format(bot_name)
        if os.path.exists(os.path.join(dir_path, "{}_".format(name)+ "{}.json".format(number))):
            with open(os.path.join(dir_path, "{}_".format(name)+ "{}.json".format(number)), "r") as f:
                return json.loads(f.read())
        else: 
            raise FileNotFoundError
        
    def saveMedia(name : str, medias):
        try:
            os.mkdir(name + "_media")
        except FileExistsError:
            pass
        finally:
            for media in medias:
                if not os.path.exists(os.path.join(name, media.filename)):
                    r = requests.get(media.url, allow_redirects=True)
                    open(os.path.join(name, media.filename), 'wb').write(r.content)
                else:
                    for i in range(100):
                        if not os.path.exists(os.path.join(name, media.filename + "_{}".format(i))):
                            r = requests.get(media.url, allow_redirects=True)
                            open(os.path.join(name, media.filename + "_{}".format(i)), 'wb').write(r.content)
                            break
        

class GPTBot():
    
    
    def __init__(self, bot_token, gpt_api_key, bot_name, 
                 streamer_name, timer_duration = 300, art_styles = None, 
                 test_mode = False, temperature = 0.7, max_tokens = 256, 
                 use_test_prompt = False, commands_enabled = True, admin_pw = None):
        self.conversations = []
        self.commands_enabled = commands_enabled
        self.__admin_pw = admin_pw
        
        self.commands = {
            "!delete_conv": {
                "perm": 5,
                "help": "!delete_conv: Deletes this Conversation from bot Memory",
                "func": self.del_conv
                },
            "!load_conv": {
                "perm": 10,
                "help": "!load_conv user number: Loads specific Conversation",
                "func": self.load_conv
                },
            "!list_conv": {
                "perm": 10,
                "help": "!list_conv: Lists availabe conversations",
                "func": self.list_conv
                },
            "!get_config": {
                "perm": 5,
                "help": "!get_config: returns current configuration",
                "func": self.get_config
                },
            "!repeat_conv": {
                "perm": 5,
                "help": "!repeat_conv: repeats current conversation WARNING: might be a lot! will return nothing when conversation is not in memory",
                "func": self.repeat_conv
                },
            "!toggle_testmode":{
                "perm": 10,
                "help": "!toggle_testmode: toggles testmode for shorter response time.",
                "func": self.toggle_test_mode
                },  
            "!set_temperature": {
                "perm": 10,
                "help": "!set_temperature value: Changes temperature",
                "func": self.set_temp
                },
            "!set_max_token": {
                "perm": 10,
                "help": "!set_max_token value: sets the maximal Amount of Tokens used",
                "func": self.set_max_tokens
                },
            "!set_delay": {
                "perm": 10,
                "help": "!set_delay value: will set minimum reply delay",
                "func": self.set_delay
                },
            "!toggle_test_prompt": {
                "perm": 10,
                "help": "!toggle_test_prompt: toggles usage of a test prompt",
                "func": self.toggle_test_prompt
                },
            "!get_init_prompt": {
                "perm": 15,
                "help": "!get_init_prompt: returns initial prompt of this conversation",
                "func": self.get_init_prompt
                },
            "!command_help":{
                "perm": 1,
                "help": "!command_help: returns all available commands",
                "func": self.help
                },
            "!disable_commands":{
                "perm": 10,
                "help": "!disable_commands passwort: disables all commands until restart, passwort is set in api_secrets.py",
                "func": self.disable_commands
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
        self.init_prompt = get_prompt(bot_name, streamer_name, self.art_styles, use_test_prompt)
        self.base_prompt = {"role": "system", "content": self.init_prompt}
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
                    self.logger.chatReply(user,message)
                    conversation.updateGPT(message)
                    conversation.writeConversation()
                    return
                else:
                    self.logger.userReply(user, message)
                    conversation.updateUser(message)
                    conversation.writeConversation()
                    return
        newConv = ConversationHandler(user, self.bot_name, init_prompt=self.base_prompt)
        newConv.updateUser(message)
        newConv.writeConversation()
        self.conversations.append(newConv)
        self.logger.userReply(user, message)
        
    
    
    
    async def check_command(self, message: str, author):
        if not self.commads_enabled:
            return False
        reply = None
        for command, value in self.commands.items():
            if message.startswith(command) and whitelist[author.name] >= value["perm"]:
                reply = await value["func"](author, message)
            elif message.startswith(command) and whitelist[author.name] < value["perm"]:
                reply = "I'm sorry {}. I'm afraid can't do that.".format(author.name)
                
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
                self.logger.warning("Clearing Message Log for {}".format(author.name))
                conversation.deleteConversation()
                del self.conversations[self.conversations.index(conversation)]
                reply = "Conversation deleted"
                break
        if not found_conv:
            conversation = ConversationHandler(author.name, self.bot_name)    
            self.logger.warning("Clearing Message Log for {}".format(author.name))
            conversation.deleteConversation()
            reply = "Conversation deleted"
        return reply
            
    async def load_conv(self, author, message):
        reply = None
        parts = message.split(sep=" ")
        self.logger.warning("{} loaded conversation ".format(author.name)+"{}".format(parts[1])+"_{}".format(parts[2]))
        try:
            for conversation in self.conversations:
                if conversation.user == author.name:
                    conversation.saveConversation()
                    del self.conversations[self.conversations.index(conversation)]
            loadedConv = ConversationHandler.loadConversation(parts[1], parts[2], self.bot_name)
            newConv = ConversationHandler(author.name, self.bot_name, conversation = loadedConv)
            self.conversations.append(newConv)
            reply = "Loaded conversation"
            self.logger.warning(reply)
        except FileNotFoundError:
            reply = "Conversation {} not found".format(parts[1])
            self.logger.warning(reply)
        return reply
                    
    async def list_conv(self, author, message):
        reply = None
        self.logger.warning("{} listed all conversations".format(author.name))
        reply = ConversationHandler.listConversations(self.bot_name)
        if reply is None:
            reply = "No conversations Found"
        return reply
                    
    async def toggle_test_mode(self, author, message):
        reply = None
        self.logger.warning("{} toggled test_mode".format(author.name))
        self.test_mode= not self.test_mode
        reply = "Test Mode is now: {}".format(self.test_mode)
        self.logger.warning(reply)
        return reply
        
    async def toggle_test_prompt(self, author, message):
        reply = None
        self.logger.warning("{} toggled test_test_prompt".format(author.name))
        self.use_test_prompt= not self.use_test_prompt
        self.init_prompt = get_prompt(self.bot_name, self.streamer_name, self.art_styles, self.use_test_prompt)
        self.base_prompt = {"role": "system", "content": self.init_prompt}
        reply = "use_test_prompt is now: {}".format(self.use_test_prompt)
        self.logger.warning(reply)
        return reply

    async def set_temp(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning("{} changed Temperature".format(author.name))
        self.temperature = parts[1]
        reply = "Temparature is now: {}".format(self.temperature)
        self.logger.warning(reply)
        return reply
        
    async def set_max_tokens(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning("{} changed Temperature".format(author.name))
        self.max_tokens = parts[1]
        reply = "Max_tokends is now: {}".format(self.max_tokens)
        self.logger.warning(reply)
        return reply
        
    async def set_delay(self, author, message):
        parts = message.split(sep=" ")
        reply = None
        self.logger.warning("{} changed delay".format(author.name))
        self.timer_duration = parts[1]
        reply = "Minimum delay is now: {}".format(self.timer_duration)
        self.logger.warning(reply)
        return reply
        
    async def get_config(self, author, message):
        reply = None
        self.logger.warning("{} requested settings".format(author.name))
        reply = "\nBot Name is: {}".format(self.bot_name)
        reply += "\nModel name is: {}".format(self.MODEL_NAME)
        reply += "\nStreamer name is: {}".format(self.streamer_name)
        reply += "\nArt Styles are: {}".format(self.art_styles)
        reply += "\nTemparature is: {}".format(self.temperature)
        reply += "\nmin Delay is: {}s".format(self.timer_duration)
        reply += "\nMax Tokens is: {}".format(self.max_tokens)
        reply += "\nTest Mode is: {}".format(self.test_mode)
        reply += "\nuse_test_prompt is: {}".format(self.use_test_prompt)
        self.logger.warning(reply)
        for r in reply.split("\n"):
            await author.send(r)
        reply = "\n Config ended."
        return reply
        
    async def repeat_conv(self, author, message):
        reply = None
        for conv in self.conversations:
            self.logger.warning("{} asked to get the conversation.".format(author.name))
            if conv.user == author.name:
                for c in conv.conversation:
                    if c["role"] == "system":
                        continue
                    elif c["role"] == "user":
                        t = "{}: ".format(author.name)+"{}".format(c["content"])
                        await author.send(t)
                    else:
                        t = "{}: ".format(self.bot_name)+"{}".format(c["content"])
                        await author.send(t)
        reply = "Conversation Ended"
        return reply
    
    async def help(self, author, message):
        self.logger.warning("{} asked for help.".format(author.name))
        reply = "Available Commands: \n"
        for command, value in self.commands.items():
            if whitelist[author.name] >= value["perm"]:
                reply += value["help"] + "\n"
        return reply
    
    async def get_init_prompt(self, author, message):
        reply = None	
        self.logger.warning("{} asked for the prompt.".format(author.name))
        for conv in self.conversations:
            if conv.user == author.name:
                conv.conversation[0]
        
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

    async def force_load():
        reply = None
        #fetches configbased on author name
        return reply
    
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
            user_prompt = "[{} amazing Media Attachements, namely:".format(media_amount) + "{}]\n".format(filenames) + user_prompt
        self.collectMessage(user_prompt, name, "user")
        if len(self.tasks) > 0 and name in self.tasks.keys():
            for user, task in self.tasks.items():
                if task is not None:
                    for conversation in self.conversations:
                        conversation.appendUserMessage(message)
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
            
if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_ALEX, OPENAI_API_KEY, "Alex", "Caesar", test_mode=True, admin_pw=ADMIN_PASSWORT)
    bot.runBot()