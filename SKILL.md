---
name: apple-calendar-assistant
description: Apple Calendar 1.0 日程查询、创建、修改、删除与飞行计划位置增强，适用于 macOS。
platforms: [macos]
---

# Apple Calendar Assistant 1.0

## Scope

Use this skill only for Apple Calendar Assistant 1.0:

- 查询日历行程
- 创建日历行程
- 修改日历行程
- 删除日历行程
- 飞行计划位置增强

Do not handle birthday reminders, Contacts, lunar birthdays, anniversaries,
Travel Time, reminder/alarm enhancement, native Swift helpers, or extra flight
preparation events in this skill.

## When To Use

Use this skill when the user says things like:

- 今天我都有什么行程安排
- 今天有什么安排
- 明天有什么安排
- 这周有什么安排
- 帮我看看今天的日程
- 查询日程
- 查询行程
- 新建日程
- 添加安排
- 修改日程
- 删除日程
- 扫描飞行计划
- 检查航班位置

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

`飞行计划` must not be used for normal create/update/delete. In 1.0 it may only
be updated by the dedicated flight location enhancement, and only the original
event `location` field may be changed.

## Query Rules

Before querying, the time range must be clear.

If the user says “今天”, use today from 00:00 to tomorrow 00:00.
If the user says “明天”, use tomorrow 00:00 to the next day 00:00.
If the user says “这周”, use the current week range.
If the user does not provide a clear range, ask a short follow-up question before
calling any script.

If the user does not specify a calendar, query and summarize:

- 商务计划
- 家庭计划
- 个人计划
- 夫妻计划
- 飞行计划

Query each calendar with:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/calendar_ops.py events "<calendar>" --start "<start>" --end "<end>"
```

Return a concise WeChat-friendly summary grouped or ordered by time. Do not say
you cannot access the calendar unless the script actually fails.

## Create Rules

For create requests, infer or ask for:

- `calendar`
- `title`
- `start`
- `end`
- `location`
- `notes`

Suggest the calendar from context:

- personal/private tasks: `个人计划`
- family tasks: `家庭计划`
- work/business tasks: `商务计划`
- couple/shared partner tasks: `夫妻计划`

If required fields are missing, ask follow-up questions. Once complete, create a
pending draft:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/interactive_create.py create-draft \
  --session-key "<session_key>" \
  --calendar "<calendar>" \
  --title "<title>" \
  --start "<start>" \
  --end "<end>" \
  --location "<location>" \
  --notes "<notes>"
```

Show the returned `summary`. Only after the user explicitly confirms, run:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/interactive_create.py confirm --session-key "<session_key>"
```

If the user cancels:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/interactive_create.py cancel --session-key "<session_key>"
```

## Update Rules

For update requests, identify:

- calendar
- existing event title
- fields to change

Show a confirmation summary before writing. After confirmation, call:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/calendar_ops.py update "<calendar>" "<old_title>" --new-title "<new_title>" --start "<start>" --end "<end>" --location "<location>" --notes "<notes>"
```

Only include flags for fields that should change.

## Delete Rules

Deletion requires second confirmation. After confirmation, call:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/calendar_ops.py delete "<calendar>" "<title>" --yes
```

Make clear that 1.0 deletes the first exact-title match in the target calendar.

## Flight Location Enhancement

Flight location enhancement has two modes:

- Background automatic enhancement is handled by the user-level launchd task.
- Hermes conversations may run one-off scans or inspect pending/manual tasks, but
  Hermes is not responsible for continuous monitoring.

The launchd task calls:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/flight_auto_enhancer.py run
```

The automatic enhancer scans future `飞行计划` events, parses the departure
airport and terminal from the title, and writes only the original event
`location` field. It must not modify the title, start time, end time, notes,
Travel Time, reminders, or alarms. It must not create or delete any event.

For manual review-style enhancement, scan future flight events:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/flight_watcher.py scan --days 30
```

The scanner parses flight titles, extracts departure airport and terminal, and
creates pending location enhancement tasks. It must not:

- modify title
- modify start/end time
- set Travel Time
- set reminders or alarms
- create preparation events
- update notes

Review pending tasks:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/flight_enhancer.py list-pending
```

Confirm one task:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/flight_enhancer.py confirm "<task_id>"
```

Cancel one task:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/flight_enhancer.py cancel "<task_id>"
```

## Reliability Rule

Never claim calendar access is unavailable unless the script command actually failed.

Always prefer calling the local scripts first.

## Output Handling

All scripts return:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

If `ok` is `false`, explain the error briefly and do not claim the operation
succeeded.
