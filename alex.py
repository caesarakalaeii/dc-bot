from bot import GPTBot
from api_secrets import *

if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_ALEX, OPENAI_API_KEY, "Alex", "Caesar", stream_link = "https://twitch.tv/caesarlp", test_mode=False, admin_pw=ADMIN_PASSWORT, max_tokens = 64, temperature= 1)
    bot.runBot()