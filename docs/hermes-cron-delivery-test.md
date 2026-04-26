# Hermes Cron Delivery Test

当前状态：`v2.0-rc local dispatch dry-run`。

本文档记录 Phase 30 对 Hermes Cron Delivery 真实投递路径的本机验证结果。本文档
只记录验证结论、架构判断和风险，不在本项目中实现真实发送。

## 验证命令模板

```bash
sunny-wechat-lite cron create "1m" "请只回复：Hermes cron delivery test" \
  --name "wechat-delivery-test" \
  --deliver "weixin:<chat_id>"

sunny-wechat-lite cron tick
sunny-wechat-lite cron list
```

## 成功判断标准

微信收到 Cronjob Response，即可判定投递链路打通。

成功收到内容示例：

```text
Cronjob Response: wechat-delivery-test
(job_id: 723c7e7db86f)
-------------

Hermes cron delivery test
```

## 本机验证结论

本机验证成功，说明以下链路已经打通：

```text
Hermes Cron
  -> DeliveryRouter
  -> Weixin Adapter
  -> 微信
```

这意味着 Hermes Cron Delivery 可以作为真实微信提醒发送路径。

## 当前边界

- Calendar Skill 仍不直接读取 `weixin` token。
- Calendar Skill 仍不直连 `ilink` / Weixin API。
- 真实发送能力仍应继续留在 Hermes profile / gateway runtime 内。
- 本项目当前实现仍保持 dry-run，不在本阶段升级为真实发送。

## 推荐后续真实发送架构

推荐架构：

```text
Calendar Skill
  -> outbox
  -> Hermes Cron job
  -> cron script 读取 outbox
  -> script stdout 作为内容
  -> Hermes Cron --deliver
  -> weixin:<chat_id>
```

在该架构下，Calendar Skill 只负责生成 outbox；Hermes Cron 负责在 Hermes runtime
内触发脚本、接收 stdout，并通过 `--deliver` 走 DeliveryRouter 完成真实投递。

## 为什么优先走 Hermes Cron Delivery

- token 留在 Hermes profile 内，不进入本项目。
- 使用 Hermes 原生 `DeliveryRouter`。
- 支持 Hermes 自身的审计与 job 管理。
- 不绕过 gateway。

## 风险与约束

- Hermes cron 输出会带 `Cronjob Response` 包装。
- 需要控制消息频率，避免过于密集的提醒。
- 需要避免重复发送。
- 需要处理 empty outbox，避免发送空消息或无意义消息。

## Phase 31 建议

- 新增一个 cron 脚本，只输出 pending outbox 消息文本。
- 用 `sunny-wechat-lite cron create --script` 该脚本，并配合
  `--deliver weixin:<chat_id>`。
- 先保持 dry-run 消费逻辑，再评估是否引入真实状态标记
  `sent_via_hermes_cron`。
