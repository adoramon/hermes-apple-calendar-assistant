---
name: apple-calendar-assistant
description: Apple Calendar v2.0-beta dry-run readiness 日程查询、确认式写入、冲突检测、提醒候选扫描、dry-run outbox 与飞行计划位置增强，适用于 macOS。
platforms: [macos]
---

# Apple Calendar Assistant v2.0-beta dry-run readiness

## Scope

Use this skill only for Apple Calendar Assistant v2.0-beta dry-run readiness:

- 查询日历行程
- 创建日历行程
- 修改日历行程
- 删除日历行程
- 自然语言日程草稿解析
- 日程冲突检测
- 即将到来日程提醒候选扫描
- 飞行计划位置增强

Do not handle birthday reminders, Contacts, lunar birthdays, anniversaries,
Travel Time, reminder/alarm enhancement, notification delivery, native Swift
helpers, or extra flight preparation events in this skill.

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
- 明天下午三点在国贸和客户开会
- 这个时间有没有冲突
- 接下来一小时有什么需要提醒
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

`飞行计划` must not be used for normal create/update/delete. It may only be
updated by the dedicated flight location enhancement, and only the original event
`location` field may be changed.

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

用户要求创建日程时，必须按以下顺序处理：

1. 先调用自然语言解析器：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/nlp_event_parser.py parse "<user_text>"
```

解析器只返回草稿，不保存 pending state，不写 Calendar.app。解析结果不得把
`飞行计划` 作为普通创建目标。

2. 如果字段缺失，询问用户补齐：

- `calendar`
- `title`
- `start`
- `end`
- `location`
- `notes`

根据上下文建议日历：

- personal/private tasks: `个人计划`
- family tasks: `家庭计划`
- work/business tasks: `商务计划`
- couple/shared partner tasks: `夫妻计划`

3. 字段完整后，创建 pending draft，并默认加 `--check-conflict`：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/interactive_create.py create-draft \
  --session-key "<session_key>" \
  --calendar "<calendar>" \
  --title "<title>" \
  --start "<start>" \
  --end "<end>" \
  --location "<location>" \
  --notes "<notes>" \
  --check-conflict
```

4. 必须向用户展示草稿、冲突情况和建议时间。若 `has_conflict` 为 true，说明
`conflicts` 和 `suggested_slots`；不要自动改时间。

5. 只有用户明确确认后，才执行：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/interactive_create.py confirm --session-key "<session_key>"
```

If the user cancels:

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/interactive_create.py cancel --session-key "<session_key>"
```

创建日程永远需要显式确认。`confirm` 使用 pending draft 中的原始时间，除非用户
要求修改草稿并确认修改后的版本。

## Update Rules

用户要求修改日程时，先识别：

- calendar
- existing event title
- fields to change

写入前必须二次确认。确认后再调用：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/calendar_ops.py update "<calendar>" "<old_title>" --new-title "<new_title>" --start "<start>" --end "<end>" --location "<location>" --notes "<notes>"
```

Only include flags for fields that should change.

## Delete Rules

用户要求删除日程时，必须二次确认。确认后再调用：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/calendar_ops.py delete "<calendar>" "<title>" --yes
```

Make clear that v2.0-beta dry-run readiness still deletes the first exact-title match in the target calendar.

## Upcoming Reminder Scan

提醒扫描规则：

- 当前 `reminder_worker.py` 只生成提醒候选 JSON
- 当前阶段不主动发送微信或 Telegram
- 是否启用 reminder worker launchd 由用户手动决定
- outbox 只是本地 dry-run 队列，不代表真实发送完成

用户询问即将提醒事项时，可调用：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/reminder_worker.py scan
```

Hermes 对话中只总结返回的候选提醒，不安装 launchd，不持续后台监控。

## Reminder And Outbox Rules

当用户询问“有什么提醒”“待发送提醒”“待处理消息”或类似问题时，调用：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/hermes_outbox_cli.py pending --limit 10
```

展示 pending messages，必须包含或保留每条记录的 `record_id`。不要自动标记为
`sent_dry_run`，除非用户明确确认这些提醒已处理。

当用户说“这些提醒已处理”“标记已处理”“确认发送完成”时，对用户指定的
`record_id` 调用：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/hermes_outbox_cli.py mark-dry-run-sent --id "<record_id>"
```

如果用户没有明确指定是哪条提醒，先询问要标记的 `record_id` 或提醒内容，不要
批量猜测。

当用户询问某条提醒状态时，调用：

```bash
python3 /Users/administrator/Code/hermes-apple-calendar-assistant/scripts/hermes_outbox_cli.py status --id "<record_id>"
```

Outbox 安全边界：

- 当前阶段不真实发送微信。
- 当前阶段不真实发送 Telegram。
- 当前阶段 outbox 只是本地 dry-run 队列。
- Hermes 当前可以读取 pending outbox。
- Hermes 可以在用户明确确认后请求 dry-run 标记。
- Hermes 不应调用任何外部网络发送接口。
- Hermes 不应调用任何真实发送接口。
- Hermes 不得删除 outbox 记录。
- Hermes 不得修改 message 内容。
- Hermes 只能读取 pending、查看 status、把 pending 标记为 `sent_dry_run`。

## Flight Location Enhancement

Flight location enhancement has two modes:

- `飞行计划` location 自动增强由用户级 launchd 后台任务负责。
- Hermes 对话不负责持续监控。
- 普通 CRUD 不得写 `飞行计划`。

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
