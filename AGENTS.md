# Project Context

This project is Apple Calendar Assistant 1.0, a macOS-only Hermes custom skill
for the `sunny-wechat-lite` profile.

## 1.0 Scope

The project only supports the Apple Calendar mainline:

1. Query calendar events
2. Create calendar events with confirmation
3. Update calendar events with confirmation
4. Delete calendar events with second confirmation
5. Flight plan location enhancement

Out of scope for 1.0:

- Birthday reminders
- Contacts integration
- Lunar birthday logic
- Anniversary workflows
- Travel Time automation
- Reminder/alarm enhancement
- Native Swift helpers
- Extra preparation events for flights

## Runtime

- macOS only
- Python 3.11+
- Standard library first
- Calendar.app access through `osascript` / AppleScript
- Deployed into Hermes profile: `sunny-wechat-lite`

## Calendar Rules

Query calendars:

- 商务计划
- 家庭计划
- 个人计划
- 夫妻计划
- 飞行计划

Write calendars for normal CRUD:

- 商务计划
- 家庭计划
- 个人计划
- 夫妻计划

`飞行计划` is read-only for normal CRUD. The only 1.0 write allowed for
`飞行计划` is the dedicated flight location enhancement, which writes the
departure airport and terminal into the original event `location` field.

## Query Rules

- The assistant must know a time range before querying.
- If the user does not provide a clear range, ask a follow-up question.
- Query output should be structured, concise, and readable in WeChat.

## Write Safety

- Create/update/delete must show a confirmation summary first.
- Create/update only execute after explicit confirmation.
- Delete requires second confirmation.
- Do not write to disallowed calendars.
- Do not create extra flight preparation events.
- Do not modify flight event start/end time.
- Do not set Travel Time or reminders in 1.0.

## File Responsibilities

- `scripts/calendar_ops.py`: core Calendar.app CRUD
- `scripts/interactive_create.py`: structured create draft and confirmation flow
- `scripts/flight_parser.py`: parse flight title into route details
- `scripts/flight_watcher.py`: scan future flight events
- `scripts/flight_enhancer.py`: manage pending flight location enhancements
- `scripts/util.py`: shared helpers
- `SKILL.md`: Hermes skill instructions
- `config/settings.json`: runtime configuration
