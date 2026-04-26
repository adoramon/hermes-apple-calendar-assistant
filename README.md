# hermes-apple-calendar-assistant

Apple Calendar Assistant 是一个 macOS-only Hermes custom skill，用于在
`sunny-wechat-lite` profile 中操作 Calendar.app。当前开发线是
`v2.0-rc local dispatch dry-run`。

## v2.0-rc Local Dispatch Dry-run

v2.0-rc local dispatch dry-run 已支持：

- 明确时间范围后查询 Apple Calendar 日程
- 确认式创建、修改、删除日程
- 自然语言日程草稿解析
- 创建草稿时可选冲突检测：`--check-conflict`
- 单日历冲突检测与建议时间段
- 提醒候选扫描：只输出 JSON，不主动发送消息
- reminder worker launchd 模板
- outbox dry-run 队列与 dry-run consumer
- outbox 真实发送前安全开关：`send_mode`、`allowed_channels`、
  `max_messages_per_run`
- 真实发送前 channel sender 抽象：当前仅支持 `dry_run` + `hermes`
- Hermes 本机 dispatch dry-run 占位：`scripts/hermes_dispatcher.py`
- Hermes 本地 outbox 读取接口：`pending`、`status`、`mark-dry-run-sent`
- `飞行计划` location 自动增强 launchd 后台任务

v2.0-beta dry-run readiness excludes:

- Birthday reminders
- Contacts, lunar birthday, or anniversary workflows
- Travel Time automation
- Reminder/alarm enhancement or notification delivery
- Native Swift helpers
- Extra preparation events for flights

Acceptance summary: the dry-run reminder/outbox chain has been validated for
local operation. It still does not send WeChat, Telegram, Hermes push, or any
external network message.

Real-send channel decision: prefer Hermes local callback / local CLI. Telegram
Bot API and direct WeChat automation are not selected for now because they would
introduce tokens, external network requests, or bypass Hermes scheduling and
audit. See [docs/real-send-channel-options.md](docs/real-send-channel-options.md)
and [docs/decision-records/ADR-001-real-send-channel.md](docs/decision-records/ADR-001-real-send-channel.md).

Phase 28 discovery update: the Hermes profile contains WeChat account/config
artifacts and a Weixin DM channel identifier, but this repository still must not
read or copy profile tokens, must not call `ilinkai.weixin.qq.com`, and must not
implement real WeChat sending until Hermes exposes a confirmed safe local
dispatch interface. See [docs/wechat-dispatch-discovery.md](docs/wechat-dispatch-discovery.md)
and [docs/decision-records/ADR-002-wechat-dispatch-discovery.md](docs/decision-records/ADR-002-wechat-dispatch-discovery.md).

Phase 29 technical research update: Hermes source contains
`gateway.delivery.DeliveryRouter`, but real delivery depends on gateway runtime
live adapters injected by `gateway/run.py`. Because this repository is an
independent Skill script, it still must not try to call real send directly,
must not replicate Weixin adapter initialization, and must not bypass Hermes
gateway permission and audit boundaries. See
[docs/hermes-delivery-router-research.md](docs/hermes-delivery-router-research.md)
and [docs/decision-records/ADR-003-hermes-delivery-router.md](docs/decision-records/ADR-003-hermes-delivery-router.md).

Phase 30 validation update: local testing confirmed that Hermes Cron Delivery
can reach WeChat through `Hermes Cron -> DeliveryRouter -> Weixin Adapter ->
微信`. This repository still must not read `weixin` token or call `ilink` /
Weixin APIs directly; the recommended future real-send architecture is Calendar
Skill outbox generation plus Hermes Cron `--deliver` inside the Hermes runtime.
See [docs/hermes-cron-delivery-test.md](docs/hermes-cron-delivery-test.md) and
[docs/decision-records/ADR-004-hermes-cron-delivery.md](docs/decision-records/ADR-004-hermes-cron-delivery.md).

