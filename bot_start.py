import os

from bot import GPTBot

if __name__ == "__main__":

    config = {
        "bot_token": os.getenv("DISCORD_TOKEN", Exception("No DISCORD_TOKEN provided")),
        "gpt_api_key": os.getenv(
            "OPENAI_API_KEY", Exception("No OPENAI_API_KEY provided")
        ),
        "bot_name": os.getenv("BOT_NAME", "Alex"),
        "channel_id": os.getenv("CHANNEL_ID", Exception("No CHANNEL_ID provided")),
        "guild_id": os.getenv("GUILD_ID", Exception("No GUILD_ID provided")),
        "streamer_name": os.getenv(
            "STREAMER_NAME", Exception("No STREAMER_NAME provided")
        ),
        "test_mode": os.getenv("TEST_MODE", "False").lower() in ("true", "1", "t"),
        "admin_pw": os.getenv(
            "ADMIN_PASSWORD", Exception("No ADMIN_PASSWORD provided")
        ),
        "debug": os.getenv("DEBUG", "False").lower() in ("true", "1", "t"),
        "timer_duration": int(os.getenv("TIMER_DURATION", "300")),
        "art_styles": os.getenv("ART_STYLES", None),
        "temperature": float(os.getenv("TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("MAX_TOKENS", "256")),
        "commands_enabled": os.getenv("COMMANDS_ENABLED", "True").lower()
        in ("true", "1", "t"),
        "stream_link": os.getenv("STREAM_LINK", None),
        "model": os.getenv("MODEL", "gpt-5-mini"),
        "use_test_prompt": os.getenv("USE_TEST_PROMPT", "False").lower()
        in ("true", "1", "t"),
        "auto_welcome_enabled": os.getenv("AUTO_WELCOME_ENABLED", "False").lower()
        in ("true", "1", "t"),
        "auto_welcome_guild_id": os.getenv("AUTO_WELCOME_GUILD_ID", None),
    }
    print("Initializing config:")
    for k, v in config.items():

        if type(v) is Exception:
            raise v
        if (
            "pw" in k.lower()
            or "password" in k.lower()
            or "token" in k.lower()
            or "key" in k.lower()
        ):
            continue
        print(f"{k}: {v}")

    bot = GPTBot(config)

    bot.run_bot()
