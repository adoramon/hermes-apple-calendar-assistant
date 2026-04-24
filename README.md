# hermes-apple-calendar-assistant

Apple Calendar Assistant is a macOS-only Hermes custom skill for operating
Calendar.app from the `sunny-wechat-lite` profile. The current development line
is `v2.0-alpha`.

## Scope

v2.0-alpha includes:

- Query Apple Calendar events after a clear time range is known.
- Create events with structured slots and explicit confirmation.
- Update existing events after confirmation.
- Delete events after second confirmation.
- Scan future `飞行计划` events and write departure airport/terminal into the
  original event `location` field.
- Run a launchd background task every 5 minutes to automatically enhance new
  future `飞行计划` events.
- Parse simple natural-language create requests into draft JSON.
- Detect conflicts for proposed event windows.
- Scan upcoming events as reminder candidates with JSON output only.

v2.0-alpha excludes:

- Birthday reminders
- Contacts, lunar birthday, or anniversary workflows
- Travel Time automation
- Reminder/alarm enhancement or notification delivery
- Native Swift helpers
- Extra preparation events for flights

## Calendar Policy

Read calendars:

- 商务计划
- 家庭计划
- 个人计划
- 夫妻计划
- 飞行计划

Normal write calendars:

- 商务计划
- 家庭计划
- 个人计划
- 夫妻计划

`飞行计划` is not writable through normal create/update/delete. The only flight
write is the dedicated location enhancement on the original flight event, and it
only updates the `location` field.

## Directory Structure

```text
hermes-apple-calendar-assistant/
├── AGENTS.md
├── README.md
├── SKILL.md
├── .gitignore
├── .codex/
│   └── config.toml
├── config/
│   └── settings.json
├── data/
│   ├── state.json
│   ├── pending_confirmations.json
│   ├── flight_seen.json
│   └── flight_pending.json
├── deploy/
│   └── launchd/
│       └── com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
├── docs/
│   └── flight-auto-enhancer.md
└── scripts/
    ├── calendar_ops.py
    ├── interactive_create.py
    ├── flight_parser.py
    ├── flight_watcher.py
    ├── flight_enhancer.py
    ├── flight_auto_enhancer.py
    ├── nl_draft_parser.py
    ├── conflict_detector.py
    ├── upcoming_reminders.py
    └── util.py
```

## Local Usage

List calendars:

```bash
python3 scripts/calendar_ops.py calendars
```

Query a calendar:

```bash
python3 scripts/calendar_ops.py events "个人计划" --start "2026-04-16T00:00:00" --end "2026-04-17T00:00:00"
```

Create a pending event draft:

```bash
python3 scripts/interactive_create.py create-draft \
  --session-key "wechat_user_001" \
  --calendar "个人计划" \
  --title "和客户开会" \
  --start "2026-04-18T15:00:00" \
  --end "2026-04-18T16:00:00" \
  --location "国贸" \
  --notes "讨论商务合作"
```

Confirm or cancel:

```bash
python3 scripts/interactive_create.py confirm --session-key "wechat_user_001"
python3 scripts/interactive_create.py cancel --session-key "wechat_user_001"
```

Parse a natural-language create request into a draft:

```bash
python3 scripts/nl_draft_parser.py parse "明天15:00-16:00在国贸和客户开会"
```

Check conflicts for a proposed event window:

```bash
python3 scripts/conflict_detector.py check --calendar "个人计划" --start "2026-04-18T15:00:00" --end "2026-04-18T16:00:00"
```

Scan upcoming reminder candidates:

```bash
python3 scripts/upcoming_reminders.py scan --minutes 60
```

Scan flight events:

```bash
python3 scripts/flight_watcher.py scan --days 30
python3 scripts/flight_enhancer.py list-pending
python3 scripts/flight_enhancer.py confirm "<task_id>"
```

Run automatic flight enhancement once:

```bash
python3 scripts/flight_auto_enhancer.py run
```

## Deployment

Deploy `SKILL.md` into the Hermes custom skill location used by
`sunny-wechat-lite`. The skill file uses absolute script paths so Hermes does not
need to run from the repository root.

Calendar access depends on macOS automation permissions for `osascript` and
Calendar.app.

Flight auto enhancement can be installed as a user-level launchd task:

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
```

The launchd task runs every 5 minutes and calls:

```bash
python3 scripts/flight_auto_enhancer.py run
```

See [docs/flight-auto-enhancer.md](docs/flight-auto-enhancer.md) for install,
uninstall, log, and `flight_seen.json` reset instructions.

## Verification

```bash
python3 -m py_compile scripts/calendar_ops.py scripts/interactive_create.py scripts/flight_parser.py scripts/flight_watcher.py scripts/flight_enhancer.py scripts/flight_auto_enhancer.py scripts/nl_draft_parser.py scripts/conflict_detector.py scripts/upcoming_reminders.py scripts/util.py
python3 -m json.tool data/state.json
python3 -m json.tool data/pending_confirmations.json
python3 -m json.tool data/flight_seen.json
python3 -m json.tool data/flight_pending.json
python3 -m unittest tests.test_flight_parser
```
## Current Status

Stable from 1.0:

- Calendar CRUD
- Confirmation workflow
- WeChat skill integration
- Flight location enhancement
- launchd automatic flight location enhancement

Added in v2.0-alpha:

- Natural-language draft parsing
- Conflict detection
- Upcoming reminder candidate scanning

Still out of scope:

- Contacts reminders
- Birthday workflows
- Travel Time
