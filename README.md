# Hermes Apple Calendar Assistant

Language: [中文](#中文) | [English](#english)

## 中文

Hermes Apple Calendar Assistant 是一个面向 macOS Calendar.app 的 Hermes
自定义 Skill。它把微信或其他 Hermes 输入转成安全的日程查询、草稿、确认式写入、
提醒摘要和出行摘要。

本仓库只保存代码、文档和配置模板。运行时数据位于 `data/`，已被 `.gitignore`
忽略，避免把真实日程、地点、航班、消息内容或待确认草稿提交到 GitHub。

### 当前状态

- 版本线：`v2.0-rc wechat voice attachment sealed`
- 平台：macOS only
- Python：3.11+
- Calendar 访问：AppleScript / `osascript`
- Hermes profile：由本机运行环境配置，本 README 不记录个人 profile 名称或 token

### 核心能力

- 查询 Apple Calendar 日程，必须有明确时间范围。
- 通过自然语言生成日程草稿。
- 创建、修改、删除日程都必须先展示确认摘要。
- 删除日程需要二次确认，并按 `calendar + title + start + end` 精确删除。
- 支持冲突检测和建议时间段。
- 支持本地提醒扫描、outbox 队列和 Hermes Cron bridge 投递。
- 支持酒店、交通、会议等出行订单文本聚合成 Trip 草稿。
- 支持一句话出差/旅行计划草稿。
- 支持 Trip 行前摘要提醒。
- 支持微信语音输入经 Hermes ASR 转文字后进入日程/Trip/提醒路由。

### 安全边界

- 不读取微信 token。
- 不直连微信 API。
- 不请求外部网络查询航班、酒店或价格。
- 不订票、不订酒店。
- 不写 Apple Reminders。
- 不跳过确认直接创建、修改或删除 Calendar 事件。
- 不创建航班日程。
- 受保护航班日历只读；唯一例外是专用航班位置增强脚本可更新原航班事件的
  `location` 字段。
- 运行时 `data/*.json` 和 `data/*.jsonl` 不进入 Git。

### 日历配置

请在 `config/settings.json` 中配置本机日历名称。README 使用通用占位符：

- `READ_CALENDARS`：允许查询的日历列表。
- `WRITE_CALENDARS`：允许普通创建/修改/删除的日历列表。
- `PROTECTED_FLIGHT_CALENDAR`：由外部航班工具同步的受保护航班日历。

不要把真实个人日历名、客户名、地点或订单信息写进 README、issue、commit message
或公开文档。

### 目录结构

```text
hermes-apple-calendar-assistant/
├── AGENTS.md
├── README.md
├── SKILL.md
├── config/
│   └── settings.json
├── data/
│   └── .gitkeep
├── deploy/
│   └── launchd/
├── docs/
├── scripts/
└── tests/
```

### 常用命令

列出日历：

```bash
python3 scripts/calendar_ops.py calendars
```

查询日程：

```bash
python3 scripts/calendar_ops.py events "<CALENDAR_NAME>" \
  --start "2026-04-28T00:00:00" \
  --end "2026-04-29T00:00:00"
```

创建待确认日程草稿：

```bash
python3 scripts/interactive_create.py create-draft \
  --session-key "<SESSION_KEY>" \
  --calendar "<CALENDAR_NAME>" \
  --title "<EVENT_TITLE>" \
  --start "2026-04-28T15:00:00" \
  --end "2026-04-28T16:00:00" \
  --location "<LOCATION>" \
  --notes "<NOTES>"
```

确认或取消草稿：

```bash
python3 scripts/interactive_create.py confirm --session-key "<SESSION_KEY>"
python3 scripts/interactive_create.py cancel --session-key "<SESSION_KEY>"
```

自然语言解析为日程草稿：

```bash
python3 scripts/nlp_event_parser.py parse "明天下午三点开会"
```

冲突检测：

```bash
python3 scripts/conflict_checker.py check \
  --calendar "<CALENDAR_NAME>" \
  --start "2026-04-28T15:00:00" \
  --end "2026-04-28T16:00:00"
```

提醒扫描：

```bash
python3 scripts/reminder_worker.py scan
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

查看 outbox：

```bash
python3 scripts/outbox.py list --limit 20
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

查询自然语言日程：

```bash
python3 scripts/schedule_query_router.py query --text "我明天什么安排"
```

航班位置增强：

```bash
python3 scripts/flight_auto_enhancer.py run
```

Trip 草稿和摘要：

```bash
python3 scripts/trip_planner.py draft --text "下周去<CITY>出差，两天"
python3 scripts/trip_briefing_worker.py scan --hours 48
```

### 微信语音策略

当前封板策略是文字优先：

- 默认只回文字。
- 用户明确要求语音回复时，Hermes 可发送可见音频附件。
- 静音、驾驶或只文字模式不追加音频附件。
- 当前 Weixin iLink 出站原生 voice 气泡可能被客户端静默丢弃，因此可靠降级是音频附件。
- 附件不应带英文 caption，文件名应使用通用中文名称。

详见 [docs/wechat-voice-secretary.md](docs/wechat-voice-secretary.md) 和
[docs/wechat-voice-validation.md](docs/wechat-voice-validation.md)。

### 部署

1. 确保 macOS 已允许终端或 Hermes 运行环境通过 AppleScript 访问 Calendar.app。
2. 在 Hermes profile 中安装或引用本仓库的 `SKILL.md`。
3. 按需安装 `deploy/launchd/` 下的 launchd 模板。
4. launchd 模板中的路径应按本机仓库位置调整。
5. 不要把 profile token、真实 chat id 或账号文件复制到本仓库。

### 验证

```bash
python3 -m py_compile scripts/*.py
python3 scripts/schedule_query_router.py query --text "我明天什么安排"
python3 scripts/flight_auto_enhancer.py run
python3 -m unittest discover tests
```

如果需要检查运行时 JSON，可在本机执行：

```bash
python3 -m json.tool data/pending_confirmations.json
```

注意：`data/` 文件只用于本机运行，不应提交。

### 隐私说明

- `data/*.json`、`data/*.jsonl` 已从 Git 历史清理，并被 `.gitignore` 忽略。
- 新增样例请使用 `<EVENT_TITLE>`、`<LOCATION>`、`<CALENDAR_NAME>`、
  `<CITY>` 等占位符。
- 不要在 README 或公开文档中写入真实姓名、日历名称、地点、订单号、航班号、
  chat id、token 或 profile 私有路径。

## English

Hermes Apple Calendar Assistant is a macOS-only Hermes custom skill for
Calendar.app. It turns Hermes inputs, including chat and voice-transcribed text,
into safe calendar queries, confirmation-required drafts, reminders, and trip
summaries.

This repository stores source code, documentation, and configuration templates
only. Runtime files under `data/` are ignored by Git so real events, locations,
flight details, messages, and pending drafts are not committed to GitHub.

### Status

- Release line: `v2.0-rc wechat voice attachment sealed`
- Platform: macOS only
- Python: 3.11+
- Calendar access: AppleScript / `osascript`
- Hermes profile: configured locally; this README does not include profile
  names, tokens, or private account data

### Features

- Query Apple Calendar events when a time range is known.
- Parse natural-language event requests into drafts.
- Require explicit confirmation before create, update, or delete operations.
- Require a second confirmation for deletion.
- Delete by exact `calendar + title + start + end` identity.
- Detect event conflicts and suggest alternative slots.
- Scan reminder candidates and write local outbox messages.
- Aggregate travel orders into Trip drafts.
- Create local Trip planning drafts from one-sentence travel intent.
- Generate pre-trip briefing messages.
- Route WeChat voice input through the existing Hermes ASR pipeline before
  calendar, Trip, or reminder handling.

### Safety Boundaries

- Do not read WeChat tokens.
- Do not call WeChat APIs directly.
- Do not request external flight, hotel, or pricing data.
- Do not book tickets or hotels.
- Do not write Apple Reminders.
- Do not skip confirmation for Calendar writes.
- Do not create flight events.
- The protected flight calendar is read-only, except for the dedicated flight
  location enhancer, which may update the original event `location` field.
- Runtime `data/*.json` and `data/*.jsonl` files must not be committed.

### Calendar Configuration

Configure local calendar names in `config/settings.json`. This README uses
generic placeholders:

- `READ_CALENDARS`: calendars allowed for queries.
- `WRITE_CALENDARS`: calendars allowed for normal create/update/delete.
- `PROTECTED_FLIGHT_CALENDAR`: the read-only flight calendar synchronized by an
  external flight source.

Do not put real calendar names, customer names, locations, or order details in
README files, issues, commit messages, or public documentation.

### Project Layout

```text
hermes-apple-calendar-assistant/
├── AGENTS.md
├── README.md
├── SKILL.md
├── config/
│   └── settings.json
├── data/
│   └── .gitkeep
├── deploy/
│   └── launchd/
├── docs/
├── scripts/
└── tests/
```

### Common Commands

List calendars:

```bash
python3 scripts/calendar_ops.py calendars
```

Query events:

```bash
python3 scripts/calendar_ops.py events "<CALENDAR_NAME>" \
  --start "2026-04-28T00:00:00" \
  --end "2026-04-29T00:00:00"
```

Create a confirmation-required draft:

```bash
python3 scripts/interactive_create.py create-draft \
  --session-key "<SESSION_KEY>" \
  --calendar "<CALENDAR_NAME>" \
  --title "<EVENT_TITLE>" \
  --start "2026-04-28T15:00:00" \
  --end "2026-04-28T16:00:00" \
  --location "<LOCATION>" \
  --notes "<NOTES>"
```

Confirm or cancel a draft:

```bash
python3 scripts/interactive_create.py confirm --session-key "<SESSION_KEY>"
python3 scripts/interactive_create.py cancel --session-key "<SESSION_KEY>"
```

Parse natural language into an event draft:

```bash
python3 scripts/nlp_event_parser.py parse "meeting tomorrow at 3pm"
```

Check conflicts:

```bash
python3 scripts/conflict_checker.py check \
  --calendar "<CALENDAR_NAME>" \
  --start "2026-04-28T15:00:00" \
  --end "2026-04-28T16:00:00"
```

Scan reminders:

```bash
python3 scripts/reminder_worker.py scan
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

Inspect outbox messages:

```bash
python3 scripts/outbox.py list --limit 20
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

Run a natural-language schedule query:

```bash
python3 scripts/schedule_query_router.py query --text "what is my schedule tomorrow"
```

Run flight location enhancement:

```bash
python3 scripts/flight_auto_enhancer.py run
```

Draft a Trip plan and scan briefings:

```bash
python3 scripts/trip_planner.py draft --text "business trip to <CITY> next week for two days"
python3 scripts/trip_briefing_worker.py scan --hours 48
```

### WeChat Voice Policy

The sealed behavior is text-first:

- Text replies are the default.
- Audio is sent only when the user explicitly asks for a voice reply.
- Silent, driving, or text-only modes do not append audio.
- Native outbound Weixin voice bubbles may be silently dropped by the iLink
  client, so a visible audio attachment is the reliable fallback.
- Audio attachments should use a generic Chinese filename and no English
  caption.

See [docs/wechat-voice-secretary.md](docs/wechat-voice-secretary.md) and
[docs/wechat-voice-validation.md](docs/wechat-voice-validation.md).

### Deployment

1. Grant Calendar.app automation permission to the terminal or Hermes runtime.
2. Install or reference `SKILL.md` from the local Hermes profile.
3. Install launchd templates from `deploy/launchd/` only when needed.
4. Adjust launchd paths for the local repository path.
5. Do not copy profile tokens, real chat ids, or account files into this repo.

### Verification

```bash
python3 -m py_compile scripts/*.py
python3 scripts/schedule_query_router.py query --text "what is my schedule tomorrow"
python3 scripts/flight_auto_enhancer.py run
python3 -m unittest discover tests
```

To inspect runtime JSON locally:

```bash
python3 -m json.tool data/pending_confirmations.json
```

Runtime files under `data/` are local-only and should not be committed.

### Privacy Notes

- `data/*.json` and `data/*.jsonl` were removed from Git history and are ignored.
- Use placeholders such as `<EVENT_TITLE>`, `<LOCATION>`, `<CALENDAR_NAME>`,
  and `<CITY>` in examples.
- Do not publish real names, calendar names, locations, order numbers, flight
  numbers, chat ids, tokens, or private profile paths.
