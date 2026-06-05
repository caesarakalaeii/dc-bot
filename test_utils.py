from utils import split_message


def test_short_message_returns_single_chunk():
    assert split_message("hello") == ["hello"]


def test_empty_message_returns_empty_list():
    assert split_message("") == []
    assert split_message(None) == []


def test_message_at_limit_is_not_split():
    text = "a" * 2000
    assert split_message(text) == [text]


def test_message_over_limit_is_split_into_chunks_within_limit():
    text = "a" * 4500
    chunks = split_message(text)
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks) == text


def test_splits_on_newline_boundary_when_possible():
    first = "a" * 1500
    second = "b" * 1500
    chunks = split_message(first + "\n" + second)
    assert chunks == [first, second]


def test_splits_on_space_when_no_newline():
    first = "a" * 1500
    second = "b" * 1500
    chunks = split_message(first + " " + second)
    assert chunks == [first, second]


def test_hard_split_when_no_separator():
    text = "a" * 1900 + "b" * 1900
    chunks = split_message(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2000
    assert "".join(chunks) == text


def test_custom_limit():
    chunks = split_message("a" * 10, limit=4)
    assert all(len(c) <= 4 for c in chunks)
    assert "".join(chunks) == "a" * 10
