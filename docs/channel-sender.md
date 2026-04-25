# Channel Sender

`scripts/channel_sender.py` 是真实发送前的通道适配抽象层。当前阶段只实现
`dry_run`，不真实发送消息，不调用 Telegram API，不调用微信 API，也不访问任何
外部网络。

## 当前支持范围

- `mode`: `dry_run`
- `channel`: `hermes`

如果 `mode` 不是 `dry_run`，会返回：

```json
{
  "ok": false,
  "data": null,
  "error": "real send is not implemented"
}
```

如果 `channel` 不是 `hermes`，会返回 unsupported channel 错误。

## 接口

`send_message(message, mode)` 是统一入口。当前只会转发到 `dry_run_send()`。

`dry_run_send(message)` 会校验 channel 和 recipient，然后返回本地 dry-run 结果，
不会发送网络请求。

`validate_channel(message)` 只允许 `hermes`。

`validate_recipient(message)` 要求 recipient 是非空字符串。

## outbox consumer 集成

`scripts/outbox_consumer.py dry-run` 现在通过 `channel_sender.send_message()` 执行
dry-run，再把 outbox 记录标记为 `sent_dry_run`。

```text
outbox_consumer
  -> channel_sender.send_message(mode=dry_run)
  -> dry_run_send
  -> outbox status: sent_dry_run
```

`sent_dry_run` 只表示本地 dry-run 消费完成，不代表真实发送完成。

## 配置

`config/settings.json` 中的 outbox 配置保持 dry-run：

```json
{
  "outbox": {
    "send_mode": "dry_run",
    "sender": "channel_sender",
    "allowed_channels": ["hermes"],
    "default_channel": "hermes",
    "default_recipient": "default",
    "max_messages_per_run": 10
  }
}
```

## 安全边界

- 不实现真实发送。
- 不接 Telegram API。
- 不接微信 API。
- 不发网络请求。
- 不修改 Apple Calendar。
- 不影响 `reminder_worker.py`。
- 不影响 `flight_auto_enhancer.py`。

未来如果增加真实 sender，应保持独立实现，并继续受 `send_mode`、
`allowed_channels` 和用户确认流程保护。
