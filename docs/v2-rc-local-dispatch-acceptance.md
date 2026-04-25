# v2.0-rc Local Dispatch Dry-run Acceptance

当前状态：`v2.0-rc local dispatch dry-run`。

本阶段完成 Hermes 本机调度闭环准备，但仍不真实发送微信、Telegram 或任何外部
网络消息。

## 完整链路

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

`sent_dry_run` 只表示本地 dry-run 消费完成，不代表真实发送。

## 安全边界

- 不真实发送微信
- 不真实发送 Telegram
- 不请求外部网络
- 不修改 Calendar
- 不删除 outbox
- 不修改 message 内容
- 不引入第三方依赖

## 验收命令

```bash
python3 -m py_compile scripts/*.py
python3 -m json.tool config/settings.json
python3 -m json.tool data/outbox_messages.jsonl || true
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
python3 scripts/outbox.py list --limit 20
python3 scripts/outbox_consumer.py dry-run --limit 10
python3 scripts/outbox.py list --limit 20
python3 scripts/flight_auto_enhancer.py run
```

`data/outbox_messages.jsonl` 是 JSONL，不是单个 JSON 文档；当文件为空或多行时，
`json.tool` 可能失败，因此验收命令允许 `|| true`。

## 如果没有 pending 记录

如果当前没有即将到来的提醒，`reminder_worker` 可能不会写入 pending outbox。可以
用以下本地命令制造一条测试 pending 记录：

```bash
python3 - <<'PY'
from scripts import outbox

message = {
    "channel": "hermes",
    "recipient": "default",
    "message": "dry-run 测试提醒",
    "metadata": {
        "type": "calendar_reminder",
        "fingerprint": "local-dispatch-test:15",
        "offset_minutes": 15,
    },
}
print(outbox.append_outbox_message(message))
PY
```

随后运行：

```bash
python3 scripts/outbox.py list --limit 20
python3 scripts/outbox_consumer.py dry-run --limit 10
python3 scripts/outbox.py list --limit 20
```

## 后续真实发送前缺口

- 真实 Hermes dispatch 协议尚未实现。
- `real_send_enabled` 必须继续保持 `false`。
- 还需要真实发送审计、失败重试、速率限制和撤回/停用方案。
- 还需要端到端验收，确认不会误发、重复发或绕过用户确认。
