# ADR-003: Hermes DeliveryRouter Boundary

## Status

Accepted for technical research record. Not implemented.

## Context

Phase 29 对 Hermes `gateway.delivery.DeliveryRouter` 做了结构性预研。

目前已知：

- `DeliveryTarget.parse("weixin:<chat_id>")` 可构造 Weixin target
- `DeliveryRouter.deliver(content, targets, metadata)` 是统一投递入口
- `_deliver_to_platform(...)` 最终调用 `adapter.send(...)`
- `gateway/run.py` 会在运行时把 live adapters 注入 `delivery_router.adapters`
- Weixin adapter 位于 `gateway/platforms/weixin.py`

与此同时，本项目仍然是独立 Skill 脚本，不运行在 Hermes gateway runtime 内。

## Decision

不在本项目中直接调用 `DeliveryRouter` 进行真实发送。

不复制 Weixin adapter 初始化逻辑。

不读取 Hermes profile token。

真实发送如需继续推进，应优先让 Hermes gateway / cron / profile-internal
webhook 在 Hermes 自身运行时内调用 `DeliveryRouter`。

## Rationale

- `DeliveryRouter` 依赖 gateway runtime 注入的 live adapters。
- 独立 Skill 脚本无法安全获得这些 live adapters。
- Weixin adapter 所需凭据属于 Hermes profile 私密配置，不应进入本项目。
- 在 Skill 中重建 adapter 初始化会复制 Hermes 内部实现并绕过统一审计边界。
- 真实发送应继续由 Hermes 控制权限、调度、审计、确认和平台适配。

## Consequences

- 本项目继续保持 dry-run 链路，不升级为真实 Weixin sender。
- `scripts/hermes_dispatcher.py` 继续保持 dry-run 占位。
- `real_send_enabled` 必须继续保持 `false`。
- `real_send_gate.enabled` 必须继续保持 `false`。
- 后续真实发送能力只能建立在 Hermes runtime 内部的正式调用路径之上。

## Preferred Next Step

- 优先探索 Hermes gateway / cron 是否能原生消费 outbox 并调用
  `DeliveryRouter`。
- 次选探索 profile 内部 webhook / cron job 读取 outbox 后再调用 gateway
  delivery。
- 不选择由 Calendar Skill 直接读取 `weixin/accounts` token 并直连 ilink API 的
  方案。
