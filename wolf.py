from bot import GPTBot
from api_secrets import *

if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_WOLF, OPENAI_API_KEY, "Winston Wolf", "Kangoshi", stream_link="https://twitch.tv/kangoshi_chan", test_mode=True, admin_pw=ADMIN_PASSWORT, max_tokens = 64, temperature= 1)
    bot.runBot()