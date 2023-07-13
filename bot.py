import asyncio
from collections.abc import Callable, Iterable, Mapping
from threading import Timer
import threading
from typing import Any
import discord
from discord.ext import commands
import time
import os
import openai

from promt_creation import get_prompt
from api_secrets import *
from logger import Logger, UserLogger
from queue import Queue



class GPTBot():
    
    def __init__(self, bot_token, gpt_api_key, bot_name, streamer_name, timer_duration = 300, art_styles = None, test_prompt = False):
        self.__bot_token = bot_token
        baselog = Logger(True, True)
        openai.api_key = gpt_api_key
        self.MODEL_NAME = "gpt-3.5-turbo"
        self.loggers = {
            "base": baselog
        }
        self.init_prompt = get_prompt(bot_name, streamer_name, art_styles, test_prompt)
        self.conversationLogs = {
            "base": [
                        {"role": "system", "content": self.init_prompt},
                    ]
        }
        self.bot_name = bot_name
        self.timer_duration = timer_duration
        self.tasks = {}
        
    def awaitingResponse(self, user):
        return self.conversationLogs[user][-1]["role"] == "user"
        
    def collectMessage(self,message, user, sender):
        user = user
        sender = sender
        sendMessage = message
        
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
       
      
    async def messageHandler(self, message):
        user_prompt = message.content
        name = message.author.name
        self.collectMessage(user_prompt, name, "user")
        if len(self.tasks) > 0:
            for user, task in self.tasks.items():
                if task is not None:
                    self.conversationLogs[name][-1]["content"] = self.conversationLogs[name][-1]["content"] + "\n" + user_prompt # this works
                    task.cancel()
        
        self.tasks[name] = await asyncio.create_task(self.gpt_sending(message.author))
        
    async def gpt_sending(self,author):
        user = author.name
        await asyncio.sleep(self.timer_duration) #wait for further messages
        if not self.awaitingResponse(user):
            return
        response = openai.ChatCompletion.create(
            model=self.MODEL_NAME,
            messages= self.conversationLogs[user],
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
        self.collectMessage(reply, user,"gpt")
        await author.send(reply)
        
    def runBot(self):
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix='!', intents=intents) 
        
        
        @bot.event
        async def on_ready():
            self.loggers["base"].passing(f"Logged in as {bot.user.name}, given name: {self.bot_name}")

        @bot.event
        async def on_message(message):
            if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
                await self.messageHandler(message)
        bot.run(self.__bot_token)
            
if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN, OPENAI_API_KEY, "Alex", "Caesar", test_prompt= True, timer_duration=10)
    bot.runBot()