import discord
from api_secrets import*
from bot import ConversationHandler

# Replace 'YOUR_BOT_TOKEN' with your own Discord bot token
bot_token = DISCORD_TOKEN_ALEX

# Replace 'TARGET_USER_ID' with the ID of the user whose DMs you want to fetch
target_user_id = 'TARGET_ID'

# Create a new Discord bot client
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user.name} ({client.user.id})')
    print('------')

    # Fetch the user object for the target user
    target_user = await client.fetch_user(int(target_user_id))

    if target_user:
        print(f'Fetching DMs from {target_user.name} ({target_user.id})')
        print('------')

        # Fetch the DM channel between the bot and the target user
        dm_channel = target_user.dm_channel or await target_user.create_dm()

        # Fetch all messages from the DM channel
        messages = []
        async for message in dm_channel.history(limit=None):
            messages.append(message)

        for message in messages:
            media = media = message.attachments
            media_amount = len(media)
            if media_amount > 0:
                ConversationHandler.saveMedia(message.author.name, media)
                
            print(f'{message.author.name} ({message.author.id}): {message.content}')
    else:
        print(f'Unable to find user with ID {target_user_id}')

# Run the bot
client.run(bot_token)