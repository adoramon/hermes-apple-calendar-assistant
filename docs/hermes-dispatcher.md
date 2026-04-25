# Hermes Dispatcher

`scripts/hermes_dispatcher.py` 是本机 Hermes 消息调度占位接口。当前只支持
dry-run dispatch，不调用微信、不调用 Telegram、不发网络请求，也不修改 message
内容。

## CLI

```bash
python3 scripts/hermes_dispatcher.py dry-run --id "<outbox_record_id>"
```

行为：

- 读取 `data/outbox_messages.jsonl`
- 查找指定 outbox record
- 要求 record 状态必须为 `pending`
- 输出将要交给 Hermes 的 message payload
- 将 record 标记为 `sent_dry_run`
- 不真实发送任何外部消息

示例输出：

```json
{
  "ok": true,
  "data": {
    "id": "sha1...",
    "mode": "dry_run",
    "message": {
      "channel": "hermes",
      "recipient": "default",
      "message": "15分钟后：...",
      "metadata": {}
    },
    "status": "sent_dry_run"
  },
  "error": null
}
```

`sent_dry_run` 只表示本地 dry-run dispatch 已消费该 outbox record，不代表微信、
Telegram 或 Hermes push 已真实发送。

## 内部函数

`channel_sender.py` 不通过 subprocess 调用 CLI，而是直接调用
`hermes_dispatcher.dry_run_dispatch_message(message)`，用于构造 Hermes dry-run
payload 并返回 `sent_dry_run` 结果。

完整本机闭环：

```text
Apple Calendar
  -> reminder_worker
  -> message_adapter
  -> outbox_messages.jsonl
  -> outbox_consumer
  -> channel_sender
  -> hermes_dispatcher dry-run
  -> sent_dry_run
```

## 安全边界

- 不真实发送微信
- 不真实发送 Telegram
- 不请求外部网络
- 不修改 Calendar
- 不删除 outbox
- 不修改 message 内容
- 只允许 pending record 做 dry-run dispatch
