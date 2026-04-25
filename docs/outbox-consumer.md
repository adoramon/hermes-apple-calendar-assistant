# Outbox Consumer Dry Run

`scripts/outbox_consumer.py` 是本地 outbox 的 dry-run 消费器。它只读取
`data/outbox_messages.jsonl` 中的 `pending` 记录，模拟“将要发送”的动作，然后把
状态更新为 `sent_dry_run`。

当前阶段不发送真实消息，不调用 Telegram、微信或任何外部网络。

## 查看 pending

先查看最近 outbox 记录：

```bash
python3 scripts/outbox.py list --limit 20
```

`status` 为 `pending` 的记录才会被 dry-run consumer 处理。已经是
`sent_dry_run` 的记录不会重复处理。

## 执行 dry-run

```bash
python3 scripts/outbox_consumer.py dry-run --limit 10
```

输出会列出本次模拟消费的消息：

```json
{
  "ok": true,
  "data": {
    "processed": [
      {
        "id": "sha1...",
        "channel": "hermes",
        "recipient": "default",
        "status": "sent_dry_run"
      }
    ],
    "skipped": []
  },
  "error": null
}
```

每条被处理的记录会写入：

```json
{
  "mode": "dry_run",
  "processed_at": "ISO时间"
}
```

## 安装 launchd

本仓库提供 dry-run consumer 的 launchd 模板，但不会自动安装：

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-outbox-consumer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

安装后每 1 分钟运行一次：

```bash
/usr/bin/python3 scripts/outbox_consumer.py dry-run --limit 10
```

## 卸载 launchd

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

## 查看状态

```bash
launchctl list | grep com.adoramon.hermes-apple-calendar-outbox-consumer
```

如果没有输出，通常表示任务未加载。

## 查看日志

```bash
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/outbox_consumer.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/outbox_consumer.err.log
```

## 手动触发一次

```bash
launchctl kickstart -k gui/$(id -u)/com.adoramon.hermes-apple-calendar-outbox-consumer
```

也可以直接运行：

```bash
python3 scripts/outbox_consumer.py dry-run --limit 10
```

## 当前阶段边界

- 不发送 Telegram
- 不发送微信
- 不接外部网络
- 不写 Apple Calendar
- 只更新本地 outbox 记录状态

## 后续接入方向

后续可以在 consumer 后面增加真正的 sender：

- Hermes sender：读取 `pending` 记录并交给 Hermes profile 展示或推送。
- Telegram sender：读取 outbox 后调用 Telegram API。
- WeChat sender：读取 outbox 后进入微信发送流程。

真实 sender 应继续保留幂等状态流转，避免同一条 outbox message 重复发送。
