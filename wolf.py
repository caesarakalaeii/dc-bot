from bot import GPTBot
from api_secrets import *

if __name__ == '__main__':
    bot = GPTBot(DISCORD_TOKEN_WOLF, OPENAI_API_KEY, "Winston Wolf", "Kangoshi", stream_link="https://twitch.tv/kangoshi_chan", test_mode=False, admin_pw=ADMIN_PASSWORT, max_tokens = 256, temperature= 1, timer_duration=100)
    bot.runBot()