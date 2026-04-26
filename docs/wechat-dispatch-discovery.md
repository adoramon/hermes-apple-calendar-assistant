# WeChat Dispatch Capability Discovery

当前状态：`v2.0-rc local dispatch dry-run`。

本文档记录 Phase 28 对 Hermes WeChat dispatch capability 的已知发现、当前边界
和后续探查建议。本文档只记录事实和安全决策，不实现真实发送。

## 已确认事实

- `sunny-wechat-lite` profile 下存在 `weixin/accounts/*.json`。
- account JSON 包含 `base_url`、`user_id`、`token` 字段。
- `channel_directory.json` 中存在 Weixin DM channel：
  `o9cq80yt8Tq__PY5jHlu0g0Q_xn0@im.wechat`

以上发现仅说明 Hermes profile 内部存在 WeChat 账号和 channel 配置线索；不代表
本项目已经获得可安全调用的发送能力。

## 当前未确认事项

- 尚未确认 Hermes 是否提供正式、本地、安全的 dispatch/send CLI。
- 尚未确认 Hermes Python 包是否暴露正式 send/dispatch 函数。
- 尚未确认 `sunny-wechat-lite` profile 是否存在可供 skill 安全调用的本地 outbound
  handler、tool 或 webhook。

## 当前结论

当前不能在本项目中实现 WeChat 真实发送。

## 原因

- `token` 属于 Hermes profile 私密配置，不属于本项目配置。
- 本 Skill 不应读取、复制、缓存或写入 Hermes profile 的 `token`。
- 直接请求 WeChat / `ilinkai.weixin.qq.com` API 会绕过 Hermes 的权限、审计和统一
  调度边界。
- Hermes 官方或本地安全 dispatch 接口尚未确认，当前没有足够依据实现真实发送。

## 明确禁止事项

- 不把任何 `token` 写入本项目。
- 不在本项目实现直接请求 `ilinkai.weixin.qq.com` 的发送逻辑。
- 不在本项目中补充微信真实发送代码。
- 不请求外部网络。

## 当前推荐链路

继续保持：

```text
reminder_worker
  -> outbox
  -> outbox_consumer
  -> dry-run
```

这条链路的职责仍然是本地生成提醒、记录 outbox、完成 dry-run 消费，不承担真实发
送。

## 建议下一步

- 继续探查 Hermes Python 包中是否存在正式 send/dispatch 函数。
- 或通过 Hermes 自身 webhook / cron 机制唤醒 profile 读取 outbox。
- 在 Hermes 官方或本地安全 dispatch 接口确认前，保持
  `real_send_enabled=false`、`real_send_gate.enabled=false`。
- 在能力未确认前，不修改 `scripts/`、`config/`、`data/`、`launchd`。
