"""Stable user identity, resilient to Discord username changes.

Discord usernames are mutable; the numeric user ID is not. The bot historically
keyed conversations, threads, the whitelist, media folders and pending-image
buffers by username, so a rename orphaned all of a user's state. This module
provides the identity registry (id -> current username) and the pure helpers
used to migrate name-keyed storage when a rename is detected.

See docs/adr/0001-identity-resilience.md for the rationale.
"""

import json
import os
import re


class IdentityRegistry:
    """Persisted map of ``str(author.id) -> current username``."""

    def __init__(self, bot_name, dir_path="persistence"):
        self.bot_name = bot_name
        self.file_path = os.path.join(dir_path, f"identities_{bot_name}.json")
        self.map = {}

    def load(self, thread_entries=None):
        """Load from disk, then optionally seed missing ids from the thread map.

        The on-disk file is authoritative (it reflects the latest rename), so
        thread bootstrap only fills in ids we don't already know.
        """
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                self.map = json.loads(f.read())
        if thread_entries:
            self.bootstrap_from_threads(thread_entries)
        return self

    def bootstrap_from_threads(self, thread_entries):
        for entry in thread_entries:
            for name, meta in entry.items():
                author_id = meta.get("author_id")
                if author_id is None:
                    continue
                self.map.setdefault(str(author_id), name)

    def get_name(self, user_id):
        return self.map.get(str(user_id))

    def set(self, user_id, name):
        self.map[str(user_id)] = name

    def save(self):
        with open(self.file_path, "w") as f:
            f.write(json.dumps(self.map))


def migrate_conversation_files(dir_path, old, new):
    """Rename ``{old}.json`` and its ``{old}_{n}.json`` numeric backups to ``new``.

    Backups are matched strictly (``{old}_<digits>.json``) so a different user
    whose name merely shares the ``{old}_`` prefix is never touched. An existing
    target is never overwritten. Returns the list of ``(src, dst)`` renamed.
    """
    if not os.path.isdir(dir_path):
        return []
    candidates = [
        (os.path.join(dir_path, f"{old}.json"), os.path.join(dir_path, f"{new}.json"))
    ]
    backup_re = re.compile(re.escape(old) + r"_(\d+)\.json$")
    for fname in os.listdir(dir_path):
        m = backup_re.fullmatch(fname)
        if m:
            candidates.append(
                (
                    os.path.join(dir_path, fname),
                    os.path.join(dir_path, f"{new}_{m.group(1)}.json"),
                )
            )
    renamed = []
    for src, dst in candidates:
        if os.path.exists(src) and not os.path.exists(dst):
            os.rename(src, dst)
            renamed.append((src, dst))
    return renamed


def migrate_media_dir(media_root, old, new):
    """Rename ``{old}_media`` to ``{new}_media``. Never clobbers an existing dir."""
    src = os.path.join(media_root, f"{old}_media")
    dst = os.path.join(media_root, f"{new}_media")
    if os.path.isdir(src) and not os.path.exists(dst):
        os.rename(src, dst)
        return True
    return False


def move_dict_key(d, old, new, overwrite=False):
    """Move ``d[old]`` to ``d[new]``. No-op if source absent or target present."""
    if old in d and (overwrite or new not in d):
        d[new] = d.pop(old)
        return True
    return False


def rekey_thread_entries(threads, old, new):
    """Re-key any ``{old: meta}`` thread entry to ``{new: meta}`` in place."""
    changed = False
    for entry in threads:
        if old in entry and new not in entry:
            entry[new] = entry.pop(old)
            changed = True
    return changed
