# ADR-002: WeChat Dispatch Discovery Boundary

## Status

Accepted for discovery record. Not implemented.

## Context

Phase 28 对 Hermes WeChat dispatch capability 进行了只读发现性梳理。

目前已知：

- `sunny-wechat-lite` profile 下存在 `weixin/accounts/*.json`
- account JSON 包含 `base_url`、`user_id`、`token`
- `channel_directory.json` 中存在 Weixin DM channel：
  `o9cq80yt8Tq__PY5jHlu0g0Q_xn0@im.wechat`

同时，当前仍未确认 Hermes 是否提供正式、安全、可审计的本地 dispatch/send CLI
或等价接口。

## Decision

不在本项目中实现 WeChat 真实发送。

不读取、复制或写入 Hermes profile token。

不在本项目中直接请求 WeChat / `ilinkai.weixin.qq.com` API。

继续保持本项目的本地 dry-run 链路：

```text
reminder_worker
  -> outbox
  -> outbox_consumer
  -> dry-run
```

## Rationale

- Hermes profile token 属于私密配置，不应进入本项目代码或配置。
- Skill 边界应保持在 Calendar、draft、outbox 和本地 dry-run。
- 直接请求 WeChat API 会绕过 Hermes 的权限、审计、调度和确认机制。
- 在未确认 Hermes 官方或本地安全 dispatch 接口之前，实现真实发送存在误发和审计
  缺口。

## Consequences

- `scripts/hermes_dispatcher.py` 继续保持 dry-run 占位，不升级为真实发送器。
- `real_send_enabled` 必须继续保持 `false`。
- `real_send_gate.enabled` 必须继续保持 `false`。
- 本项目不保存任何 WeChat token 或 profile 私密配置。
- 真实发送能力后续只能建立在 Hermes 官方或 profile-local 的安全 dispatch 接口之
  上。

## Next Steps

- 继续探查 Hermes Python 包是否存在正式 send/dispatch 函数。
- 评估 Hermes 自身 webhook / cron 机制是否可安全唤醒 profile 读取 outbox。
- 只有在确认本地安全接口、审计边界、权限控制和人工确认策略后，才重新评估真实发
  送方案。
