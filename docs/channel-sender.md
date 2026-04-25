# Channel Sender

`scripts/channel_sender.py` 是真实发送前的通道适配抽象层。当前阶段只实现
`dry_run`，不真实发送消息，不调用 Telegram API，不调用微信 API，也不访问任何
外部网络。

## 当前支持范围

- `mode`: `dry_run`
- `channel`: `hermes`

当前配置中 `send_modes_supported` 只有 `dry_run`。`real` 是未来真实 Hermes 通道
发送的保留分支，本阶段不会发送。

如果 `mode` 是 `real`，无论 `real_send_enabled` 是否被误改，本阶段都会返回：

```json
{
  "ok": false,
  "data": null,
  "error": "real send is not implemented"
}
```

如果 `mode` 不是 `dry_run` 或 `real`，会返回 unsupported send mode 错误。

如果 `channel` 不是 `hermes`，会返回 unsupported channel 错误。

## 接口

`send_message(message, mode)` 是统一入口。当前分支：

- `dry_run`：转发到 `dry_run_send()`，返回 `sent_dry_run`。
- `real`：先检查 `real_send_enabled`，但本阶段仍返回
  `real send is not implemented`。
- 其他 mode：返回 unsupported send mode。

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

## send_mode 与 real_send_enabled

- `send_mode=dry_run`：当前唯一可用模式。
- `send_modes_supported=["dry_run"]`：声明本安装只支持 dry-run。
- `real_send_enabled=false`：真实发送总开关，默认关闭。
- `hermes_channel.enabled=false`：Hermes 真实通道保留配置，默认关闭。

为什么当前禁止真实发送：

- 还没有真实 Hermes dispatch 协议。
- 还没有投递确认、失败重试、速率限制和用户撤回策略。
- 还没有对真实 sender 做端到端权限与审计验证。
- 项目当前验收目标是本地 dry-run outbox，不是消息投递系统。

## Hermes 通道未来设计草案

未来 Hermes 真实通道可以沿用当前 payload：

```json
{
  "channel": "hermes",
  "recipient": "default",
  "message": "...",
  "metadata": {
    "type": "calendar_reminder",
    "fingerprint": "..."
  }
}
```

建议真实发送前必须完成：

- 将 `send_modes_supported` 显式扩展为包含真实模式。
- 将 `real_send_enabled` 由人工配置为 `true`。
- 将 `hermes_channel.enabled` 由人工配置为 `true`。
- 增加真实 sender 的失败重试、幂等、审计日志和回滚策略。
- 增加端到端验收，确认不会误发、重复发或绕过用户确认。
- 保持 Telegram/微信 sender 与 Hermes sender 解耦，不能混用凭据或 API。

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
