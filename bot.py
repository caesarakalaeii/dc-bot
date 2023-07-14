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
    
    
    def __init__(self, user, init_prompt, bot_name):
        self.user = user
        self.bot_name = bot_name
        self.dir_path = "{}_conversations".format(self.bot_name)
        self.file_path = os.path.join(self.dir_path, "{}.json".format(self.user))
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
        if not os.path.exists(self.file_path):
            os.mkdir(self.dir_path)
        
    def writeConversation(self):
        with open(self.file_path, "w") as f:
            f.write(json.dumps(self.conversation))

                
    def fetchConversation(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                self.conversation = json.loads(f.read())
        else: raise FileNotFoundError


class GPTBot():
    
    def __init__(self, bot_token, gpt_api_key, bot_name, streamer_name, timer_duration = 300, art_styles = None, test_mode = False):
        self.conversations = []
        self.__bot_token = bot_token
        self.logger = Logger(True, True)
        openai.api_key = gpt_api_key
        self.MODEL_NAME = "gpt-3.5-turbo"
        self.init_prompt = get_prompt(bot_name, streamer_name, art_styles, test_mode)
        self.base_prompt = {"role": "system", "content": self.init_prompt}
        self.test_mode = test_mode           
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
        newConv = ConversationHandler(user, self.base_prompt, self.bot_name)
        newConv.updateUser(message)
        newConv.writeConversation()
        self.conversations.append(newConv)
        self.logger.userReply(user, message)
        
        
       
      
    async def messageHandler(self, message):
        user_prompt = message.content
        media = message.attachments
        media_amount = len(media)
        if media_amount > 0:
            user_prompt = "[{} amazing Media Attachements] \n".format(media_amount) + user_prompt
        name = message.author.name
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
    bot = GPTBot(DISCORD_TOKEN, OPENAI_API_KEY, "Alex", "Caesar", timer_duration=30)
    bot.runBot()