Phase 31 bridge update: this repository now includes a read-only Hermes Cron
Outbox Bridge script for `cron --script`, which renders oldest `pending` outbox
records as plain text without changing outbox status. It is intended for
validation and integration preparation only; until Phase 32 adds status marking,
it must not be treated as a long-running real-send workflow. See
[docs/hermes-cron-outbox-bridge.md](docs/hermes-cron-outbox-bridge.md).

Phase 32 bridge update: the Hermes Cron Outbox Bridge now supports
`--mark-sent`, which marks selected `pending` records as
`sent_via_hermes_cron` after rendering them to stdout for Hermes Cron delivery.
Real WeChat sending is still completed by Hermes Cron Delivery, not by this
repository. The bridge still does not read Hermes tokens, does not call WeChat
APIs directly, and does not modify message content. See
[docs/hermes-cron-outbox-bridge.md](docs/hermes-cron-outbox-bridge.md).

Phase 33 enablement update: the Hermes Cron Outbox Bridge path is now the
active delivery path. `reminder_worker` launchd writes pending outbox messages,
Hermes Cron job `calendar-outbox-wechat-bridge` reads them with
profile script `~/.hermes/profiles/sunny-wechat-lite/scripts/calendar_outbox_bridge.py`,
and Hermes Cron Delivery sends them through DeliveryRouter and the Weixin
adapter. Different profiles should use their own `~/.hermes/profiles/<profile>/scripts/`
directory rather than a global Hermes scripts directory. `outbox_consumer`
dry-run launchd must remain paused so it does not consume pending messages
before the Cron bridge can deliver them. `sent_via_hermes_cron` means the
record was handed to Hermes Cron stdout for delivery and should not be sent
again by the bridge, but it is not a guarantee that downstream delivery
succeeded. See
[docs/hermes-cron-outbox-bridge.md](docs/hermes-cron-outbox-bridge.md),
[docs/hermes-profile-install.md](docs/hermes-profile-install.md), and
[docs/v2-rc-local-dispatch-acceptance.md](docs/v2-rc-local-dispatch-acceptance.md).

Phase 34 wrapper correction: Hermes `cron --script` in this setup reads Python
scripts from the profile-specific directory, so the wrapper must be
`calendar_outbox_bridge.py`, not a `.sh` shell wrapper. The wrapper is local
Hermes profile runtime configuration, not part of this repository, and different
profiles should keep their own wrapper under
`~/.hermes/profiles/<profile>/scripts/`.

Phase 38 reminder action update: WeChat reminder follow-up replies can now be
parsed into confirmation-required drafts. Replies such as `延后30分钟`, `取消这个日程`,
`改到明天上午10点`, `已到达`, `不再提醒`, and `提前30分钟提醒我` are handled through
`scripts/reminder_action_flow.py`. Drafting never modifies Calendar; cancel and
reschedule actions only execute after explicit confirmation. See
[docs/reminder-action-flow.md](docs/reminder-action-flow.md).

Phase 39 reminder action test update: Hermes WeChat interaction testing now
uses `延后30分钟`, `取消这个日程`, and `改到明天上午10点` as acceptance replies. The
expected behavior is always draft first, then explicit confirmation for delete
or reschedule. If a WeChat reply does not produce a draft, check
`~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log`,
`~/.hermes/profiles/sunny-wechat-lite/logs/gateway.error.log`, and
`python3 scripts/outbox.py list --limit 20`.

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
│       ├── com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
│       ├── com.adoramon.hermes-apple-calendar-reminder-worker.plist
│       └── com.adoramon.hermes-apple-calendar-outbox-consumer.plist
├── docs/
│   ├── reminder-worker.md
│   ├── flight-auto-enhancer.md
│   └── v2-roadmap.md
└── scripts/
    ├── calendar_ops.py
    ├── interactive_create.py
    ├── flight_parser.py
    ├── flight_watcher.py
    ├── flight_enhancer.py
    ├── flight_auto_enhancer.py
    ├── nlp_event_parser.py
    ├── conflict_checker.py
    ├── reminder_worker.py
    ├── upcoming_reminders.py
    ├── settings.py
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
python3 scripts/nlp_event_parser.py parse "明天下午三点和王总开会"
```

Check conflicts for a proposed event window:

```bash
python3 scripts/conflict_checker.py check --calendar "商务计划" --start "2026-04-27T15:00:00" --end "2026-04-27T16:00:00"
```

Scan reminder candidates:

```bash
python3 scripts/reminder_worker.py scan
```

Write outbound reminder messages into the local dry-run outbox:

```bash
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

