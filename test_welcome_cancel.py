"""Tests for discarding a scheduled welcome when the user messages first.

A user who joins gets a welcome DM scheduled after a random 5-10 min delay.
If they proactively DM the bot before that fires, the pending welcome must be
discarded — otherwise they get an out-of-the-blue welcome mid-conversation.
"""

import asyncio

import pytest

from bot import GPTBot


def _config():
    return {
        "channel_id": "1",
        "guild_id": "2",
        "commands_enabled": True,
        "admin_pw": "pw",
        "debug": False,
        "bot_token": "token",
        "gpt_api_key": "sk-test",
        "model": "gpt-4o",
        "use_test_prompt": True,
        "streamer_name": "streamer",
        "art_styles": ["realism"],
        "bot_name": "alex",
        "stream_link": "https://example.com",
        "test_mode": True,
        "temperature": 1.0,
        "max_tokens": 256,
        "timer_duration": 10,
    }


@pytest.fixture
def bot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return GPTBot(_config())


def test_proactive_message_cancels_pending_welcome(bot):
    async def scenario():
        # A welcome is scheduled for user 100 (a real coroutine that sleeps).
        async def _pending():
            await asyncio.sleep(3600)

        task = asyncio.create_task(_pending())
        bot.welcome_tasks[100] = task
        await asyncio.sleep(0)  # let the task start

        # User 100 proactively messages -> the welcome should be discarded.
        bot.cancel_welcome_task(100)
        await asyncio.sleep(0)  # let the cancellation propagate

        assert task.cancelled()
        assert 100 not in bot.welcome_tasks

    asyncio.run(scenario())


def test_cancel_is_noop_without_pending_welcome(bot):
    # No task scheduled for this user -> must not raise.
    bot.cancel_welcome_task(999)
    assert 999 not in bot.welcome_tasks
