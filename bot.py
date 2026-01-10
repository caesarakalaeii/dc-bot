import asyncio
import json
import os
import random
import time
import discord
import openai
from openai import OpenAI

from conversation_handler import ConversationHandler
from logger import Logger
from promt_creation import get_prompt, get_art_styles
from queue_item import QueueItem
from receipt_creation import image_creation
from utils import (
    handle_args,
    save_media,
    load_conversation,
    list_conversations,
    unpack_message,
    ensure_persistence_dir_exists,
)


class GPTBot:

    queue: asyncio.Queue

    def __init__(
        self,
        bot_config: dict,
    ):
        ensure_persistence_dir_exists()
        ensure_persistence_dir_exists("media")
        self.conversations = []
        self.channel_id = int(bot_config["channel_id"])
        self.guild_id = int(bot_config["guild_id"])
        self.commands_enabled = bot_config["commands_enabled"]
        self.__admin_pw = bot_config["admin_pw"]
        self.bot = None
        self.debug = bot_config["debug"]
        self.commands = {
            "!delete_conv": {
                "perm": 5,
                "help": "!delete_conv: Deletes this Conversation from bot Memory",
                "value_type": None,
                "func": self.del_conv,
            },
            "!load_conv": {
                "perm": 10,
                "help": '!load_conv "user" ["number"]: Loads specific Conversation',
                "value_type": [str, int],
                "func": self.load_conv,
            },
            "!list_conv": {
                "perm": 10,
                "help": "!list_conv: Lists available conversations",
                "value_type": None,
                "func": self.list_conv,
            },
            "!get_config": {
                "perm": 5,
                "help": "!get_config: returns current configuration",
                "value_type": None,
                "func": self.get_config,
            },
            "!repeat_conv": {
                "perm": 5,
                "help": "!repeat_conv: repeats current conversation WARNING: might be a lot! will return nothing when conversation is not in memory",
                "value_type": None,
                "func": self.repeat_conv,
            },
            "!toggle_testmode": {
                "perm": 10,
                "help": "!toggle_testmode: toggles testmode for shorter response time.",
                "value_type": None,
                "func": self.toggle_test_mode,
            },
            "!set_temperature": {
                "perm": 10,
                "help": "!set_temperature value: Changes temperature",
                "value_type": float,
                "func": self.set_temp,
            },
            "!set_max_token": {
                "perm": 10,
                "help": "!set_max_token value: sets the maximal Amount of Tokens used",
                "value_type": int,
                "func": self.set_max_tokens,
            },
            "!set_delay": {
                "perm": 10,
                "help": "!set_delay value: will set minimum reply delay",
                "value_type": int,
                "func": self.set_delay,
            },
            "!toggle_test_prompt": {
                "perm": 10,
                "help": "!toggle_test_prompt: toggles usage of a test prompt",
                "value_type": None,
                "func": self.toggle_test_prompt,
            },
            "!get_init_prompt": {
                "perm": 15,
                "help": "!get_init_prompt: returns initial prompt of this conversation",
                "value_type": None,
                "func": self.get_init_prompt,
            },
            "!command_help": {
                "perm": 1,
                "help": "!command_help: returns all available commands",
                "value_type": None,
                "func": self.help,
            },
            "!disable_commands": {
                "perm": 15,
                "help": "!disable_commands passwort: disables all commands until restart, passwort is set in api_secrets.py",
                "value_type": str,
                "func": self.disable_commands,
            },
            "!del_specific": {
                "perm": 10,
                "help": '!del_specific "user": deletes conversation log of specific user from memory',
                "value_type": str,
                "func": self.del_specific_conv,
            },
            "!shutdown": {
                "perm": 15,
                "help": "!shutdown: shutdown this bot",
                "value_type": None,
                "func": self.shutdown,
            },
            "!save_all": {
                "perm": 10,
                "help": "!save_all: saves all on going conversations",
                "value_type": None,
                "func": self.save_all,
            },
            "!get_msg_log": {
                "perm": 10,
                "help": "!get_msg_log user_id: Returns all DMs by user",
                "value_type": int,
                "func": self.get_message_log,
            },
            "!force_resend": {
                "perm": 10,
                "help": '!force_resend "name" ["message"]: Tries to send last message or specified message',
                "value_type": str,
                "func": self.resend_msg,
            },
            "!load_author": {
                "perm": 10,
                "help": "!load_author user_id: Tries to load author by ID, load conversation first!",
                "value_type": int,
                "func": self.load_author,
            },
            "!clear_memory": {
                "perm": 10,
                "help": "!clear_memory: clears conversations from memory, while retaining .jsons unchanged",
                "value_type": None,
                "func": self.clear_memory,
            },
            "!ban": {
                "perm": 15,
                "help": "!ban user_id: Bans user_id from interacting with bot",
                "value_type": int,
                "func": self.ban,
            },
            "!unban": {
                "perm": 15,
                "help": "!unban user_id: Unbans user_id from interacting with bot",
                "value_type": int,
                "func": self.unban,
            },
            "!whitelist": {
                "perm": 15,
                "help": '!whitelist "user" "value": whitelists user with permission value 1-15, to deactivate commands set value to 0',
                "value_type": [str, int],
                "func": self.whitelist,
            },
            "!reload_whitelist": {
                "perm": 15,
                "help": "!reload_whitelist: reloads whitelist from disk",
                "value_type": None,
                "func": self.reload_whitelist,
            },
            "!reload_blacklist": {
                "perm": 15,
                "help": "!reload_blacklist: reloads blacklist from disk",
                "value_type": None,
                "func": self.reload_blacklist,
            },
            "!init_conv": {
                "perm": 10,
                "help": '!init_conv "user" "id" "message": Initializes conversation with message to user with id',
                "value_type": [str, int, str],
                "func": self.init_conv,
            },
            "!fake_receipt": {
                "perm": 10,
                "help": '!fake_receipt "user" "id" "store name" "amount": Fakes a PayPal receipt for the given Store name and Amount (Currently only in german)',
                "value_type": [str, int, str, int],
                "func": self.fake_receipt,
            },
            "!toggle_auto_welcome": {
                "perm": 15,
                "help": "!toggle_auto_welcome: Toggles automatic welcome messages for new members",
                "value_type": None,
                "func": self.toggle_auto_welcome,
            },
            "!reload_welcomed_users": {
                "perm": 15,
                "help": "!reload_welcomed_users: Reloads welcomed users list from disk",
                "value_type": None,
                "func": self.reload_welcomed_users,
            },
            "!check_welcome_status": {
                "perm": 10,
                "help": "!check_welcome_status: Shows auto-welcome status and statistics",
                "value_type": None,
                "func": self.check_welcome_status,
            },
        }
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "gpt_2_receipt",
                    "description": "Send a receipt to the user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "string",
                                "description": "The amount of money to be shown on the receipt in dollar, e.g. 12.99",
                            },
                            "store_name": {
                                "type": "string",
                                "description": "The name of the recipient, e.g. 'GFX Masters'",
                            },
                        },
                        "required": ["amount", "store_name"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        ]
        self.__bot_token = bot_config["bot_token"]
        self.authors = []
        self.logger = Logger(True, True)
        if self.__admin_pw is None:
            self.logger.error(
                "No admin password provided, you will not be able to disable commands!"
            )
        self.client = OpenAI(api_key=bot_config["gpt_api_key"])
        self.MODEL_NAME = bot_config["model"]
        self.use_test_prompt = bot_config["use_test_prompt"]
        self.streamer_name = bot_config["streamer_name"]
        art_styles = bot_config["art_styles"]
        if art_styles is None:
            art_styles = get_art_styles()
        self.art_styles = art_styles
        self.init_prompt = get_prompt(
            bot_config["bot_name"],
            bot_config["streamer_name"],
            self.art_styles,
            bot_config["use_test_prompt"],
            bot_config["stream_link"],
        )
        self.conv_data = "something"
        self.test_mode = bot_config["test_mode"]
        self.temperature = bot_config["temperature"]
        self.max_tokens = bot_config["max_tokens"]
        self.bot_name = bot_config["bot_name"]
        self.timer_duration = bot_config["timer_duration"]
        loaded_black = self.load_blacklist()
        self.black_list = loaded_black
        loaded_white = self.load_whitelist()
        self.white_list = loaded_white
        self.threads = self.load_threads()
        self.tasks = {}
        self.queue = asyncio.Queue()
        # Auto-welcome configuration
        self.auto_welcome_enabled = bot_config.get("auto_welcome_enabled", False)
        # Auto-welcome guild ID (separate from logging guild, defaults to main guild if not specified)
        auto_welcome_guild_str = bot_config.get("auto_welcome_guild_id", None)
        self.auto_welcome_guild_id = int(auto_welcome_guild_str) if auto_welcome_guild_str else self.guild_id
        self.welcomed_users = self.load_welcomed_users()
        self.welcome_tasks = {}  # Track pending welcome tasks
        self.welcome_template = self.get_welcome_template()
        # Webhook configuration for thread impersonation
        self.webhook_cache = {}  # Dictionary: thread_id -> webhook object

    """Utility methods"""

    def get_welcome_template(self):
        """
        Returns the welcome message template.
        Placeholders: {user_name}, {bot_name}, {streamer_name}
        """
        return (
            f"Hey {{user_name}}! Welcome to the community!\n\n"
            f"I'm {{bot_name}}, {{streamer_name}}'s assistant. I'm here to help you with "
            f"anything you might need - whether it's questions about the stream, art commissions, "
            f"or just a friendly chat.\n\n"
            f"What can I help you with today?"
        )

    async def handle_thread(self, author):
        user = author.name
        thread_id = None
        for thread in self.threads:
            if user in thread.keys():
                thread_id = thread[user]["thread_id"]
        if thread_id is None:
            thread = await self.create_thread(author)
            thread_id = thread.id
        return thread_id

    async def collect_message(self, message, author, sender, files=None):
        """Collects a message, stores it in the conversation handler and replies to the thread."""
        user = author.name
        for conversation in self.conversations:
            if conversation.user == user:
                if conversation.author is None:
                    conversation.author = author
                if sender == "gpt":
                    self.logger.chatReply(user, self.bot_name, message)
                    thread_id = await self.handle_thread(author)
                    await self.reply_to_thread(thread_id, message, files, sender)
                    conversation.update_gpt(message)
                    conversation.write_conversation()
                    return
                else:
                    self.logger.userReply(user, message)
                    thread_id = await self.handle_thread(author)
                    await self.reply_to_thread(thread_id, message, files, author)
                    conversation.update_user(message)
                    conversation.write_conversation()
                    return
        if sender == "gpt":
            new_conv = ConversationHandler(
                user, self.bot_name, init_prompt=self.init_prompt, author=author
            )
            self.conversations.append(new_conv)
            self.logger.chatReply(user, self.bot_name, message)
            thread_id = await self.handle_thread(author)
            await self.reply_to_thread(thread_id, message, files, author)
            new_conv.update_gpt(message)
            new_conv.write_conversation()
            return
        new_conv = ConversationHandler(
            user, self.bot_name, init_prompt=self.init_prompt, author=author
        )
        new_conv.update_user(message)
        new_conv.write_conversation()
        self.conversations.append(new_conv)
        self.logger.userReply(user, message)
        thread_id = await self.handle_thread(author)
        await self.reply_to_thread(thread_id, message, files, author)

    async def message_handler(self, message):
        user_prompt, author, files = await unpack_message(message)
        name = author.name
        if f"{author.id}" in self.black_list:
            await author.send("You have no power here!")
            return
        if await self.check_command(message):
            return
        media_amount = len(files)
        if media_amount > 0:
            save_media(name, message.attachments)
            filenames = ""
            for m in files:
                filenames += m.filename + ", "
            user_prompt = (
                f"[{media_amount} amazing Media Attachments, namely:{filenames}]\n"
                + user_prompt
            )
        await self.collect_message(user_prompt, author, "user", files)
        for conversation in self.conversations:
            if conversation.user == name:
                conversation.append_user_message(user_prompt)
                if not conversation.awaiting_response():
                    return

        await self.queue.put(QueueItem(message))
        await self.gpt_sending()

    async def gpt_sending(self):

        q = await self.queue.get()
        author = q.message.author
        for conversation in self.conversations:
            if conversation.user == author.name:

                messages = []  # Kinda useless but also nice
                message = ""

                reversed_conv = conversation.conversation.copy()
                reversed_conv.reverse()
                for c in reversed_conv:
                    if c["role"] == "user":
                        messages.append(c["content"])
                    else:
                        break
                messages.reverse()
                for m in messages:
                    message += f"\n{m}"
                message_length = len(message)
                age = int(time.time() - q.timestamp)

                if not self.test_mode:
                    time_to_wait = (
                        random.randint(
                            self.timer_duration - age,
                            self.timer_duration + message_length - age,
                        )
                        / 2
                    )
                    time_to_type = 10 + (
                        time_to_wait - message_length
                    )  # type 10s at least
                    await asyncio.sleep(time_to_wait)  # wait for further messages

                    async with author.typing():
                        if age <= self.timer_duration:
                            await asyncio.sleep(
                                time_to_type
                            )  # wait for further messages
                        else:
                            async with author.typing():
                                await asyncio.sleep(5)
                else:
                    async with author.typing():
                        await asyncio.sleep(5)
                messages = conversation.conversation
                if len(messages) > 20:
                    old = messages
                    messages = [old[0]]
                    for m in old[-20:]:
                        messages.append(m)
                if conversation.awaiting_response():
                    response = self.client.chat.completions.create(
                        model=self.MODEL_NAME,
                        messages=messages,
                        max_completion_tokens=self.max_tokens,
                        tools=self.tools,
                    )
                    if await self.check_for_tools(response, author.id):
                        self.logger.info(
                            f"Tool called by {author.name}, handling reply in tool function."
                        )
                        return

                    # Die Antwort aus der response extrahieren
                    if response.choices[0].message.content is None:
                        self.logger.warning(
                            "Message ignored: No content in response, no Tool was called."
                        )
                        return
                    reply: str = response.choices[0].message.content
                    reply = reply.replace("USER_NAME", author.name)
                    if conversation.awaiting_response():
                        # if the conversation is awaiting a response, we can send the reply to the thread
                        await self.collect_message(reply, author, "gpt")
                        # send reply to user
                        if self.debug:
                            self.logger.info(f"Reply: {reply}")
                        else:
                            self.logger.info("Sending Message to User")
                            try:
                                await author.send(reply)
                            except discord.errors.HTTPException as e:
                                error_msg = f"Failed to send GPT reply to {author.name}: {e}"
                                self.logger.error(error_msg)
                                # Log to thread
                                thread_id = await self.handle_thread(author)
                                if e.code == 40003:
                                    await self.reply_to_thread(thread_id, f"⚠️ Rate limit: Could not send GPT reply to {author.name}. Discord is rate limiting DM creation. Will retry on next message.", None, "gpt")
                                else:
                                    await self.reply_to_thread(thread_id, f"⚠️ Failed to send GPT reply to {author.name}: {e}", None, "gpt")
                    self.queue.task_done()
                return

    async def check_for_tools(self, response, user_id):
        self.logger.info("Checking for tools in response")
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.function.name == "gpt_2_receipt":
                    args = json.loads(tool_call.function.arguments)
                    self.logger.info(
                        f"Tool gpt_2_receipt called with arguments: {args}"
                    )
                    amount = args.get("amount")
                    store_name = args.get("store_name")
                    await self.send_receipt(amount, store_name, user_id)
                    return True
        return False

    async def gpt_sending_user(self, author):
        user = author.name
        for conversation in self.conversations:
            if conversation.user == user:
                if not conversation.awaiting_response():
                    return
                messages = conversation.conversation
                if len(messages) > 20:
                    old = messages
                    messages = [old[0]]
                    for m in old[-20:]:
                        messages.append(m)

                response = self.client.chat.completions.create(
                    model=self.MODEL_NAME,
                    messages=messages,
                    max_completion_tokens=self.max_tokens,  # maximal amount of tokens, one token roughly equates to 4 chars
                    tools=self.tools,
                )

                if await self.check_for_tools(response, author.id):
                    # if a tool is called, the reply is handled in the tool function
                    return
                # Die Antwort aus der response extrahieren
                response_message = response["choices"][0]["message"]
                reply = response_message["content"]
                # Die Antwort an den Absender der DM zurückschicken
                await self.collect_message(reply, author, "gpt")

                if self.debug:
                    self.logger.info(f"Reply: {reply}")
                else:
                    try:
                        await author.send(reply)
                    except discord.errors.HTTPException as e:
                        error_msg = f"Failed to send GPT reply to {author.name}: {e}"
                        self.logger.error(error_msg)
                        # Log to thread
                        thread_id = await self.handle_thread(author)
                        if e.code == 40003:
                            await self.reply_to_thread(thread_id, f"⚠️ Rate limit: Could not send GPT reply to {author.name}. Discord is rate limiting DM creation. Will retry on next message.", None, "gpt")
                        else:
                            await self.reply_to_thread(thread_id, f"⚠️ Failed to send GPT reply to {author.name}: {e}", None, "gpt")

    async def send_welcome_message(self, member):
        """
        Send a welcome DM to a new member after a random delay.
        Creates a conversation record and initiates contact.

        Args:
            member: discord.Member object of the user who joined
        """
        try:
            # Random delay between 5-10 minutes (300-600 seconds)
            delay = random.randint(300, 600)
            self.logger.info(
                f"Scheduling welcome message for {member.name} ({member.id}) in {delay} seconds"
            )

            await asyncio.sleep(delay)

            # Check if user is still in the guild
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                try:
                    # Refresh member object to ensure they're still in guild
                    member = await guild.fetch_member(member.id)
                except discord.NotFound:
                    self.logger.info(
                        f"User {member.name} ({member.id}) left before welcome message could be sent"
                    )
                    return

            # Format welcome message with placeholders
            welcome_message = self.welcome_template.format(
                user_name=member.name,
                bot_name=self.bot_name,
                streamer_name=self.streamer_name,
            )

            # Send DM
            try:
                await member.send(welcome_message)
                self.logger.passing(
                    f"Welcome message sent to {member.name} ({member.id})"
                )

                # Create conversation record (bot initiates, so it's a "gpt" message)
                await self.collect_message(welcome_message, member, "gpt")

                # Mark user as welcomed
                self.add_welcomed_user(member.id)

            except discord.Forbidden:
                self.logger.warning(
                    f"Cannot send DM to {member.name} ({member.id}) - user has DMs disabled"
                )
                # Still mark as welcomed to avoid retry spam
                self.add_welcomed_user(member.id)

            except discord.HTTPException as e:
                if e.code == 40003:
                    self.logger.error(
                        f"Rate limit error sending welcome to {member.name} ({member.id}): Discord is rate limiting DM creation"
                    )
                    # Don't mark as welcomed - will retry on rejoin
                else:
                    self.logger.error(
                        f"HTTP error sending welcome to {member.name} ({member.id}): {e}"
                    )

        except asyncio.CancelledError:
            self.logger.info(f"Welcome task cancelled for {member.name} ({member.id})")
            raise
        except Exception as e:
            self.logger.error(
                f"Unexpected error in send_welcome_message for {member.name}: {e}"
            )
        finally:
            # Clean up task reference
            if member.id in self.welcome_tasks:
                del self.welcome_tasks[member.id]

    async def reply_to_thread(self, thread_id, message, files=None, sender=None):
        """Send message to thread, using webhooks for user impersonation."""
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            thread = None
            for existing_thread in channel.threads:
                if existing_thread.id == thread_id:
                    thread = existing_thread
                    break

            if thread:
                len_files = len(files) if files else 0

                if sender == "gpt":
                    # Bot messages: use normal send (bot's real profile)
                    reply = message  # No prefix needed
                    self.logger.passing(f'Bot reply: "{reply}" with {len_files} files')
                    await thread.send(reply, files=files)
                else:
                    # User messages: use webhook for impersonation
                    username = sender.name
                    avatar_url = (
                        sender.avatar.url if sender.avatar else sender.default_avatar.url
                    )

                    self.logger.passing(
                        f'User message via webhook: "{message}" from {username} with {len_files} files'
                    )

                    # Try webhook, fallback to old format if it fails
                    await self.send_via_webhook(
                        thread=thread,
                        message=message,
                        username=username,
                        avatar_url=avatar_url,
                        files=files,
                    )
            else:
                self.logger.warning(
                    f"Thread with {thread_id} not found in channel {self.channel_id} of guild {self.guild_id}."
                )

    async def get_or_create_webhook(self, thread):
        """Get cached webhook for thread or create new one."""
        if thread.id in self.webhook_cache:
            # Return cached webhook
            return self.webhook_cache[thread.id]

        try:
            # Webhooks must be created on the parent channel, not the thread
            parent_channel = thread.parent
            if parent_channel is None:
                self.logger.error(f"Thread {thread.id} has no parent channel")
                return None

            # Create new webhook on the parent channel
            webhook = await parent_channel.create_webhook(
                name=f"relay_{thread.id}",
                reason="Message relay for conversation tracking",
            )
            self.webhook_cache[thread.id] = webhook
            self.logger.info(f"Created webhook for thread {thread.id} on parent channel {parent_channel.id}")
            return webhook
        except discord.Forbidden:
            self.logger.error(
                f"Missing manage_webhooks permission for parent channel of thread {thread.id}"
            )
            return None
        except discord.HTTPException as e:
            self.logger.error(f"Failed to create webhook for thread {thread.id}: {e}")
            return None

    async def send_via_webhook(self, thread, message, username, avatar_url, files=None):
        """Send message via webhook with custom username and avatar."""
        webhook = await self.get_or_create_webhook(thread)

        if webhook is None:
            # Fallback to old format if webhook creation failed
            self.logger.warning(f"Webhook unavailable, using fallback format")
            fallback_message = f"{username} says: {message}"
            await thread.send(fallback_message, files=files)
            return False

        try:
            await webhook.send(
                content=message,
                username=username,
                avatar_url=avatar_url,
                files=files,
                thread=thread,
                wait=True,
            )
            self.logger.info(f"Sent message via webhook as {username} to thread {thread.id}")
            return True
        except discord.HTTPException as e:
            self.logger.error(f"Webhook send failed: {e}, using fallback")
            # Fallback to old format
            fallback_message = f"{username} says: {message}"
            await thread.send(fallback_message, files=files)
            return False

    async def check_command(self, message_object):
        message, author, _ = await unpack_message(message_object)

        if not self.commands_enabled:
            return False
        reply = None
        try:
            for command, value in self.commands.items():
                if (
                    message.startswith(command)
                    and int(self.white_list[author.name]) > 15
                ):
                    self.logger.warning(
                        f"{author.name} invoked {command} with too much permissions"
                    )
                    reply = "Bruh"
                elif (
                    message.startswith(command)
                    and int(self.white_list[author.name]) >= value["perm"]
                ):
                    reply = await value["func"](message_object)
                elif (
                    message.startswith(command)
                    and int(self.white_list[author.name]) < value["perm"]
                ):
                    reply = f"I'm sorry {author.name}. I'm afraid can't do that."
                    self.logger.warning(
                        f"{author.name} invoked {command} without necessary permissions"
                    )
                elif self.white_list[author.name] == "0":
                    self.logger.warning(
                        f"{author.name} invoked {command} with 0 permissions"
                    )
                    return True
            if message.startswith("!") and reply is None:
                reply = "Unknown Command."
        except KeyError:
            return False
        if reply is not None:
            await author.send(reply)
            return True

        return False

    def load_blacklist(self):
        if os.path.exists(f"persistence/blacklist_{self.bot_name}.json"):
            with open(f"persistence/blacklist_{self.bot_name}.json", "r") as f:
                return json.loads(f.read())
        else:
            self.logger.fail("Couldn't load Blacklist")
            return {}

    def write_blacklist(self):
        with open(f"persistence/blacklist_{self.bot_name}.json", "w") as f:
            f.write(json.dumps(self.black_list))

    def load_whitelist(self):
        if os.path.exists(f"persistence/whitelist_{self.bot_name}.json"):
            with open(f"persistence/whitelist_{self.bot_name}.json", "r") as f:
                return json.loads(f.read())
        else:
            self.logger.fail("Couldn't load Whitelist")
            return {}

    def write_whitelist(self):
        with open(f"persistence/whitelist_{self.bot_name}.json", "w") as f:
            f.write(json.dumps(self.white_list))

    def clc_mem(self):
        for c in self.conversations:
            del self.conversations[self.conversations.index(c)]
        self.logger.error("Memory cleared")

    def load_threads(self):
        if os.path.exists(f"persistence/threads_{self.bot_name}.json"):
            with open(f"persistence/threads_{self.bot_name}.json", "r") as f:
                return json.loads(f.read())
        else:
            return []

    def write_threads(self):
        with open(f"persistence/threads_{self.bot_name}.json", "w") as f:
            f.write(json.dumps(self.threads))

    def load_welcomed_users(self):
        """Load list of user IDs who have been welcomed."""
        file_path = f"persistence/welcomed_users_{self.bot_name}.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.loads(f.read())
        else:
            self.logger.info("No welcomed users file found, creating new one")
            return []

    def write_welcomed_users(self):
        """Persist the list of welcomed users to disk."""
        file_path = f"persistence/welcomed_users_{self.bot_name}.json"
        with open(file_path, "w") as f:
            f.write(json.dumps(self.welcomed_users))
        self.logger.info(
            f"Welcomed users list saved with {len(self.welcomed_users)} entries"
        )

    def add_welcomed_user(self, user_id: int):
        """Add a user ID to the welcomed users list."""
        if user_id not in self.welcomed_users:
            self.welcomed_users.append(user_id)
            self.write_welcomed_users()
            self.logger.info(f"Added user {user_id} to welcomed users list")

    def run_bot(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.members = True  # Required for on_member_join event
        self.bot = discord.Client(intents=intents)

        @self.bot.event
        async def on_ready():
            self.logger.passing(
                f"Logged in as {self.bot.user.name}, given name: {self.bot_name}"
            )

        @self.bot.event
        async def on_message(message):
            if (
                isinstance(message.channel, discord.DMChannel)
                and message.author != self.bot.user
            ):
                await self.message_handler(message)

        @self.bot.event
        async def on_member_join(member):
            """
            Triggered when a user joins the guild specified by AUTO_WELCOME_GUILD_ID.
            Schedules a welcome message if auto-welcome is enabled.
            """
            # Only handle joins for the auto-welcome target guild
            if member.guild.id != self.auto_welcome_guild_id:
                self.logger.info(
                    f"Ignoring join from non-target guild: {member.guild.name} (ID: {member.guild.id})"
                )
                return

            self.logger.info(
                f"New member joined: {member.name} ({member.id}) in guild {member.guild.name}"
            )

            # Check if auto-welcome is enabled
            if not self.auto_welcome_enabled:
                self.logger.info(
                    f"Auto-welcome disabled, skipping welcome for {member.name}"
                )
                return

            # Check if user has already been welcomed
            if member.id in self.welcomed_users:
                self.logger.info(
                    f"User {member.name} ({member.id}) already welcomed, skipping"
                )
                return

            # Check if user is a bot
            if member.bot:
                self.logger.info(
                    f"User {member.name} ({member.id}) is a bot, skipping welcome"
                )
                return

            # Schedule welcome message
            task = asyncio.create_task(self.send_welcome_message(member))
            self.welcome_tasks[member.id] = task
            self.logger.passing(
                f"Welcome task created for {member.name} ({member.id})"
            )

        self.bot.run(self.__bot_token)

    async def create_thread(self, author):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            name = author.name
            _id = author.id
            thread = await channel.create_thread(
                name=f"{name}", type=discord.ChannelType.public_thread
            )
            if thread is None:
                self.logger.error(
                    f"Thread creation failed for {name} in channel {self.channel_id}"
                )
                return None
            self.threads.append({name: {"author_id": _id, "thread_id": thread.id}})
            self.write_threads()
            return thread
        self.logger.error(
            f"Channel with id {self.channel_id} not found, cannot create thread."
        )
        self.logger.info(f"{type(self.channel_id)}")
        exit(1)

    """Command Methods"""

    async def help(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.warning(f"{author.name} asked for help.")
        reply = "Available Commands: \n"
        for command, value in self.commands.items():
            if int(self.white_list[author.name]) >= value["perm"]:
                reply += value["help"] + "\n"
        self.logger.info(reply)
        return reply

    async def ban(self, message_object):
        message, author, _ = await unpack_message(message_object)
        splits = message.split(" ")
        if len(splits) < 2:
            reply = "no user_id provided"
        else:
            self.black_list.append(splits[1])
            self.write_blacklist()
            self.logger.warning(f"{author.name} banned user with id {splits[1]}")
            reply = f"user with id {splits[1]} is now banned"

        return reply

    async def unban(self, message_object):
        message, author, _ = await unpack_message(message_object)
        splits = message.split(" ")
        if len(splits) < 2:
            reply = "no user_id provided"
        else:
            del self.black_list[self.black_list.index(splits[1])]
            self.write_blacklist()
            self.logger.warning(f"{author.name} unbanned user with id {splits[1]}")
            reply = f"user with id {splits[1]} is now unbanned"

        return reply

    async def reload_blacklist(self, message_object):
        _, author, _ = await unpack_message(message_object)

        self.black_list = self.load_blacklist()
        self.logger.warning(
            f"{author.name} reloaded blacklist with values {self.black_list}"
        )
        return f"Blacklist loaded with values {self.black_list}"

    async def whitelist(self, message_object):
        message, author, _ = await unpack_message(message_object)
        splits = message.split(" ")
        if len(splits) < 3:
            reply = "no user and/or value provided"
        else:
            name, value = handle_args(message)
            self.white_list.update({name: int(value[0])})
            self.write_whitelist()
            self.logger.warning(f"{author.name} whitelisted {name} with {value}")
            reply = f"{name} is now whitelisted with {value}"

        return reply

    async def reload_whitelist(self, message_object):
        _, author, _ = await unpack_message(message_object)

        self.black_list = self.load_whitelist()
        self.logger.warning(
            f"{author.name} reloaded whitelist with values {self.white_list}"
        )
        return f"Whitelist loaded with values {self.white_list}"

    async def init_conv(self, message_object):
        message, author, _ = await unpack_message(message_object)
        name, values = handle_args(message)
        self.logger.warning(f"{author.name} tries to initialize conversation")

        if len(values) >= 2:
            await self.load_conv(message_object, force=True)
            await self.load_author(message_object, _id=values[0])
            send = values[1]
            await self.resend_msg(message_object)
            reply = f"Initialized conversation with {name} with id {values[0]}.\nMessage is: {send}"
        else:
            reply = "Too little information to initialize conversation"
        self.logger.info(reply)
        return reply

    async def del_conv(self, message_object):
        _, author, _ = await unpack_message(message_object)
        return self.delete_conversation(author.name, author.name)

    async def del_specific_conv(self, message_object):
        message, author, _ = await unpack_message(message_object)
        name, _ = handle_args(message)
        return self.delete_conversation(name, author.name)

    def delete_conversation(self, name, requester):
        reply = None
        found_conv = False
        for conversation in self.conversations:
            if conversation.user == name:
                found_conv = True
                self.logger.warning(f"Clearing Message Log for {name}")
                conversation.save_conversation()
                conversation.delete_conversation()
                del self.conversations[self.conversations.index(conversation)]
                reply = "Conversation deleted"
                break
        if not found_conv:
            conversation = ConversationHandler(
                name, self.bot_name, init_prompt=self.init_prompt
            )
            self.logger.warning(
                f"Clearing Message Log for {name}, requested by: {requester}"
            )
            try:
                conversation.delete_conversation()
                reply = "Conversation deleted"
            except FileNotFoundError:
                reply = "Conversation does not exist"
        self.logger.info(reply)
        return reply

    async def load_conv(self, message_object, force=False):
        message, author, _ = await unpack_message(message_object)
        name, values = handle_args(message)
        if int(self.white_list[author.name]) >= self.commands["!load_conv"]["perm"]:
            self.logger.warning(f"{author.name} loading conversation {name}")
            try:
                for conversation in self.conversations:
                    if conversation.user == name:
                        conversation.save_conversation()
                        del self.conversations[self.conversations.index(conversation)]
                loaded_conv = load_conversation(name, None, self.bot_name)
                new_conv = ConversationHandler(
                    author.name, self.bot_name, conversation=loaded_conv
                )
                self.conversations.append(new_conv)
                loaded_conv = ConversationHandler(
                    name, self.bot_name, conversation=loaded_conv
                )
                self.conversations.append(loaded_conv)
                reply = "Loaded conversation"
            except FileNotFoundError:
                if force:
                    loaded_conv = ConversationHandler(
                        name, self.bot_name, init_prompt=self.init_prompt
                    )
                    self.conversations.append(loaded_conv)
                    reply = f"Fake loaded conversation {name}"
                else:
                    reply = f"Conversation {name} not found"
        elif (
            len(values) == 0
            and int(self.white_list[author.name]) < self.commands["!load_conv"]["perm"]
        ):
            self.logger.warning(
                f"{author.name} tried loading conversation {name}, without necessary permission"
            )
            reply = "Please provide a conversation number."
        elif len(values) > 1:
            self.logger.warning(
                f"{author.name} loading conversation {name}_{values[0]}"
            )
            try:
                for conversation in self.conversations:
                    if conversation.user == author.name:
                        conversation.save_conversation()
                        del self.conversations[self.conversations.index(conversation)]
                loaded_conv = load_conversation(name, values[0], self.bot_name)
                new_conv = ConversationHandler(
                    author.name, self.bot_name, conversation=loaded_conv
                )
                self.conversations.append(new_conv)
                loaded_conv = ConversationHandler(
                    name, self.bot_name, conversation=loaded_conv
                )
                self.conversations.append(loaded_conv)
                reply = "Loaded conversation"
            except FileNotFoundError:
                reply = f"Conversation {name}_{values[0]} not found"

        else:
            reply = 'Command usage is !load_conv "user" "number"'
        self.logger.info(reply)

        return reply

    async def list_conv(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.warning(f"{author.name} listed all conversations")
        reply = list_conversations(self.bot_name)
        if reply is None:
            reply = "No conversations Found"
        self.logger.info(reply)
        return reply

    async def repeat_conv(self, message_object):
        message, author, _ = await unpack_message(message_object)
        reply = None
        splits = message.split(" ")
        name = author.name
        if len(splits) >= 2:
            name = splits[1]
        for conv in self.conversations:
            self.logger.warning(f"{author.name} asked to get the conversation.")
            if conv.user == author.name:
                replies = []
                for c in conv.conversation:
                    if c["role"] == "system":
                        continue
                    elif c["role"] == "user":
                        replies.append(f"{name}: {c['content']}")
                    else:
                        replies.append(f"{self.bot_name}: {c['content']}")
                for r in replies[:-1]:
                    self.logger.info(r)
                    await author.send(r)
                    await asyncio.sleep(1)
                reply = replies[-1]
                self.logger.info(reply)
        if reply == "":
            reply = "Found trailing data, report to Admin"
            self.logger.error(reply)
        if reply is None:
            reply = "No conversation found"
            self.logger.warning(reply)
        return reply

    async def load_author(self, message_object, _id=None):
        message, author, _ = await unpack_message(message_object)
        reply = None
        found_author = False
        parts = message.split(" ")
        if _id is not None:
            parts[1] = _id
        if len(parts) >= 2:
            self.logger.warning(
                f"{author.name} requested to load author with ID {parts[1]}"
            )
            target_user = await self.bot.fetch_user(int(parts[1]))
            if target_user is None:
                reply = "Loading author failed"
            else:
                for c in self.conversations:
                    if c.user == target_user.name:
                        c.author = target_user
                        found_author = True
                        break
                if not found_author:
                    reply = "Author not found/Conversation not found"
                else:
                    reply = "Author found and loaded"

        elif len(parts) < 2:
            reply = "No ID provided"
        self.logger.warning(reply)
        return reply

    async def toggle_test_mode(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.warning(f"{author.name} toggled test_mode")
        self.test_mode = not self.test_mode
        reply = f"Test Mode is now: {self.test_mode}"
        self.logger.info(reply)
        return reply

    async def toggle_test_prompt(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.warning(f"{author.name} toggled test_test_prompt")
        self.use_test_prompt = not self.use_test_prompt
        self.init_prompt = get_prompt(
            self.bot_name, self.streamer_name, self.art_styles, self.use_test_prompt
        )
        reply = f"use_test_prompt is now: {self.use_test_prompt}"
        self.logger.info(reply)
        return reply

    async def set_temp(self, message_object):
        message, author, _ = await unpack_message(message_object)
        parts = message.split(sep=" ")
        self.logger.warning(f"{author.name} changed Temperature")
        self.temperature = float(parts[1])
        reply = f"Temperature is now: {self.temperature}"
        self.logger.info(reply)
        return reply

    async def set_max_tokens(self, message_object):
        message, author, _ = await unpack_message(message_object)
        parts = message.split(sep=" ")
        self.logger.warning(f"{author.name} changed Max Tokens")
        self.max_tokens = int(parts[1])
        reply = f"Max_tokens is now: {self.max_tokens}"
        self.logger.info(reply)
        return reply

    async def set_delay(self, message_object):
        message, author, _ = await unpack_message(message_object)
        parts = message.split(sep=" ")
        self.logger.warning(f"{author.name} changed delay")
        self.timer_duration = int(parts[1])
        reply = f"Minimum delay is now: {self.timer_duration}"
        self.logger.info(reply)
        return reply

    async def get_config(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.warning(f"{author.name} requested settings")
        replies = [
            f"Bot Name is: {self.bot_name}",
            f"Model name is: {self.MODEL_NAME}",
            f"Streamer name is: {self.streamer_name}",
            f"Art Styles are: {self.art_styles}",
            f"Temperature is: {self.temperature}",
            f"min Delay is: {self.timer_duration}s",
            f"Max Tokens is: {self.max_tokens}",
            f"Test Mode is: {self.test_mode}",
            f"use_test_prompt is: {self.use_test_prompt}",
        ]
        for r in replies[:-1]:
            self.logger.info(r)
            await author.send(r)
        reply = replies[-1]
        self.logger.info(reply)
        return reply

    async def clear_memory(self, message_object):
        _, author, _ = await unpack_message(message_object)
        reply = f"{author.name} cleared memory"
        self.logger.warning(f"{author.name} cleared memory")
        self.clc_mem()
        return reply

    async def get_init_prompt(self, message_object):
        _, author, _ = await unpack_message(message_object)
        reply = None
        splits = []
        self.logger.warning(f"{author.name} asked for the prompt.")
        for conv in self.conversations:
            if conv.user == author.name:
                prompt = conv.init_prompt
                splits = prompt.split("\n")
                for l in splits[:-1]:
                    self.logger.info(l)
                    await author.send(l)
            reply = splits[-1]
        if reply is None:
            reply = "No prompt found"
        self.logger.info(reply)
        return reply

    async def disable_commands(self, message_object):
        message, _, _ = await unpack_message(message_object)
        parts = message.split(sep=" ")

        if len(parts) > 0:
            if parts[1] == self.__admin_pw:
                reply = "DISABLED COMMANDS; THIS CAN NOT BE REVERTED WITHOUT A RESTART"
                self.logger.error(reply)
                self.commands_enabled = False
            else:
                reply = (
                    "The Password provided does not match, this event will be reported!"
                )
                self.logger.error(reply)
        else:
            reply = "No Password provided, this event will be reported!"
            self.logger.error(reply)
        return reply

    async def save_all(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.warning(f"{author.name} requested to save all conversations.")
        if len(self.conversations) > 0:
            for c in self.conversations:
                c.save_conversation()
            reply = "Saved all conversations"
        else:
            reply = "No conversations in memory"
        self.logger.info(reply)
        return reply

    async def shutdown(self, message_object):
        _, author, _ = await unpack_message(message_object)
        self.logger.error(f"{author.name} initiated shutdown, saving conversations.")
        await self.save_all(message_object)

        # Cancel all pending welcome tasks
        if self.welcome_tasks:
            self.logger.info(f"Cancelling {len(self.welcome_tasks)} pending welcome tasks")
            for user_id, task in self.welcome_tasks.items():
                task.cancel()
            self.logger.info("All welcome tasks cancelled")

        # Clear webhook cache
        if self.webhook_cache:
            self.logger.info(f"Clearing {len(self.webhook_cache)} cached webhooks")
            self.webhook_cache.clear()

        self.logger.error("Saved conversations.\nShutting down.")

        exit()

    async def get_message_log(self, message_object):
        message, author, _ = await unpack_message(message_object)
        reply = None
        splits = message.split(" ")
        if self.bot is not None:

            target_user = self.bot.get_user(int(splits[1]))
            if target_user:
                self.logger.warning(
                    f"Fetching DMs from {target_user.name} ({target_user.id}), requested by {author.name}"
                )
                self.logger.info("------")
                # Fetch the DM channel between the bot and the target user
                dm_channel = target_user.dm_channel or await target_user.create_dm()
                # Fetch all messages from the DM channel
                messages = []
                async for message in dm_channel.history(limit=None):
                    messages.append(message)
                for m in messages:
                    reply = f"{m.author.name} ({m.author.id}): {m.content}"
                    self.logger.info(reply)
                    await author.send(reply)
            else:
                reply = f"Unable to find user with ID {splits[1]}"
                self.logger.warning(reply)
        if reply is None:
            reply = "Bot not initialized, How did we get here?"
            self.logger.warning(reply)
        return reply

    async def resend_msg(self, message_object):
        message, author, files = await unpack_message(message_object)
        if len(files) == 0:
            files = None
        fetch_last_message = False
        name, values = handle_args(message)
        reply = None
        if len(values) > 0:
            self.logger.warning("Sending User defined Message")
            if len(values) > 1:
                reply = values[1]
            else:
                reply = values[0]
            for c in self.conversations:
                if c.user == name:
                    await self.collect_message(reply, c.author, "gpt", files)
                    try:
                        await c.author.send(reply, files=files)
                        return "Sending User defined Message"
                    except discord.errors.HTTPException as e:
                        error_msg = f"Failed to send DM to {name}: {e}"
                        self.logger.error(error_msg)
                        # Log to thread
                        thread_id = await self.handle_thread(c.author)
                        await self.reply_to_thread(thread_id, f"⚠️ Rate limit error: Could not send message to {name}. Discord is rate limiting DM creation.", None, "gpt")
                        # Return error to admin
                        if e.code == 40003:
                            return f"❌ Discord rate limit: Opening DMs too fast. Message to {name} was not sent. Please wait a moment and try again."
                        return f"❌ Failed to send DM to {name}: {e}"
        elif len(values) == 0:
            fetch_last_message = True
        else:
            reply = "No Arguments given!"
            return reply
        self.logger.warning(f"{author.name} requested resend to {name}")
        for c in self.conversations:
            if c.user == name:
                if fetch_last_message:
                    last_conv = c.conversation[-1]
                    if last_conv["role"] == "user":
                        await self.gpt_sending_user(c.author)
                        return "Requested new Message from GPT"
                    else:
                        reply = last_conv["content"]

                if c.author is not None:
                    self.logger.warning("Resending Message")
                    await self.collect_message(reply, c.author, "user")
                    try:
                        await c.author.send(reply)
                        for u, t in self.tasks.items():
                            t.cancel()
                        return "Resending Message"
                    except discord.errors.HTTPException as e:
                        error_msg = f"Failed to resend DM to {name}: {e}"
                        self.logger.error(error_msg)
                        # Log to thread
                        thread_id = await self.handle_thread(c.author)
                        await self.reply_to_thread(thread_id, f"⚠️ Rate limit error: Could not resend message to {name}. Discord is rate limiting DM creation.", None, "gpt")
                        # Return error to admin
                        if e.code == 40003:
                            return f"❌ Discord rate limit: Opening DMs too fast. Message to {name} was not resent. Please wait a moment and try again."
                        return f"❌ Failed to resend DM to {name}: {e}"

                if c.author is None:
                    reply = "User has no Author."
                    self.logger.warning(reply)
                    return reply
        reply = "Conversation not found."
        self.logger.warning(reply)
        return reply

    async def fake_receipt(self, message_object):
        message, _, _ = await unpack_message(message_object)
        name, values = handle_args(message)
        user_id = values[0]
        store_name = values[1]
        amount = values[2]
        return await self.send_receipt(amount, store_name, user_id, name)

    async def send_receipt(self, amount, store_name, user_id, name=None):
        target_user = await self.bot.fetch_user(user_id)
        if name is None:
            name = target_user.name
        file = image_creation(amount, store_name)
        files = [
            file,
        ]
        file_size = file.fp.__sizeof__()
        self.logger.warning(
            f"Sending Fake receipt to {name}\n store name: {store_name}, amount: {amount}, file_size: {file_size}"
        )
        chat_reply = f"{self.streamer_name} shared the receipt with me, please check that the addressee ({store_name}) and the amount ({amount}.00$) are indeed correct:"
        try:
            await target_user.send(chat_reply, files=files)
        except discord.errors.HTTPException as e:
            error_msg = f"Failed to send receipt to {name}: {e}"
            self.logger.error(error_msg)
            # Log to thread if possible
            try:
                thread_id = await self.handle_thread(target_user)
                if e.code == 40003:
                    await self.reply_to_thread(thread_id, f"⚠️ Rate limit: Could not send receipt to {name}. Discord is rate limiting DM creation.", None, "gpt")
                else:
                    await self.reply_to_thread(thread_id, f"⚠️ Failed to send receipt to {name}: {e}", None, "gpt")
            except Exception as thread_error:
                self.logger.error(f"Also failed to log to thread: {thread_error}")
            return f"Failed to send receipt: {e}"
        file = image_creation(amount, store_name)
        files = [
            file,
        ]
        await self.collect_message(chat_reply, target_user, "gpt", files=files)
        return "Send faked receipt"

    async def toggle_auto_welcome(self, message_object):
        """Toggle the auto-welcome feature on/off."""
        _, author, _ = await unpack_message(message_object)

        self.auto_welcome_enabled = not self.auto_welcome_enabled

        self.logger.warning(
            f"{author.name} toggled auto_welcome to {self.auto_welcome_enabled}"
        )

        reply = f"Auto-welcome is now: {'ENABLED' if self.auto_welcome_enabled else 'DISABLED'}"

        # Cancel all pending welcome tasks if disabling
        if not self.auto_welcome_enabled and self.welcome_tasks:
            cancelled_count = 0
            for user_id, task in list(self.welcome_tasks.items()):
                task.cancel()
                cancelled_count += 1
            reply += f"\nCancelled {cancelled_count} pending welcome tasks."
            self.logger.info(f"Cancelled {cancelled_count} pending welcome tasks")

        self.logger.info(reply)
        return reply

    async def reload_welcomed_users(self, message_object):
        """Reload the welcomed users list from disk."""
        _, author, _ = await unpack_message(message_object)

        self.welcomed_users = self.load_welcomed_users()

        self.logger.warning(
            f"{author.name} reloaded welcomed users list with {len(self.welcomed_users)} entries"
        )

        return f"Welcomed users list reloaded with {len(self.welcomed_users)} entries"

    async def check_welcome_status(self, message_object):
        """Return current auto-welcome status and statistics."""
        _, author, _ = await unpack_message(message_object)

        self.logger.info(f"{author.name} requested welcome status")

        status = "ENABLED" if self.auto_welcome_enabled else "DISABLED"
        welcomed_count = len(self.welcomed_users)
        pending_count = len(self.welcome_tasks)

        reply = (
            f"Auto-Welcome Status: {status}\n"
            f"Total users welcomed: {welcomed_count}\n"
            f"Pending welcome tasks: {pending_count}"
        )

        if pending_count > 0:
            reply += "\n\nPending welcomes:"
            for user_id in self.welcome_tasks.keys():
                reply += f"\n- User ID: {user_id}"

        self.logger.info(reply)
        return reply
