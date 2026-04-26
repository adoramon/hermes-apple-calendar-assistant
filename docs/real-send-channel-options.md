# Real Send Channel Options

当前状态：`v2.0-rc local dispatch dry-run`。本项目已经具备
`reminder_worker -> outbox -> outbox_consumer -> channel_sender -> hermes_dispatcher`
的本地 dry-run 链路，但仍不实现真实发送。

本文比较未来真实发送的候选方案，并记录当前推荐方向。

## 方案 A：Hermes 本地回调 / 本地 CLI

由 Hermes profile 自己负责最终发送，calendar assistant 只把 outbound message
交给 Hermes 本地接口。

优点：

- 安全边界清晰，符合 Skill 架构。
- 不把 Telegram token、微信凭据或其他发送凭据放进本项目。
- calendar assistant 不直接请求外部网络。
- 不绕过 Hermes 的统一调度、权限、审计和人工确认。
- 后续可以由 Hermes profile 决定是否展示、确认、发送或丢弃。

缺点：

- 需要确认 Hermes 是否有可调用的本地 dispatch 能力。
- 需要确认 `sunny-wechat-lite` 是否有 outbound message API。
- 需要确认 profile 内部是否需要新增 tool 或 handler。

Phase 29 补充结论：

- Hermes 内部已发现 `gateway.delivery.DeliveryRouter`。
- `DeliveryRouter` 真实发送依赖 gateway runtime 注入的 live adapters。
- 独立 Skill 脚本无法直接安全复用该 runtime。
- 因此推荐把真实发送继续放在 Hermes gateway / cron / profile-internal webhook
  中实现，而不是放在 calendar assistant 内。

## 方案 B：Telegram Bot API

calendar assistant 直接调用 Telegram Bot API 发送提醒。

优点：

- 实现简单。
- Telegram Bot API 文档成熟。

缺点：

- 需要在本项目中保存或读取 bot token。
- 需要外部网络请求。
- 绕过 Hermes 的统一调度和审计。
- 发送失败、重试、限流、权限和撤回都要在本项目重新实现。

当前结论：暂不选择。

## 方案 C：微信通道

通过 Hermes WeChat profile 或本地微信自动化发送提醒。

优点：

- 用户感知最好，提醒直接出现在微信链路中。

缺点：

- 风险最高，容易误发。
- 本地微信自动化链路复杂且脆弱。
- 真实发送、重试、撤回、账号状态和窗口焦点都可能带来不可控副作用。
- 如果 calendar assistant 直接驱动微信，会绕过 Hermes profile 的统一策略。
- 如果 calendar assistant 直接读取 `weixin/accounts` token 或复制 Weixin
  adapter 初始化逻辑，也会绕过 Hermes gateway 的权限和审计。

当前结论：暂不选择。

## 推荐方案

推荐方案 A：Hermes Cron Delivery / Hermes 本地回调。

选择原因：

- 不把 token 放进本项目。
- 不直接请求外部网络。
- 不绕过 Hermes。
- 后续可由 Hermes 做权限、审计、人工确认和最终投递。
- 与当前 `hermes_dispatcher.py` dry-run 占位方向一致。

Phase 30 补充结论：

- 已验证 `sunny-wechat-lite cron create --deliver "weixin:<chat_id>"` 可真实送达
  微信。
- 已验证链路：
  `Hermes Cron -> DeliveryRouter -> Weixin Adapter -> 微信`。
- 因此后续真实发送的优先落地方向应为 Hermes Cron Delivery，而不是 calendar
  assistant 直连微信。

## 实现前必须确认

- Hermes 是否支持本地 dispatch CLI。
- `sunny-wechat-lite` 是否有 outbound message API。
- 是否需要 profile 内部 tool。
- 是否需要用户二次确认。
- Hermes 如何记录发送审计和失败原因。
- Hermes 如何处理重复消息、撤回和紧急停用。
- Hermes cron / webhook 是否可在 runtime 内直接使用 delivery targets。

Phase 30 之后仍需继续确认：

- Cronjob Response 包装是否可接受，或是否需要后续优化展示方式。
- Cron 读取 outbox 时如何避免 empty outbox 输出。
- 如何做频率限制和重复发送控制。

在以上问题确认前，保持 `real_send_enabled=false`，不要启用真实发送。
