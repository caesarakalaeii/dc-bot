import asyncio
import random
import discord
from discord.ext import commands
import json
import os
import openai

from promt_creation import get_prompt
from api_secrets import *
from logger import Logger
from queue import Queue

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
    def __init___(self, user, bot_name, conversation):
        self.user = user
        self.bot_name = bot_name
        self.dir_path = "{}_conversations".format(self.bot_name)
        self.file_path = os.path.join(self.dir_path, "{}.json".format(self.user))
        self.conversation = conversation
        
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
        
    def listConversations(bot_name):
        return os.listdir("{}_conversations".format(bot_name))

    def loadConversation(name, number, bot_name):
        dir_path = "{}_conversations".format(bot_name)
        if os.path.exists(os.path.join(dir_path, "{}_".format(name)+ "{}.json".format(number))):
            with open(os.path.join(dir_path, "{}_".format(name)+ "{}.json".format(number)), "r") as f:
                return json.loads(f.read())
        else: 
            raise FileNotFoundError

class GPTBot():
    
    def __init__(self, bot_token, gpt_api_key, bot_name, streamer_name, timer_duration = 300, art_styles = None, test_mode = False, temperature = 0.7, max_tokens = 256, use_test_prompt = False):
        self.conversations = []
        self.__bot_token = bot_token
        self.logger = Logger(True, True)
        openai.api_key = gpt_api_key
        self.MODEL_NAME = "gpt-3.5-turbo"
        self.use_test_prompt = use_test_prompt
        self.art_styles = art_styles
        self.streamer_name = streamer_name
        self.init_prompt = get_prompt(bot_name, streamer_name, art_styles, use_test_prompt)
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
        reply = None
        parts = message.split(sep=" ")
        
        if message.startswith("!delete_conv"):
            for conversation in self.conversations:
                if conversation.user == author.name:
                    self.logger.warning("Clearing Message Log for {}".format(author.name))
                    conversation.deleteConversation()
                    del self.conversations[self.conversations.index(conversation)]
            reply = "Conversation deleted"
            
        elif message.startswith("!load_conv"):
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
                 
        elif message.startswith("!list_conversations"):
            self.logger.warning("{} listed all conversations".format(author.name))
            reply = ConversationHandler.listConversations(self.bot_name)
            if reply is None:
                reply = "No conversations Found"
                
        elif message.startswith("!toggle_testmode"):
            self.logger.warning("{} toggled test_mode".format(author.name))
            self.test_mode= not self.test_mode
            reply = "Test Mode is now: {}".format(self.test_mode)
            self.logger.warning(reply)
            
        elif message.startswith("!toggle_test_prompt"):
            self.logger.warning("{} toggled test_test_prompt".format(author.name))
            self.use_test_prompt= not self.use_test_prompt
            self.init_prompt = get_prompt(self.bot_name, self.streamer_name, self.art_styles, self.use_test_prompt)
            self.base_prompt = {"role": "system", "content": self.init_prompt}
            reply = "use_test_prompt is now: {}".format(self.use_test_prompt)
            self.logger.warning(reply)
        
        elif message.startswith("!set_temperature"):
            self.logger.warning("{} changed Temperature".format(author.name))
            self.temperature = parts[1]
            reply = "Temparature is now: {}".format(self.temperature)
            self.logger.warning(reply)
            
        elif message.startswith("!set_max_token"):
            self.logger.warning("{} changed Temperature".format(author.name))
            self.max_tokens = parts[1]
            reply = "Temparature is now: {}".format(self.max_tokens)
            self.logger.warning(reply)
            
        elif message.startswith("!set_delay"):
            self.logger.warning("{} changed delay".format(author.name))
            self.timer_duration = parts[1]
            reply = "Temparature is now: {}".format(self.timer_duration)
            self.logger.warning(reply)
            
        elif message.startswith("!command_help"):
            self.logger.warning("{} asked for help.".format(author.name))
            reply = """
            The Following commands are available:
            !delete_conv: Deletes this Conversation from bot Memory
            !load_conversation user number: Loads specific Conversation
            !list_conversations: Lists availabe conversations
            WARNING: The following commadns should only be used, when you know exactly what they do, as they are global!
            Ask Caesar if neccesarry!
            !toggle_testmode: toggles testmode for shorter response time. 
            !set_temperature value: Changes temperature
            !set_max_token value: sets the maximal Amount of Tokens used
            !set_delay: will set minimum reply delay
            !toggle_test_prompt: toggles usage of a test prompt
            """
        if not reply == None:
            await author.send(reply)
            return True
        
        return False
    async def messageHandler(self, message):
        user_prompt = message.content
        name = message.author.name
        if await self.check_command(user_prompt, message.author):
            return
        media = message.attachments
        media_amount = len(media)
        if media_amount > 0:
            user_prompt = "[{} amazing Media Attachements] \n".format(media_amount) + user_prompt
        self.collectMessage(user_prompt, name, "user")
        if len(self.tasks) > 0 and name in self.tasks.keys():
            for user, task in self.tasks.items():
                if task is not None:
                    for conversation in self.conversations:
                        
                        conversation.appendUserMessage(message)
                        task.cancel()
           
        self.tasks[name] = await asyncio.create_task(self.gpt_sending(message.author, len(message.content)))
        
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
    bot = GPTBot(DISCORD_TOKEN, OPENAI_API_KEY, "Alex", "Caesar", test_mode=True)
    bot.runBot()