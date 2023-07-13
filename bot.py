import asyncio
import discord
from discord.ext import commands
import os
import openai
from prompt import initial_prompt 
from api_secrets import *
from logger import Logger, UserLogger
from queue import Queue






class GPTBot(discord.Client):
    
    def __init__(self, bot_token, gpt_api_key):
        self.__bot_token = bot_token
        baselog = Logger(True, True)
        openai.api_key = gpt_api_key
        self.MODEL_NAME = "gpt-3.5-turbo"
        self.loggers = {
            "base": baselog
        }
        self.conversationLogs = {
            "base": [
                        {"role": "system", "content": initial_prompt},
                    ]
        }
        self.task = None
        self.message_queue = Queue()
        
        
        
    def collectMessage(self,sendMessage, user, sender):
        if not user in self.loggers.keys():
            self.loggers.update({user: UserLogger(user, True, True)})
        if not user in self.conversationLogs.keys():
            self.conversationLogs.update({user: self.conversationLogs["base"]})
        if sender == "gpt":
            self.loggers[user].chatReply(sendMessage)
            self.conversationLogs[user].append({"role": "assistant", "content": sendMessage})
        else:
            self.loggers[user].userReply(sendMessage)
            self.conversationLogs[user].append({"role": "user", "content": sendMessage})
       
    @asyncio.coroutine        
    async def messageHandler(self, message):
        user_prompt = message.content
        name = message.author.name
        self.collectMessage(user_prompt, name, "user")
        prompt = self.conversationLogs[name]
        await asyncio.sleep(10) #wait for further messages
        response = openai.ChatCompletion.create(
            model=self.MODEL_NAME,
            messages= prompt,
            max_tokens=256,  # maximal amout of tokens, one token roughly equates to 4 chars
            temperature=0.2,  # control over creativity
            n=1, # amount of answers
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0  
        )

        # Die Antwort aus der response extrahieren
        response_message = response['choices'][0]['message']
        reply = response_message['content']
        # Die Antwort an den Absender der DM zurückschicken
        self.collectMessage(reply, name, "gpt")
        await message.author.send(reply)
        self.task = None
        self.temp_message = None
                
        
        
        
    def runBot(self):
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix='!', intents=intents) 
        
        
           
        @bot.event
        async def on_ready():
            self.loggers["base"].passing(f"Angemeldet als {bot.user.name}")

        @bot.event
        async def on_message(message):
            if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
                if self.task is None:
                    self.task = asyncio.create_task(self.messageHandler(message))
                else:
                    self.task.cancel()
                    self.task = asyncio.create_task(self.messageHandler(message))
            await self.task   
        bot.run(self.__bot_token)
            
if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN, OPENAI_API_KEY)
    bot.runBot()