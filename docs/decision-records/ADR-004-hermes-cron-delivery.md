# ADR-004: Hermes Cron Delivery Path

## Status

Accepted for validation record. Not implemented in this repository.

## Context

Phase 30 已完成 Hermes Cron Delivery 的本机验证。

验证命令模板：

```bash
sunny-wechat-lite cron create "1m" "请只回复：Hermes cron delivery test" \
  --name "wechat-delivery-test" \
  --deliver "weixin:<chat_id>"

sunny-wechat-lite cron tick
sunny-wechat-lite cron list
```

验证结果：微信成功收到 `Cronjob Response` 包装消息，说明 Hermes Cron 可经由
`DeliveryRouter` 和 Weixin adapter 完成真实投递。

## Decision

确认 Hermes Cron Delivery 可作为后续真实微信提醒发送路径。

Calendar Skill 继续只负责 outbox 生成，不直接读取 `weixin` token，不直连
`ilink` / Weixin API。

后续真实发送如继续推进，优先采用：

```text
Calendar Skill
  -> outbox
  -> Hermes Cron job
  -> cron script stdout
  -> Hermes Cron --deliver
  -> weixin:<chat_id>
```

## Rationale

- token 继续留在 Hermes profile 内。
- 真实投递走 Hermes 原生 `DeliveryRouter`。
- Hermes Cron 自带 job 管理和一定的审计能力。
- 不需要在本项目复制 Weixin adapter 或网关逻辑。
- 不绕过 Hermes gateway。

## Risks

- Cron 输出会带 `Cronjob Response` 包装。
- 需要做频率控制，避免提醒轰炸。
- 需要处理重复发送。
- 需要处理 empty outbox。

## Consequences

- 本项目当前仍保持 dry-run，不在本阶段启用真实发送。
- `scripts/hermes_dispatcher.py` 继续保持 dry-run 占位。
- `real_send_enabled` 继续保持 `false`。
- `real_send_gate.enabled` 继续保持 `false`。
- Phase 31 应优先验证“cron script 读取 outbox + --deliver”这一集成路径。