Dry-run consume pending outbox messages:

```bash
python3 scripts/outbox_consumer.py dry-run --limit 10
```

Draft a reminder follow-up action:

```bash
python3 scripts/reminder_action_flow.py draft --text "延后30分钟"
python3 scripts/reminder_action_flow.py confirm --session-key "<session_key>"
```

Hermes WeChat reminder follow-up test replies:

- `延后30分钟`
- `取消这个日程`
- `改到明天上午10点`

Expected behavior: generate a draft first; do not modify Calendar during draft;
delete and reschedule require explicit second confirmation.

Hermes local outbox CLI:

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
python3 scripts/hermes_outbox_cli.py status --id "<record_id>"
python3 scripts/hermes_outbox_cli.py mark-dry-run-sent --id "<record_id>"
```

The Hermes CLI only reads pending messages, checks status, and marks pending
records as `sent_dry_run`. It cannot delete records, modify message content, mark
real `sent`, or send network requests.

Outbox safety switches live in `config/settings.json`:

```json
{
  "outbox": {
    "send_mode": "dry_run",
    "send_modes_supported": ["dry_run"],
    "real_send_enabled": false,
    "sender": "channel_sender",
    "allowed_channels": ["hermes"],
    "default_channel": "hermes",
    "default_recipient": "default",
    "max_messages_per_run": 10,
    "hermes_channel": {
      "enabled": false,
      "transport": "local_cli",
      "notes": "reserved for future real Hermes dispatch"
    }
  }
}
```

Final real-send gate:

```json
{
  "real_send_gate": {
    "enabled": false,
    "require_manual_config_change": true,
    "require_confirm_phrase": "ENABLE_REAL_SEND",
    "allowed_channels": [],
    "audit_required": true
  }
}
```

`send_mode` must remain `dry_run` in the current beta line. Any other value
returns `ok=false` because real sending is not implemented yet. The consumer also
skips channels outside `allowed_channels`, and caps each run by
`max_messages_per_run`. See [docs/channel-sender.md](docs/channel-sender.md) for
the pre-real-send channel sender abstraction and reserved Hermes channel design.
See [docs/real-send-gate.md](docs/real-send-gate.md) for the final real-send
gate, and [docs/rollback.md](docs/rollback.md) for rollback steps.

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

Flight auto enhancer 与 reminder worker 的区别：

- `flight_auto_enhancer.py` 只服务 `飞行计划`，会在允许边界内写回原事件
  `location` 字段，用于补充出发机场/航站楼。
- `reminder_worker.py` 只读所有 `read_calendars`，生成提醒候选 JSON，并用
  `data/reminder_seen.json` 做幂等；当前阶段不发送微信、Telegram 或系统通知。

Reminder scanning can also run as a launchd task:

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-reminder-worker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

The reminder worker launchd task runs every 1 minute and calls:

```bash
python3 scripts/reminder_worker.py scan
```

For the v2.0-beta dry-run outbox chain, reminder worker can also be run by
launchd with outbound outbox writing enabled:

```bash
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

In this mode it only reads Calendar.app and writes
`data/outbox_messages.jsonl`. It does not send WeChat, Telegram, or any external
network message. Install/uninstall is the same reminder worker LaunchAgent flow:

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-reminder-worker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

Logs:

```bash
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.err.log
```

Hermes can inspect pending outbox messages with:

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

