# Real Send Gate

`real_send_gate` 是真实发送前的最终安全闸门。它的目的不是开启真实发送，而是确保
未来即使有人误改 `send_mode=real`，系统也不会绕过人工确认、channel 白名单和
审计要求。

当前阶段仍不实现真实发送。

## 配置

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

字段说明：

- `enabled`：最终真实发送闸门。默认 `false`。
- `require_manual_config_change`：要求真实发送必须经过人工配置变更。默认 `true`。
- `require_confirm_phrase`：调用方必须传入的确认短语。默认
  `ENABLE_REAL_SEND`。
- `allowed_channels`：真实发送允许的 channel。默认空列表，不允许任何 channel。
- `audit_required`：真实发送前必须具备审计记录。默认 `true`。

## 当前行为

`scripts/channel_sender.py` 在 `mode=real` 时必须检查：

- `outbox.real_send_enabled=true`
- `real_send_gate.enabled=true`
- message channel 在 `real_send_gate.allowed_channels`
- 调用方传入的 `confirm_phrase` 等于 `require_confirm_phrase`

任一条件不满足都会返回 `ok=false`。即使全部满足，本阶段仍返回：

```json
{
  "ok": false,
  "data": null,
  "error": "real send adapter not implemented"
}
```

这意味着真实发送 adapter 尚未实现，系统不会发送微信、Telegram、Hermes push 或
任何外部网络消息。

## outbox consumer real 模式

可以执行阻断验证：

```bash
python3 scripts/outbox_consumer.py --mode real --confirm-phrase ENABLE_REAL_SEND --limit 1
```

如果存在 pending outbox 记录，consumer 会把该记录标记为
`failed_real_send_blocked`，并在 `result.reason` 中记录阻断原因。它不会标记为
`sent`，也不会删除 outbox 记录。

## 未来启用真实发送前检查清单

- 明确真实 Hermes dispatch 协议。
- 增加真实 sender adapter，并完成端到端测试。
- 保持 `real_send_gate.allowed_channels` 最小化。
- 审计 outbox 状态流转和失败原因。
- 验证失败重试、限流、撤回和紧急停用策略。
- 确认不会绕过用户确认或 SKILL 安全规则。
- 保留 dry-run 回滚路径。

在上述清单完成前，不应把 `real_send_enabled` 或 `real_send_gate.enabled` 改为
`true`。
