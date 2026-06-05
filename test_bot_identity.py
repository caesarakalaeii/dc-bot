"""Integration tests for username-rename resilience at the GPTBot level.

These exercise the glue (reconcile_identity / _migrate_user) against a real
GPTBot instance and a temporary persistence dir. The Discord gateway and OpenAI
calls are never reached — we only touch the in-memory + on-disk state.
"""

import json
import os

import pytest

from bot import GPTBot
from conversation_handler import ConversationHandler


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


class FakeAuthor:
    def __init__(self, name, id):
        self.name = name
        self.id = id


@pytest.fixture
def bot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return GPTBot(_config())


def _conv_dir(bot):
    return f"persistence/{bot.bot_name}_conversations"


def test_first_sight_records_identity(bot):
    name = bot.reconcile_identity(FakeAuthor("alice", 100))
    assert name == "alice"
    assert bot.identities.get_name(100) == "alice"


def test_rename_migrates_conversation_file_and_whitelist(bot):
    # alice is known and whitelisted, with an on-disk conversation.
    bot.identities.set(100, "alice")
    bot.white_list["alice"] = "10"
    conv = ConversationHandler("alice", bot.bot_name, init_prompt="sys")
    conv.conversation = [{"role": "system", "content": "sys"},
                         {"role": "user", "content": "hi"}]
    conv.write_conversation()
    bot.conversations.append(conv)

    # She renames to "alice2" and sends a message.
    new_name = bot.reconcile_identity(FakeAuthor("alice2", 100))

    assert new_name == "alice2"
    # Conversation file followed the rename, history intact.
    assert os.path.exists(os.path.join(_conv_dir(bot), "alice2.json"))
    assert not os.path.exists(os.path.join(_conv_dir(bot), "alice.json"))
    with open(os.path.join(_conv_dir(bot), "alice2.json")) as f:
        assert json.loads(f.read())[-1]["content"] == "hi"
    # In-memory handler re-keyed.
    assert bot.conversations[0].user == "alice2"
    # Whitelist permission carried over.
    assert bot.white_list.get("alice2") == "10"
    assert "alice" not in bot.white_list
    # Registry updated.
    assert bot.identities.get_name(100) == "alice2"


def test_rename_rekeys_thread_entry(bot):
    bot.identities.set(100, "alice")
    bot.threads.append({"alice": {"author_id": 100, "thread_id": 555}})

    bot.reconcile_identity(FakeAuthor("alice2", 100))

    assert bot.threads == [{"alice2": {"author_id": 100, "thread_id": 555}}]


def test_no_rename_is_stable(bot):
    bot.identities.set(100, "alice")
    bot.white_list["alice"] = "5"
    bot.reconcile_identity(FakeAuthor("alice", 100))
    assert bot.white_list == {"alice": "5"}
    assert bot.identities.get_name(100) == "alice"


def test_bootstrap_recovers_already_renamed_user(tmp_path, monkeypatch):
    # Simulate the omoboluwatife case: the user already renamed before the
    # registry existed, but a thread entry carries their old name + id.
    monkeypatch.chdir(tmp_path)
    os.makedirs("persistence", exist_ok=True)
    with open("persistence/threads_alex.json", "w") as f:
        f.write(json.dumps([{"oldname": {"author_id": 777, "thread_id": 9}}]))

    bot = GPTBot(_config())
    # On their next message under the NEW name, the rename is detected.
    conv = ConversationHandler("oldname", bot.bot_name, init_prompt="sys")
    conv.conversation = [{"role": "system", "content": "sys"}]
    conv.write_conversation()

    new_name = bot.reconcile_identity(FakeAuthor("newname", 777))

    assert new_name == "newname"
    assert os.path.exists(os.path.join(_conv_dir(bot), "newname.json"))
    assert bot.threads == [{"newname": {"author_id": 777, "thread_id": 9}}]
