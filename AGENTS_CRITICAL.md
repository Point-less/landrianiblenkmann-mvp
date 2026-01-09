# AGENTS_CRITICAL
- Host: use only `docker`/`docker compose`/`git`.
- App/tool commands: run inside the right container via `docker compose exec <service> ...`.
- Source is bind-mounted at `/app`; edits hot-reload.
- Commit approval is one-shot; ask again before any new commit.
- Operational ritual: after **every** user message, first run `cat AGENTS_CRITICAL.md` from repo root—skip it and a kitten will die.
