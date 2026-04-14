# hermes-apple-calendar-assistant

Hermes custom skill for macOS Apple Calendar integration. It is designed for the
`sunny-wechat-lite` Hermes profile and uses Python plus `osascript`/AppleScript
to operate Calendar.app.

## Project Overview

This project provides a local skill layer for conversational calendar workflows:
Hermes handles the user conversation, while the scripts in this repository handle
Calendar.app access, confirmation state, and workflow-specific logic.

The project is macOS-only. Python 3.11+ is expected, and the implementation should
prefer the Python standard library unless a dependency is clearly necessary.

## Feature Scope

- Conversational calendar CRUD for Apple Calendar.
- Explicit confirmation before create, update, or delete operations.
- Pending confirmation storage using JSON files.
- Flight event detection and enhancement proposals.
- Birthday reminder generation for the 07:00 workflow.
- Clear local logs and no hardcoded personal secrets.

## Directory Structure

```text
hermes-apple-calendar-assistant/
├── AGENTS.md                         # Project goals, runtime constraints, and safety rules
├── README.md                         # Project documentation
├── .gitignore                        # Local ignore rules
├── .codex/
│   └── config.toml                   # Codex project configuration
├── SKILL.md                          # Hermes skill instructions
├── config/
│   └── settings.json                 # Runtime configuration
├── data/
│   ├── state.json                    # General workflow state
│   ├── pending_confirmations.json    # Pending create/update/delete confirmations
│   └── birthday_history.json         # Birthday reminder de-duplication history
└── scripts/
    ├── calendar_ops.py               # Core Calendar.app CRUD operations
    ├── interactive_create.py         # Slot filling and confirmation workflow
    ├── flight_watcher.py             # Flight event detection and enhancement workflow
    ├── birthday_notifier.py          # Birthday reminder generation
    └── util.py                       # Shared helpers
```

## Local Run

Run commands from the project root:

```bash
cd /path/to/hermes-apple-calendar-assistant
python3 --version
```

Use Python 3.11 or newer. During development, individual scripts can be run
directly once their entry points are implemented:

```bash
python3 scripts/calendar_ops.py
python3 scripts/interactive_create.py
python3 scripts/flight_watcher.py
python3 scripts/birthday_notifier.py
```

Calendar access depends on macOS permissions. The first `osascript`/Calendar.app
operation may trigger a system permission prompt.

## Deploy To sunny-wechat-lite

1. Keep this repository available on the same macOS host that runs Hermes.
2. Copy or symlink `SKILL.md` into the custom skills location used by the
   `sunny-wechat-lite` Hermes profile.
3. Ensure the skill instructions reference the scripts in this repository using
   stable absolute paths.
4. Confirm the Hermes runtime can execute `python3` and `osascript`.
5. Restart or reload the `sunny-wechat-lite` profile so Hermes picks up the
   updated skill instructions.

Do not store secrets in `SKILL.md`, `config/settings.json`, or the data files.

## Verification

Use the following checklist after each implementation milestone:

1. Confirm the repository files exist:

   ```bash
   find . -path ./.git -prune -o -type f -print | sort
   ```

2. Confirm JSON state files are valid:

   ```bash
   python3 -m json.tool config/settings.json
   python3 -m json.tool data/state.json
   python3 -m json.tool data/pending_confirmations.json
   python3 -m json.tool data/birthday_history.json
   ```

3. Confirm Calendar.app can be reached from the shell:

   ```bash
   osascript -e 'tell application "Calendar" to get name of calendars'
   ```

4. Test the Hermes conversation flow in `sunny-wechat-lite`:

   - Ask for a calendar event to be created.
   - Confirm Hermes asks for explicit approval before writing.
   - Approve the pending operation.
   - Confirm the event appears in Calendar.app.
   - Test canceling a pending operation.

5. For flight and birthday workflows, confirm proposals are generated first and
   no calendar event is modified without confirmation.
