from streamer_collection import streamers
from api_secrets import *
from bot import GPTBot



bots = []
for streamer_name,v in streamers.items():
    bots.append(GPTBot(v.bot_token, OPENAI_API_KEY, v.bot_name, streamer_name))
for bot in bots:
    bot.runBot()