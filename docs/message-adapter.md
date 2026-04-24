# Message Adapter

`scripts/message_adapter.py` converts local reminder candidates into standard
outbound message payloads. It does not send messages and does not access any
external network.

## raw 输出用途

`reminder_worker.py scan` 默认输出 raw 格式：

```bash
python3 scripts/reminder_worker.py scan
```

raw 输出用于本地调试、幂等检查和后续业务逻辑处理，保留 reminder worker 原始
字段，例如 `scan_minutes`、`offsets`、`reminders` 和 `skipped`。

## outbound 输出用途

outbound 格式用于为 Hermes、Telegram、WeChat 等后续通道准备统一消息结构：

```bash
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default
```

输出中的每条 `messages[]` 包含：

- `channel`
- `recipient`
- `message`
- `metadata`

`metadata.type` 当前为 `calendar_reminder`，并携带日历、标题、时间、地点、
offset 和 fingerprint。

## 后续接入方向

- Hermes：读取 outbound JSON 后，由 Hermes profile 决定如何展示给用户。
- Telegram：后续可添加独立 sender，读取 outbound payload 后再调用 Telegram API。
- WeChat：后续可添加独立 sender，读取 outbound payload 后再进入微信发送流程。

## 当前阶段边界

- 不发送 Hermes 消息
- 不调用 Telegram API
- 不调用微信
- 不接外部网络
- 不修改 Calendar.app
- 只做本地 JSON 输出适配
