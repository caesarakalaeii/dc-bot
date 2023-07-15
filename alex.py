from bot import GPTBot
from api_secrets import *

if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_ALEX, OPENAI_API_KEY, "Alex", "Caesar", test_mode=True, admin_pw=ADMIN_PASSWORT)
    bot.runBot()