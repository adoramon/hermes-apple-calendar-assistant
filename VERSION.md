# Apple Calendar Assistant

## v2.0.0-alpha

Development scope:

- Natural-language create draft parsing
- Event conflict detection
- Upcoming reminder candidate scanning with JSON output only
- Existing confirmation requirements and flight safety boundaries preserved
- `interactive_create.py create-draft --check-conflict`
- `reminder_worker.py scan` with `data/reminder_seen.json` idempotency
- launchd template for the reminder worker
- Hermes skill instructions for parse -> draft -> conflict check -> confirm

## v1.0.0

Release scope:

- Query events
- Create with confirmation
- Update
- Delete with second confirmation
- Flight location enhancement
