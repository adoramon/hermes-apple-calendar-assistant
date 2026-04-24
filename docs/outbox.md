# Outbox Dry Run Queue

`data/outbox_messages.jsonl` 是本地 dry run 消息队列，用来保存
`reminder_worker.py` 生成的 outbound message。当前阶段只落盘，不发送微信、
Telegram，也不访问任何外部网络。

## 作用

outbox 让提醒 Worker 和未来的发送器解耦：

- `reminder_worker.py` 负责扫描 Calendar 并生成提醒消息。
- `scripts/outbox.py` 负责把消息写入本地 JSONL 队列并提供查看命令。
- 后续 Hermes、Telegram 或 WeChat sender 可以读取这个队列，再决定如何发送。

## 写入 outbox

```bash
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

输出会包含本次写入数量和 `message_ids`。同一个 reminder fingerprint、
offset、channel、recipient 组合不会重复写入；重复项会进入 `skipped`，
reason 为 `already_in_outbox`。

## 查看 outbox

```bash
python3 scripts/outbox.py list --limit 20
```

每条 JSONL 记录格式：

```json
{
  "id": "sha1...",
  "created_at": "ISO时间",
  "status": "pending",
  "message": {
    "channel": "hermes",
    "recipient": "default",
    "message": "15分钟后：商务计划｜测试会议｜2026-04-27 15:00｜地点：...",
    "metadata": {}
  }
}
```

## 当前阶段边界

- 不发送真实消息
- 不调用 Telegram API
- 不调用微信
- 不接外部网络
- 不写 Apple Calendar
- 只写本地 `data/outbox_messages.jsonl`

## 后续 Hermes 消费方式

后续可以新增独立 sender，由 Hermes profile 定时或按需读取 outbox 中
`status=pending` 的记录，完成展示或发送后再由 sender 更新状态。本阶段不实现
状态流转，避免提前引入发送侧复杂度。
