# hermes-apple-calendar-assistant

Apple Calendar Assistant 1.0 is a macOS-only Hermes custom skill for operating
Calendar.app from the `sunny-wechat-lite` profile.

## Scope

1.0 includes:

- Query Apple Calendar events after a clear time range is known.
- Create events with structured slots and explicit confirmation.
- Update existing events after confirmation.
- Delete events after second confirmation.
- Scan future `飞行计划` events and write departure airport/terminal into the
  original event `location` field.

1.0 excludes:

- Birthday reminders
- Contacts, lunar birthday, or anniversary workflows
- Travel Time automation
- Reminder/alarm enhancement
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
write in 1.0 is the dedicated location enhancement on the original flight event.

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
└── scripts/
    ├── calendar_ops.py
    ├── interactive_create.py
    ├── flight_parser.py
    ├── flight_watcher.py
    ├── flight_enhancer.py
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

Scan flight events:

```bash
python3 scripts/flight_watcher.py scan --days 30
python3 scripts/flight_enhancer.py list-pending
python3 scripts/flight_enhancer.py confirm "<task_id>"
```

## Deployment

Deploy `SKILL.md` into the Hermes custom skill location used by
`sunny-wechat-lite`. The skill file uses absolute script paths so Hermes does not
need to run from the repository root.

Calendar access depends on macOS automation permissions for `osascript` and
Calendar.app.

## Verification

```bash
python3 -m py_compile scripts/calendar_ops.py scripts/interactive_create.py scripts/flight_parser.py scripts/flight_watcher.py scripts/flight_enhancer.py scripts/util.py
python3 -m json.tool data/state.json
python3 -m json.tool data/pending_confirmations.json
python3 -m json.tool data/flight_seen.json
python3 -m json.tool data/flight_pending.json
```
## Current Status

Stable in 1.0:

- Calendar CRUD
- Confirmation workflow
- WeChat skill integration
- Flight location enhancement

Not in 1.0:

- Contacts reminders
- Birthday workflows
- Travel Time