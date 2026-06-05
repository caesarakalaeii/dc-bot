"""Tests for the token-budget escalation in GPTBot._create_completion.

Reasoning models can return empty content with finish_reason 'length' when the
configured max_tokens is too small; the helper must retry at larger budgets.
"""

import asyncio

import pytest

from bot import GPTBot
from test_bot_identity import _config


class _Choice:
    def __init__(self, finish_reason):
        self.finish_reason = finish_reason
        self.message = type("M", (), {"content": "ok", "tool_calls": None})()


class _Resp:
    def __init__(self, finish_reason):
        self.choices = [_Choice(finish_reason)]


class FakeCompletions:
    def __init__(self, finish_reasons):
        # finish_reason returned for each successive call
        self._reasons = list(finish_reasons)
        self.budgets = []

    def create(self, model, messages, max_completion_tokens, tools):
        self.budgets.append(max_completion_tokens)
        reason = self._reasons[len(self.budgets) - 1]
        return _Resp(reason)


class FakeClient:
    def __init__(self, finish_reasons):
        self.chat = type("C", (), {"completions": FakeCompletions(finish_reasons)})()


@pytest.fixture
def bot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return GPTBot(_config())


def test_no_escalation_when_first_response_complete(bot):
    bot.max_tokens = 256
    bot.client = FakeClient(["stop"])
    asyncio.run(bot._create_completion([{"role": "user", "content": "hi"}]))
    assert bot.client.chat.completions.budgets == [256]


def test_escalates_to_4096_on_length(bot):
    bot.max_tokens = 256
    bot.client = FakeClient(["length", "stop"])
    asyncio.run(bot._create_completion([{"role": "user", "content": "hi"}]))
    assert bot.client.chat.completions.budgets == [256, 4096]


def test_escalates_through_8192_when_still_truncated(bot):
    bot.max_tokens = 256
    bot.client = FakeClient(["length", "length", "length"])
    resp = asyncio.run(bot._create_completion([{"role": "user", "content": "hi"}]))
    assert bot.client.chat.completions.budgets == [256, 4096, 8192]
    assert resp is not None


def test_no_smaller_retries_when_max_tokens_already_large(bot):
    bot.max_tokens = 8192
    bot.client = FakeClient(["length"])
    asyncio.run(bot._create_completion([{"role": "user", "content": "hi"}]))
    # No rung is larger than 8192, so we don't pointlessly retry at 4096.
    assert bot.client.chat.completions.budgets == [8192]