See [docs/reminder-worker.md](docs/reminder-worker.md) for manual run,
install, uninstall, log, and `reminder_seen.json` reset instructions.

Outbox consumer dry-run can run as a separate launchd task:

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-outbox-consumer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

The outbox consumer launchd task runs every 1 minute and calls:

```bash
python3 scripts/outbox_consumer.py dry-run --limit 10
```

This launchd task only performs dry-run consumption: it reads pending records from
`data/outbox_messages.jsonl` and marks them as `sent_dry_run`. It does not send
WeChat, Telegram, Hermes push, or any external network message. `sent_dry_run`
means “consumed by the local dry-run consumer”, not “actually delivered”.

Uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

Logs:

```bash
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/outbox_consumer.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/outbox_consumer.err.log
```

Current dry-run reminder flow:

```text
Calendar.app
  -> reminder_worker.py scan --format outbound --write-outbox
  -> message_adapter.py
  -> data/outbox_messages.jsonl
  -> outbox_consumer.py dry-run --limit 10
  -> channel_sender.py dry_run
  -> hermes_dispatcher.py dry-run
  -> status: sent_dry_run
```

This flow still does not send Telegram, WeChat, or external network requests.
If `outbox_consumer` is enabled by launchd, it may consume pending outbox records
quickly; in that case `hermes_outbox_cli.py pending --limit 10` can be empty even
though reminders were scanned and marked `sent_dry_run`.
The outbox consumer is guarded by `send_mode=dry_run`, channel allow-listing, and
per-run message limits before any future real sender is added.
See [docs/outbox-consumer.md](docs/outbox-consumer.md) for launchd install,
uninstall, status, log, and manual trigger instructions.
See [docs/hermes-outbox-cli.md](docs/hermes-outbox-cli.md) for the Hermes-facing
local pending/status/mark interface. Hermes can also inspect pending outbox
before consumer dry-run processing with:

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

v2.0-beta 当前链路：

```text
Calendar.app
  ↓
reminder_worker
  ↓
message_adapter
  ↓
outbox_messages.jsonl
  ↓
outbox_consumer dry-run
  ↓
channel_sender
  ↓
hermes_dispatcher dry-run
  ↓
sent_dry_run
```

Hermes inspection path:

```text
outbox_messages.jsonl
  ↓
hermes_outbox_cli
  ↓
Hermes 展示 / 用户确认
```

## Verification

```bash
python3 -m py_compile scripts/*.py
python3 -m json.tool data/state.json
python3 -m json.tool data/pending_confirmations.json
python3 -m json.tool data/flight_seen.json
python3 -m json.tool data/flight_pending.json
python3 -m json.tool data/reminder_seen.json
launchctl list | grep com.adoramon.hermes-apple-calendar
tail -n 100 logs/reminder_worker.out.log
tail -n 100 logs/outbox_consumer.out.log
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
python3 scripts/outbox.py list --limit 20
tail -n 100 ~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log
tail -n 100 ~/.hermes/profiles/sunny-wechat-lite/logs/gateway.error.log
python3 scripts/outbox_consumer.py dry-run --limit 10
python3 scripts/flight_auto_enhancer.py run
python3 -m unittest tests.test_flight_parser
```

See [docs/v2-beta-acceptance.md](docs/v2-beta-acceptance.md) for the full
dry-run acceptance checklist and rollback commands.
See [docs/v2-rc-local-dispatch-acceptance.md](docs/v2-rc-local-dispatch-acceptance.md)
for the local dispatch dry-run acceptance checklist.
## Current Status

Stable from 1.0:

- Calendar CRUD
- Confirmation workflow
- WeChat skill integration
- Flight location enhancement
- launchd automatic flight location enhancement

Added through v2.0-beta dry-run accepted:

- Natural-language draft parsing
- Conflict detection
- Upcoming reminder candidate scanning
- Reminder worker idempotency and launchd template
- Local outbox queue, dry-run consumer, and Hermes local outbox CLI

Still out of scope:

- Contacts reminders
- Birthday workflows
- Travel Time
