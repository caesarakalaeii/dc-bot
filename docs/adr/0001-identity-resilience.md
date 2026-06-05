# ADR 0001: Resilient user identity against Discord renames

- Status: Accepted
- Date: 2026-06-05

## Context

The bot historically keyed almost all per-user state on the Discord **username**
(`author.name` / `conversation.user`):

- conversation lookups in memory (`conversation.user == name`)
- conversation files on disk (`persistence/{bot}_conversations/{username}.json` and backups)
- the monitoring **thread** map (`threads_{bot}.json`, keyed by username, though it
  already stored `author_id` as metadata)
- the **whitelist** (`whitelist_{bot}.json`, keyed by username)
- the per-user **media** folder (`persistence/media/{username}_media/`)
- the in-memory **pending images** buffer (keyed by username)

Only the **blacklist** and **welcomed-users** state used the immutable numeric
`author.id`.

Discord usernames are mutable. When a user renames themselves, the next message
arrives under the *new* name, no in-memory or on-disk record matches, and the bot
silently starts a brand-new empty conversation — orphaning the entire history,
thread, whitelist permission and media of that user. This is what happened to the
user `omoboluwatife`.

## Decision

Treat the numeric `author.id` as the **stable identity** and the username as a
mutable display attribute, but **keep username-keyed storage** (so the operator
workflow — `!load_conv "name"`, human-editable base64 whitelist in `run.sh`,
readable thread names — is preserved). Reconcile the two with a small identity
registry and a **migrate-on-rename** step:

1. A persisted registry `persistence/identities_{bot}.json` maps `id -> current
   username`. On startup it is **bootstrapped from the existing thread map**
   (each thread entry already carries `author_id`), so users who predate the
   registry — including one who already renamed — are recoverable automatically.
2. On every inbound interaction we have both `author.id` and `author.name`.
   `reconcile_identity(author)` looks up the registry by id:
   - unknown id → record `id -> name`;
   - known id, name changed → a **rename**: migrate all name-keyed state from the
     old name to the new one, then update the registry;
   - known id, same name → no-op.
3. Migration (`_migrate_user`) renames the conversation files and backups, renames
   the media folder, re-keys the in-memory `ConversationHandler`, the whitelist
   entry, the pending-images buffer and the thread-map entry. It **never clobbers**
   an existing target (collisions are logged and skipped).

Reconciliation runs at the top of `message_handler` (before the command/whitelist
check, so a renamed admin keeps their permissions) and for the target user of a
thread-injected message.

### Rejected alternative: re-key everything to `author.id`

A full big-bang migration to id-keyed files/whitelist/threads was rejected because
(a) it requires a risky one-shot migration of all existing on-disk data, (b) it
breaks the operator's name-based commands and the human-edited whitelist env var,
and (c) the migrate-on-rename approach is self-healing and incremental. The numeric
id is still the source of truth for identity; only the *storage key* stays the name.

## Consequences

- A rename now transparently carries the conversation, thread, permission and media
  across, on the user's next message — no manual intervention.
- One extra small JSON file (`identities_{bot}.json`) is written when a new user is
  first seen or a rename is reconciled.
- Name collisions (renaming to a name already in use) are logged and skipped rather
  than silently merged, to avoid data loss; this is rare and surfaced in logs.
- The whitelist remains name-keyed by design; the operator workflow is unchanged.
