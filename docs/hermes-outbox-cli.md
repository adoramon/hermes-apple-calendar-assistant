# Hermes Outbox CLI

`scripts/hermes_outbox_cli.py` 是给 Hermes Skill 调用的本地 outbox 接口。它只
操作 `data/outbox_messages.jsonl`，用于读取待展示消息、查看状态，以及把用户已
确认展示过的消息标记为 `sent_dry_run`。

当前阶段不真实发送，不调用 Telegram、微信或任何外部网络。

## 读取 pending

Hermes 可以读取待展示消息：

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

输出中的 `records[]` 包含 `id`、`channel`、`recipient`、`message` 和
`metadata`。Hermes 应把 `message` 展示给用户，并保留 `id` 以便后续标记。

## 展示给用户

Hermes 只负责把 pending 消息作为本地提醒展示出来。本阶段不调用外部 sender，
也不把消息交给 Telegram 或微信 API。

建议展示格式：

```text
提醒：15分钟后：商务计划｜测试会议｜2026-04-27 15:00
```

## 标记 dry-run sent

当 Hermes 已展示某条消息后，可以标记为 `sent_dry_run`：

```bash
python3 scripts/hermes_outbox_cli.py mark-dry-run-sent --id "<record_id>"
```

安全边界：

- 只允许 `pending -> sent_dry_run`
- 不允许标记为真实 `sent`
- 不删除记录
- 不修改 message 内容
- 不发送网络请求

## 查看状态

```bash
python3 scripts/hermes_outbox_cli.py status --id "<record_id>"
```

如果记录不存在，会返回：

```json
{
  "ok": false,
  "data": null,
  "error": "outbox_record_not_found"
}
```

## 后续真实发送边界

未来如果要接 Hermes 主动推送、Telegram 或 WeChat，应新增独立 sender，并继续
遵守 `config/settings.json` 中的 outbox 安全开关。这个 CLI 保持为 Hermes 本地
消费接口，不承担真实发送职责。
