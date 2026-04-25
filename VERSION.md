# Apple Calendar Assistant

Current version: `v2.0-rc local dispatch dry-run`

## v2.0.0-beta

当前状态：`v2.0-rc local dispatch dry-run`

变更记录：

- outbound reminder message adapter
- dry-run outbox queue: `data/outbox_messages.jsonl`
- dry-run outbox consumer
- outbox consumer launchd template
- Phase 13 安全开关与配置收口：
  `outbox.send_mode=dry_run`、`allowed_channels`、`max_messages_per_run`
- Phase 14 Hermes 本地消费接口：
  `pending`、`status`、`mark-dry-run-sent`
- Phase 15 Hermes Skill 调用规则收口：
  提醒查询、状态查看、dry-run 已处理标记和 outbox 风险边界
- Phase 19 v2.0-beta dry-run 全链路验收文档收口：
  launchd 状态、验收命令、dry-run 链路和回滚方法
- Phase 20 v2.0-rc 真实发送前通道适配设计：
  `channel_sender.py`，当前仅支持 `dry_run` + `hermes`
- Phase 21 v2.0-rc Hermes 通道真实发送方案设计：
  `real_send_enabled=false`、`send_modes_supported=["dry_run"]`、
  `hermes_channel` 保留配置
- Phase 22-24 v2.0-rc 本机 Hermes 调度闭环准备：
  `hermes_dispatcher.py`、`channel_sender -> hermes_dispatcher` dry-run、
  本机闭环验收文档
- 当前阶段仍不真实发送 Telegram、微信或任何外部网络请求

## v2.0.0-alpha

变更记录：

- shared settings/util helpers
- natural language event parser
- conflict checker
- conflict-aware draft creation
- reminder scan worker
- reminder launchd template
- 保留所有写操作确认要求
- 保留 `飞行计划` 普通 CRUD 禁写边界

## v1.0.0

Release scope:

- Query events
- Create with confirmation
- Update
- Delete with second confirmation
- Flight location enhancement
