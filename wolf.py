from bot import GPTBot
from api_secrets import *

if __name__ == '__main__':

    bot = GPTBot(bot_token=DISCORD_TOKEN_WOLF, gpt_api_key=OPENAI_API_KEY, bot_name="Winston Wolf", streamer_name="Kangoshi",channel_id= 1136746061684293632,guild_id=789235412018135040, stream_link="https://twitch.tv/kangoshi_chan", test_mode=False, admin_pw=ADMIN_PASSWORT, max_tokens = 256, temperature= 1, timer_duration=100)
    bot.runBot()