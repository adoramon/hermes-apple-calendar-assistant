# Hermes Apple Calendar Assistant

## What This Skill Is

This skill helps Hermes operate macOS Apple Calendar through local Python scripts.
It is intended for the Hermes profile `sunny-wechat-lite`.

This is the first version of the skill. It only covers basic Apple Calendar CRUD
and confirmation workflow:

- Query calendar events
- Create calendar events
- Update calendar events
- Delete calendar events

The runtime is macOS only. Calendar operations are performed by `osascript` /
AppleScript through `scripts/calendar_ops.py`.

## When To Use

Use this skill when the user asks to:

- Query or list calendar events
- Create a new schedule/calendar event
- Modify an existing schedule/calendar event
- Delete an existing schedule/calendar event

Do not use the normal create/update/delete flow for special calendars or special
workflows such as:

- 飞行计划
- 生日
- 节假日

Flight enhancement and birthday reminder workflows are intentionally out of the
main flow for this first version.

## Allowed Write Calendars

The first version may only write to these calendars:

- 商务计划
- 家庭计划
- 个人计划
- 夫妻计划

If the user asks to create, update, or delete events in any other calendar, do
not write to Apple Calendar. Explain that this first version only supports writes
to the allowed calendars above.

## Required Fields For Create

Before creating an event, collect these fields:

- `calendar`
- `title`
- `start`
- `end`
- `location`
- `notes`

`calendar`, `title`, `start`, and `end` are required. `location` and `notes` may
be empty strings if the user does not provide them.

If required fields are missing, ask follow-up questions before creating a pending
confirmation. Do not call the final create operation until the user explicitly
confirms.

## Confirmation Rules

All write operations require confirmation before execution:

- Create
- Update
- Delete

Before any write operation, show a concise confirmation summary. Only execute the
write after the user clearly replies with `确认`.

If the user says `取消`, `不用了`, `算了`, or otherwise declines, cancel the
pending action and do not write to Apple Calendar.

If the user response is ambiguous, ask whether they want to confirm or cancel.

## Query Flow

For event queries, call `scripts/calendar_ops.py`.

Use:

```bash
python3 scripts/calendar_ops.py events "<calendar>" --start "<start>" --end "<end>"
```

If the user does not provide a time range, the script defaults to a bounded range
instead of scanning the full calendar history.

For listing calendars, use:

```bash
python3 scripts/calendar_ops.py calendars
```

Query operations do not require confirmation because they do not write to Apple
Calendar.

## Create Flow

Use `scripts/interactive_create.py` for create-event state management.

The normal create flow is:

1. Collect structured slots from the conversation:
   - `calendar`
   - `title`
   - `start`
   - `end`
   - `location`
   - `notes`
2. Call `build_draft_from_slots(payload)`.
3. If `missing_fields` is not empty, ask the user to provide those fields.
4. If `invalid_fields` contains `calendar`, explain the allowed write calendars.
5. Call `build_confirmation_summary(draft)`.
6. Show the confirmation summary to the user.
7. Call `save_pending_confirmation(session_key, draft)` to store the pending task.
8. Wait for the user to reply.
9. If the user replies `确认`, call `confirm_pending_action(session_key)`.
10. If the user declines or cancels, call `cancel_pending_action(session_key)`.

`confirm_pending_action(session_key)` is the only create-flow function that writes
to Apple Calendar. It calls `calendar_ops.create_event()` internally.

CLI demo:

```bash
python3 scripts/interactive_create.py demo
```

The demo does not call the final confirmation path and should not create a real
Calendar.app event.

## Update Flow

For the first version, update only supports exact-title matching through
`scripts/calendar_ops.py`.

Before updating, collect:

- `calendar`
- `old_title`
- one or more updated fields:
  - `new_title`
  - `start`
  - `end`
  - `location`
  - `notes`

Then show a confirmation summary. Only after the user replies `确认`, call:

```bash
python3 scripts/calendar_ops.py update \
  "<calendar>" \
  "<old_title>" \
  --new-title "<new_title>" \
  --start "<start>" \
  --end "<end>" \
  --location "<location>" \
  --notes "<notes>"
```

Only include CLI flags for fields the user wants to update. Do not do fuzzy
matching or multi-candidate selection in this first version.

## Delete Flow

For delete, collect:

- `calendar`
- `title`

Then show a confirmation summary. Only after the user replies `确认`, call:

```bash
python3 scripts/calendar_ops.py delete "<calendar>" "<title>" --yes
```

The delete implementation deletes the first exact-title match in the target
calendar. Make this clear in the confirmation summary if there may be multiple
events with the same title.

## Output Handling

The scripts return structured JSON-like results:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

If `ok` is `false`, explain the error to the user and do not assume the operation
succeeded.

If a write operation fails, keep the response clear and operational: mention what
failed, why if available, and what information is needed to retry.

## Safety Principles

- Never write to Apple Calendar without explicit user confirmation.
- Never use normal create/update/delete for disallowed calendars.
- Never hardcode personal secrets.
- Prefer structured payloads over natural-language parsing in this first version.
- Keep flight enhancement and birthday reminder behavior out of the main CRUD
  flow until their dedicated workflows are implemented.
