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
- Phase 25 v2.0-rc 真实发送前最终闸门与回滚策略：
  `real_send_gate`、blocked real mode、outbox audit/result、rollback docs
- Phase 26 v2.0-rc 真实发送通道方案设计：
  推荐 Hermes 本地回调 / 本地 CLI，暂不选择 Telegram Bot API 或微信自动化
- Phase 28 v2.0-rc Hermes WeChat dispatch capability discovery 文档化：
  记录 profile 内存在 WeChat account/channel 线索，但当前仍禁止读取 token、
  禁止直连 `ilinkai.weixin.qq.com`、禁止实现真实发送
- Phase 29 v2.0-rc Hermes DeliveryRouter 真实发送技术预研：
  记录 `gateway.delivery.DeliveryRouter` 结构，确认独立 Skill 无法获得 live
  adapters，因此当前不能直接调用真实发送
- Phase 30 v2.0-rc Hermes Cron Delivery 真实投递路径验证：
  已验证 `Hermes Cron -> DeliveryRouter -> Weixin Adapter -> 微信` 链路可用，
  但 Calendar Skill 仍不直接读取 token、不直连微信 API
- Phase 31 v2.0-rc Hermes Cron Outbox Bridge：
  新增只读 bridge 脚本供 `cron --script` 读取 pending outbox 并输出纯文本，
  当前不标记 sent，不应长期启用
- Phase 32 v2.0-rc Hermes Cron Outbox Bridge 发送后标记：
  新增 `--mark-sent`，bridge 输出后可将记录标记为
  `sent_via_hermes_cron`，避免重复发送
- Phase 33 v2.0-rc Hermes Cron Outbox Bridge 正式启用：
  reminder_worker launchd + Hermes Cron bridge + Hermes Cron Delivery 已作为
  当前真实微信提醒链路启用，`outbox_consumer` dry-run launchd 已暂停避免抢占
- Phase 34 v2.0-rc Hermes Cron Bridge 脚本类型修正：
  `cron --script` 应使用 profile/scripts 下的 Python wrapper
  `calendar_outbox_bridge.py`，不能使用 `.sh` shell wrapper
- Phase 38 v2.0-rc 微信提醒交互式日程秘书：
  新增提醒后续操作解析、最近提醒上下文读取、确认式操作草稿与确认执行流程
- Phase 39 v2.0-rc 微信提醒后续操作实测文档收口：
  记录 Hermes 微信交互测试用例 `延后30分钟`、`取消这个日程`、
  `改到明天上午10点`；明确先生成草稿，删除/改期必须二次确认
- v2.0-rc Calendar event query bugfix：
  修复 `calendar_ops.py events` 对 Calendar AppleScript 时间过滤、多行地点/备注、
  空字段解析的兼容问题，避免日历中存在的事件被提醒扫描漏掉
- Phase 40 v2.0-rc 提醒文案优化与 Hermes 行为约束修正：
  Hermes Cron bridge 输出个人助理式中文提醒；微信后续回复优先进入 draft；
  明确项目操作 Apple Calendar，禁止误称同步到 Apple Reminders
- Phase 41 v2.0-rc Apple Calendar Assistant 人格语气升级：
  新增 `scripts/response_style.py` 统一用户可见文案，创建/修改/删除/提醒/冲突/
  待确认草稿采用“高先生的私人行政助理”语气，并保留 JSON 结构化输出
- Phase 42 v2.0-rc 高先生专属 AI 女助理人格系统：
  新增 `scripts/assistant_persona.py` 正式统一人格文案函数，CLI 保留核心 JSON
  字段并增加 `data.display_message`；Hermes 回复优先采用 display_message
- Phase 43 v2.0-rc 酒店订单识别与行程写入：
  新增酒店订单规则解析和确认式草稿流程，仅允许写入 `个人计划` / `夫妻计划`，
  必须确认入住时间，确认后才写入 Apple Calendar
- Phase 43 补充：酒店订单截图自动识别入口：
  Hermes / 多模态模型先提取截图文字，疑似酒店订单时自动进入
  `hotel_order_flow.py draft`，不要求用户额外说明“这是酒店订单”
- Phase 44 v2.0-rc 酒店订单截图微信实测文档收口：
  记录微信截图实测验收链路：截图文字提取后必须进入
  `hotel_order_flow.py draft`，缺少字段时继续追问 `个人计划` / `夫妻计划`
  和入住时间，用户确认后才调用 `hotel_order_flow.py confirm` 写入 Apple
  Calendar；日志关键字为 `draft`、`update-draft`、`confirm`
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
