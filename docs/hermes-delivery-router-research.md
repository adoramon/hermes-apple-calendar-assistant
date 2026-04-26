# Hermes DeliveryRouter Real-send Research

当前状态：`v2.0-rc local dispatch dry-run`。

本文档记录 Phase 29 对 Hermes `gateway.delivery.DeliveryRouter` 的技术预研结
果。本文档只记录结构发现、架构边界和后续建议，不实现真实发送。

## 已确认结构

根据当前源码探查，Hermes 中存在 `gateway.delivery.DeliveryRouter`，并具备以下
结构特征：

- `DeliveryTarget.parse("weixin:<chat_id>")` 可解析 delivery target。
- `DeliveryRouter.deliver(content, targets, metadata)` 提供统一投递入口。
- `_deliver_to_platform(...)` 最终调用：
  `adapter.send(target.chat_id, content, metadata=...)`
- `gateway/run.py` 会在 gateway 运行时把 live adapters 注入
  `delivery_router.adapters`
- Weixin adapter 位于 `gateway/platforms/weixin.py`

这些发现说明 Hermes 内部已经存在真实发送所需的 delivery abstraction，但它依赖
gateway 运行时上下文，而不是独立 skill 脚本的静态调用。

## 为什么当前不能在独立 Skill 中直接调用真实发送

`hermes-apple-calendar-assistant` 是独立 Skill 脚本，不运行在 Hermes gateway 的 live
adapter 注入上下文中。

因此当前不能在 Skill 中直接调用 `DeliveryRouter` 真实发送，原因包括：

- 没有 live adapters。独立 Skill 无法直接获得 `gateway/run.py` 注入的
  `delivery_router.adapters`。
- 不能读取 profile token。Weixin adapter 的凭据属于 Hermes profile 私密配置，不应
  被本项目读取。
- 不应复制 Weixin adapter 初始化逻辑。即使源码可见，也不应在本项目中重建 adapter
  初始化流程。
- 不能绕过 Hermes gateway 的权限和审计。若 Skill 直接拼装 adapter 或自行发请求，
  会绕过 Hermes 的统一调度、权限控制、审计和后续确认策略。

## 当前技术结论

Hermes 内部存在可用于真实发送的 `DeliveryRouter` 机制，但当前它属于 Hermes
gateway runtime capability，不属于本项目这个独立 Skill 的直接调用能力。

因此，当前仍不能在本项目中实现真实发送。

## 当前推荐链路

继续保持 dry-run：

```text
reminder_worker
  -> outbox
  -> outbox_consumer
  -> channel_sender
  -> hermes_dispatcher dry-run
```

该链路继续负责本地提醒生成、outbox 记录、dry-run 消费和占位式 Hermes handoff，
不承担真实 Weixin 投递。

## 推荐路线

### 方案 A：优先

让 Hermes gateway / cron 原生调用 `DeliveryRouter` 发送 outbox 消息。

理由：

- 真实发送发生在 Hermes 自己的 gateway runtime 中。
- live adapters 由 Hermes 自己注入。
- token、权限、审计和平台适配都继续留在 Hermes 内部。

### 方案 B：次选

写一个 Hermes profile 内部 webhook / cron job，让它读取 outbox 并调用 gateway
delivery。

理由：

- 仍由 Hermes profile 内部完成真实发送。
- Calendar Skill 继续只负责 outbox 生产，不负责 adapter 初始化和真实投递。

### 方案 C：不推荐

Calendar Skill 直接读取 `weixin/accounts` token 并调用 ilink API。

不推荐原因：

- 会让本项目接触 Hermes profile 私密 token。
- 会复制或绕过 Hermes Weixin adapter 和 gateway runtime。
- 会绕过 Hermes 的统一权限、审计和调度边界。
- 会把真实发送、失败重试、限流和风控复杂度错误地下沉到本项目。

## Phase 30 建议

- 探查 Hermes cron 是否支持 delivery targets。
- 尝试用 Hermes cron / webhook 触发“读取 outbox 并回复到 weixin home channel”。
- 确认该链路是否能够在不暴露 token 的前提下复用 Hermes gateway delivery。
- 在上述能力确认前，继续保持 `real_send_enabled=false` 和
  `real_send_gate.enabled=false`。
