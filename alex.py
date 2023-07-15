from bot import GPTBot
from api_secrets import *

if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_ALEX, OPENAI_API_KEY, "Alex", "Caesar", test_mode=True)
    bot.runBot()