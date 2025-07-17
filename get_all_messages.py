import os

import discord
from bot import ConversationHandler
from utils import save_media

# Replace 'YOUR_BOT_TOKEN' with your own Discord bot token
bot_token = os.getenv("DISCORD_TOKEN", Exception("No DISCORD_TOKEN provided"))

# Replace 'TARGET_USER_ID' with the ID of the user whose DMs you want to fetch
target_user_ids = [
    "USER_IDS",
]

# Create a new Discord bot client
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user.name} ({client.user.id})")
    print("------")
    full_convs = ""
    # Fetch the user object for the target user
    for target_user_id in target_user_ids:
        target_user = await client.fetch_user(int(target_user_id))

        if target_user:
            text = f"Fetching DMs from {target_user.name} ({target_user.id})"
            full_convs += text + "\n"
            print(text)
            print("------")

            # Fetch the DM channel between the bot and the target user
            dm_channel = target_user.dm_channel or await target_user.create_dm()

            # Fetch all messages from the DM channel
            messages = []
            async for message in dm_channel.history(limit=None):
                messages.append(message)

            messages.reverse()
            for message in messages:
                media = message.attachments
                media_amount = len(media)

                if media_amount > 0:
                    save_media(message.author.name, media)
                text = (
                    f"{message.author.name} ({message.author.id}): {message.content}\n"
                )
                print(text)
                full_convs += text
            full_convs += "\n"
        else:
            print(f"Unable to find user with ID {target_user_id}")
    with open("full_convs.txt", "w", encoding="utf-8", errors="ignore") as f:
        f.write(full_convs)
    print("End of Conversations")


# Run the bot
client.run(bot_token)
