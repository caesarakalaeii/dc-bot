from bot import GPTBot
from api_secrets import *


if __name__ == '__main__':
    bot = GPTBot(bot_token=DISCORD_TOKEN_ALEX, gpt_api_key=OPENAI_API_KEY, bot_name="Alex",  
                 streamer_name="Caesar",channel_id=1129125304993067191,guild_id=877203185700339742, 
                 stream_link = "https://twitch.tv/caesarlp", test_mode=False, admin_pw=ADMIN_PASSWORT, 
                 max_tokens = 256, temperature= 1, timer_duration=100, model = "gpt-4")
    bot.runBot()