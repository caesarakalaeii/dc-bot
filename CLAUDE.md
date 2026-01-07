# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord bot that uses OpenAI's GPT models to engage in conversations with users via DMs. The bot is designed to impersonate a persona (configurable) and can generate fake PayPal receipts as part of its functionality. The bot supports automatic welcome messages for new Discord members with configurable delays. All conversations are tracked, persisted to disk, and can be managed through a comprehensive command system.

## Development Commands

### Running the Bot
```bash
# Install dependencies
pip install -r requirements.txt

# Run directly
python bot_start.py

# Run with Docker
docker build -t dc-bot .
docker run -d -e DISCORD_TOKEN=... -e OPENAI_API_KEY=... dc-bot
```

### Testing
There is no formal test suite. Testing is done manually by:
1. Setting `TEST_MODE=True` to reduce response delays
2. Using `USE_TEST_PROMPT=True` for a simplified prompt
3. Using the various `!` commands to inspect and manipulate bot state

## Architecture

### Core Components

**GPTBot (bot.py)**: The main bot class that orchestrates all functionality:
- Manages Discord client lifecycle and event handling
- Maintains in-memory conversation state for all active users
- Handles message queueing and GPT response generation with configurable delays
- Implements permission-based command system (15 levels, whitelist/blacklist)
- Thread management: creates Discord threads in a designated channel for each user conversation
- Tool calling: supports OpenAI function calling to trigger receipt generation

**ConversationHandler (conversation_handler.py)**: Manages individual user conversations:
- Tracks conversation history as a list of role/content message objects
- Persists conversations to JSON files in `persistence/{bot_name}_conversations/`
- Supports saving numbered backups (e.g., `username_0.json`, `username_1.json`)
- Maintains system prompt as first message in conversation

**Configuration (bot_start.py)**: Entry point that loads all configuration from environment variables:
- Required: `DISCORD_TOKEN`, `OPENAI_API_KEY`, `CHANNEL_ID`, `GUILD_ID`, `STREAMER_NAME`, `ADMIN_PASSWORD`
- Optional: `BOT_NAME`, `MODEL`, `TEMPERATURE`, `MAX_TOKENS`, `TIMER_DURATION`, `TEST_MODE`, etc.
- `WHITE_LIST` and `BLACK_LIST` are base64-encoded JSON and decoded by `run.sh` on startup

### Message Flow

1. User sends DM to bot → `on_message` event handler
2. Message unpacked and checked against blacklist
3. Command check (if message starts with `!`)
4. If not command: collect message, append to conversation, add to queue
5. `gpt_sending()` processes queue with artificial delays and typing indicators
6. GPT response generated with last 20 messages (+ system prompt)
7. Response sent to user via DM and logged to Discord thread
8. Conversation written to disk

### Key Behavioral Notes

**Timing System**: In production mode (non-test), the bot waits a random amount of time based on `TIMER_DURATION` and message length to simulate human-like response times. Messages are queued via `asyncio.Queue`.

**Conversation Limits**: Only the most recent 20 messages are sent to GPT (plus system prompt) to avoid context window issues and control costs.

**Thread Mirroring**: All DM conversations are mirrored to public threads in the configured channel (CHANNEL_ID) for monitoring/logging purposes.

**Permission System**: Commands have permission levels 1-15. Users are whitelisted with a permission value. Only users with sufficient permission can execute commands. Permission value 0 blocks command execution.

**Tool Calling**: The bot supports OpenAI function calling. Currently implements `gpt_2_receipt` function to generate fake PayPal receipts when GPT determines it's appropriate based on conversation context.

**Auto-Welcome System**: When enabled (`AUTO_WELCOME_ENABLED=true`), the bot automatically sends welcome DMs to new Discord members after a random 5-10 minute delay. The bot tracks welcomed users to prevent spam on rejoin. Welcome tasks are managed via `asyncio.create_task()` and stored in `self.welcome_tasks` dictionary. Users who have DMs disabled are marked as welcomed to avoid retry spam.

### Persistence Structure

```
persistence/
├── {bot_name}_conversations/
│   ├── {username}.json          # Active conversation
│   └── {username}_{n}.json      # Saved backups
├── media/{username}_media/      # User attachments
├── threads_{bot_name}.json      # Thread ID mappings
├── whitelist_{bot_name}.json    # User permissions
├── blacklist_{bot_name}.json    # Banned user IDs
└── welcomed_users_{bot_name}.json  # User IDs who have been welcomed
```

## Important Implementation Details

**Prompt Construction**: The initial prompt is constructed in `promt_creation.py` (note the typo in filename) by replacing placeholders (STREAMER_NAME, BOT_NAME, ART_STYLES, STREAM_LINK) in `prompt.py:initial_prompt`.

**Media Handling**: Attachments are saved to disk in `persistence/media/` and referenced in the conversation text as `[N amazing Media Attachments, namely: filename1, filename2]`. The actual files are NOT sent to GPT.

**Receipt Generation**: `receipt_creation.py` uses PIL to overlay text onto `paypal_blank.png` with custom fonts from `paypal_fonts/`. Currently only supports German language format.

**Error Handling**: The bot logs extensively via `logger.py` but has minimal error recovery. Failed messages or API calls may leave conversations in inconsistent states.

**Author Management**: The bot tracks Discord Author objects separately from conversation data. Authors can be loaded by ID using `!load_author` command after loading a conversation.

## Deployment

The bot is containerized with Docker and designed to run in Kubernetes with a PVC for persistence:
- `run.sh` decodes base64-encoded WHITE_LIST/BLACK_LIST env vars on startup
- Runs as non-root user (65532)
- GitHub Actions workflow in `.github/workflows/build_and_push.yml` builds and pushes images

## Common Patterns

**Adding New Commands**: Add to `self.commands` dict in `GPTBot.__init__()` with:
- `perm`: permission level required
- `help`: help text shown to users
- `value_type`: expected argument types
- `func`: async method reference

**Modifying GPT Behavior**: Update `prompt.py:initial_prompt` or adjust parameters:
- `temperature`: creativity (0-2)
- `max_tokens`: response length limit
- `tools`: OpenAI function definitions

**Command Argument Parsing**: Use `handle_args(message)` from `utils.py` to extract quoted arguments from command messages. Returns `(name, values)` tuple.
