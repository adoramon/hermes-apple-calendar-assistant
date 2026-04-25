# Apple Calendar Assistant

Current version: `v2.0-beta`

## v2.0.0-beta

变更记录：

- outbound reminder message adapter
- dry-run outbox queue: `data/outbox_messages.jsonl`
- dry-run outbox consumer
- outbox consumer launchd template
- Phase 13 安全开关与配置收口：
  `outbox.send_mode=dry_run`、`allowed_channels`、`max_messages_per_run`
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
