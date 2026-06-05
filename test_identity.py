import json
import os

import pytest

from identity import (
    IdentityRegistry,
    migrate_conversation_files,
    migrate_media_dir,
    move_dict_key,
    rekey_thread_entries,
)


# --- IdentityRegistry ---------------------------------------------------------

def test_registry_set_and_get(tmp_path):
    reg = IdentityRegistry("alex", dir_path=str(tmp_path))
    reg.set(123, "alice")
    assert reg.get_name(123) == "alice"
    # ID is normalised to string, so int and str lookups agree.
    assert reg.get_name("123") == "alice"


def test_registry_unknown_returns_none(tmp_path):
    reg = IdentityRegistry("alex", dir_path=str(tmp_path))
    assert reg.get_name(999) is None


def test_registry_persists_and_reloads(tmp_path):
    reg = IdentityRegistry("alex", dir_path=str(tmp_path))
    reg.set(123, "alice")
    reg.save()

    reloaded = IdentityRegistry("alex", dir_path=str(tmp_path)).load()
    assert reloaded.get_name(123) == "alice"


def test_bootstrap_from_threads_seeds_missing_ids(tmp_path):
    threads = [
        {"alice": {"author_id": 123, "thread_id": 1}},
        {"bob": {"author_id": 456, "thread_id": 2}},
    ]
    reg = IdentityRegistry("alex", dir_path=str(tmp_path)).load(thread_entries=threads)
    assert reg.get_name(123) == "alice"
    assert reg.get_name(456) == "bob"


def test_bootstrap_does_not_override_authoritative_file(tmp_path):
    # The identities file is authoritative (reflects the latest rename); stale
    # thread metadata must not clobber it.
    reg = IdentityRegistry("alex", dir_path=str(tmp_path))
    reg.set(123, "alice_renamed")
    reg.save()

    threads = [{"alice_old": {"author_id": 123, "thread_id": 1}}]
    reloaded = IdentityRegistry("alex", dir_path=str(tmp_path)).load(thread_entries=threads)
    assert reloaded.get_name(123) == "alice_renamed"


def test_bootstrap_skips_entries_without_author_id(tmp_path):
    threads = [{"legacy": {"thread_id": 1}}]
    reg = IdentityRegistry("alex", dir_path=str(tmp_path)).load(thread_entries=threads)
    assert reg.map == {}


# --- migrate_conversation_files ----------------------------------------------

def _write(path, content="[]"):
    with open(path, "w") as f:
        f.write(content)


def test_migrate_renames_primary_and_numeric_backups(tmp_path):
    d = str(tmp_path)
    _write(os.path.join(d, "old.json"), '["primary"]')
    _write(os.path.join(d, "old_0.json"), '["b0"]')
    _write(os.path.join(d, "old_1.json"), '["b1"]')

    renamed = migrate_conversation_files(d, "old", "new")

    assert os.path.exists(os.path.join(d, "new.json"))
    assert os.path.exists(os.path.join(d, "new_0.json"))
    assert os.path.exists(os.path.join(d, "new_1.json"))
    assert not os.path.exists(os.path.join(d, "old.json"))
    assert len(renamed) == 3
    with open(os.path.join(d, "new.json")) as f:
        assert f.read() == '["primary"]'


def test_migrate_does_not_match_other_users_with_shared_prefix(tmp_path):
    d = str(tmp_path)
    _write(os.path.join(d, "bob.json"))
    # A different user whose name starts with "bob" must not be touched.
    _write(os.path.join(d, "bob_smith.json"))
    _write(os.path.join(d, "bob_0.json"))

    migrate_conversation_files(d, "bob", "bobby")

    assert os.path.exists(os.path.join(d, "bobby.json"))
    assert os.path.exists(os.path.join(d, "bobby_0.json"))
    # bob_smith is a real username, not a "bob" backup — left alone.
    assert os.path.exists(os.path.join(d, "bob_smith.json"))


def test_migrate_never_clobbers_existing_target(tmp_path):
    d = str(tmp_path)
    _write(os.path.join(d, "old.json"), '["old"]')
    _write(os.path.join(d, "new.json"), '["existing-new"]')

    renamed = migrate_conversation_files(d, "old", "new")

    # Target already existed — skip, do not destroy it.
    assert renamed == []
    assert os.path.exists(os.path.join(d, "old.json"))
    with open(os.path.join(d, "new.json")) as f:
        assert f.read() == '["existing-new"]'


def test_migrate_no_files_is_noop(tmp_path):
    assert migrate_conversation_files(str(tmp_path), "ghost", "phantom") == []


# --- migrate_media_dir --------------------------------------------------------

def test_migrate_media_dir_renames(tmp_path):
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "old_media"))
    _write(os.path.join(root, "old_media", "file.pdf"), "x")

    assert migrate_media_dir(root, "old", "new") is True
    assert os.path.isdir(os.path.join(root, "new_media"))
    assert os.path.exists(os.path.join(root, "new_media", "file.pdf"))


def test_migrate_media_dir_missing_is_noop(tmp_path):
    assert migrate_media_dir(str(tmp_path), "old", "new") is False


def test_migrate_media_dir_does_not_clobber(tmp_path):
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "old_media"))
    os.makedirs(os.path.join(root, "new_media"))
    assert migrate_media_dir(root, "old", "new") is False
    assert os.path.isdir(os.path.join(root, "old_media"))


# --- move_dict_key ------------------------------------------------------------

def test_move_dict_key_moves_value():
    d = {"old": 5}
    assert move_dict_key(d, "old", "new") is True
    assert d == {"new": 5}


def test_move_dict_key_missing_source_is_noop():
    d = {"x": 1}
    assert move_dict_key(d, "old", "new") is False
    assert d == {"x": 1}


def test_move_dict_key_does_not_overwrite_by_default():
    d = {"old": 1, "new": 2}
    assert move_dict_key(d, "old", "new") is False
    assert d == {"old": 1, "new": 2}


# --- rekey_thread_entries -----------------------------------------------------

def test_rekey_thread_entries_renames_key_preserving_metadata():
    threads = [{"old": {"author_id": 123, "thread_id": 7}}]
    assert rekey_thread_entries(threads, "old", "new") is True
    assert threads == [{"new": {"author_id": 123, "thread_id": 7}}]


def test_rekey_thread_entries_noop_when_absent():
    threads = [{"someone": {"author_id": 1, "thread_id": 2}}]
    assert rekey_thread_entries(threads, "old", "new") is False
