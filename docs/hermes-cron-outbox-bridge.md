# Hermes Cron Outbox Bridge

当前状态：`v2.0-rc local dispatch dry-run`。

`scripts/hermes_cron_outbox_bridge.py` 是一个专门给 Hermes cron `--script` 调用的
outbox bridge。它读取本地 `pending` outbox，输出适合 Hermes Cron Delivery 发送
的纯文本；在显式传入 `--mark-sent` 时，会把已输出记录标记为
`sent_via_hermes_cron`。

## 功能说明

CLI：

```bash
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent
```

行为：

- 读取 `data/outbox_messages.jsonl`
- 找出 `status=pending` 的记录
- 按 `created_at` 升序输出
- 最多输出 `limit` 条
- 输出适合 Hermes Cron Delivery 的纯文本
- 默认 `--empty-mode silent`，无 pending 时 stdout 为空，避免无意义通知
- 仅在传入 `--mark-sent` 时，才把已输出记录标记为 `sent_via_hermes_cron`

可选参数：

```bash
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode silent
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode message
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent --empty-mode silent
```

- `silent`：无 pending 时 stdout 为空
- `message`：无 pending 时输出 `当前没有待发送日历提醒。`
- `--mark-sent`：输出后把这些记录标记为 `sent_via_hermes_cron`

示例输出：

```text
日历提醒：
1. 15分钟后：商务计划｜测试会议｜2026-04-27 15:00｜地点：国贸
2. 60分钟后：家庭计划｜接孩子｜2026-04-27 18:00
```

## 手动测试命令

```bash
python3 -m py_compile scripts/*.py
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode message
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent --empty-mode message
python3 scripts/outbox.py list --limit 20
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode message
python3 scripts/flight_auto_enhancer.py run
```

## 如何创建 Hermes cron job

```bash
sunny-wechat-lite cron create "every 5m" \
  --name "calendar-outbox-wechat-bridge" \
  --script "/Users/administrator/Code/hermes-apple-calendar-assistant/scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent --empty-mode silent" \
  --deliver "weixin:<chat_id>"
```

推荐在 Hermes profile 内部使用 cron `--script` 读取 outbox，并把 stdout 通过
`--deliver` 投递到 `weixin:<chat_id>`。

## 当前阶段边界

- 默认行为仍可只读 `pending`，不标记 `sent`。
- 传入 `--mark-sent` 时，bridge 会在输出后将这些记录标记为
  `sent_via_hermes_cron`。
- 本阶段不删除 outbox。
- 本阶段不发送网络请求。
- 本阶段不读取 Hermes token。
- 本阶段不直连 WeChat / Telegram。

bridge 写入的 result 结构为：

```json
{
  "mode": "hermes_cron",
  "processed_at": "ISO时间",
  "note": "Message handed to Hermes Cron stdout for delivery"
}
```

## 为什么默认使用 empty-mode silent

`--empty-mode silent` 的作用是：当当前没有 `pending` outbox 时，bridge 输出空字
符串，从而避免 Hermes Cron Delivery 发送“没有提醒”的无意义通知。

如果需要手动验证 bridge 是否正常工作，可在测试时使用
`--empty-mode message`。

## 正式启用建议

- `--mark-sent` 表示交给 Hermes Cron stdout 后即标记 `sent_via_hermes_cron`。
- 如果 Hermes Cron Delivery 之后失败，目前无法自动回滚。
- 因此建议先用低频率、`limit=1` 验证。

## 风险说明

- `--mark-sent` 的标记时点早于 Hermes 最终投递结果。
- 如果 Hermes Cron Delivery 之后失败，目前无法自动回滚。
- 如果不传 `--mark-sent`，`pending` 会重复发送。
- 正式启用时仍建议从低频率、小 `limit` 开始。
