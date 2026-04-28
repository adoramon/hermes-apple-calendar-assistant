# Apple Calendar Assistant

Current version: `v2.0-rc wechat voice attachment sealed`

## v2.0.0-beta

当前状态：`v2.0-rc wechat voice attachment sealed`

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
- Phase 44 补充：sunny-wechat-lite Skill 自主创建治理：
  明确微信侧日历、酒店订单、提醒和航班上下文不得触发 Hermes 自主创建或替换
  日历相关 Skill；自动保存/创建 Skill 提示应回复 `Nothing to save.`，除非高先生
  当前对话明确要求
- Phase 45 Pro 商务出行自动秘书系统：
  新增 `travel_order_parser.py`、`trip_aggregator.py`、`trip_flow.py`，
  支持机票/酒店/高铁订单聚合为一次 Trip，确认日历后一次性写入 Apple Calendar，
  并通过 `trip_seen.json` 做事件 fingerprint 去重
- Phase 46 微信端 Trip 聚合实测收口：
  补充连续发送机票/酒店/高铁订单截图的标准微信链路、日志关键字
  `travel_order_parser.py parse`、`trip_aggregator.py add`、
  `trip_flow.py draft`、`trip_flow.py set-calendar`、`trip_flow.py confirm`，
  并文档化成功判断标准、失败排查、测试话术与 `trip_drafts.json` /
  `trip_seen.json` 清理方法
- Phase 47 老板一句话出差模式：
  新增 `travel_intent_parser.py`、`trip_planner.py` 和
  `docs/travel-intent-planner.md`，支持直接从自然语言出差/旅行意图生成
  Trip planning draft，经用户确认后写入 Apple Calendar；仅生成本地计划草稿，
  不订票、不查价格、不查实时航班、不请求外部网络
- Phase 48 一句话出差模式微信端实测收口：
  新增 `docs/travel-intent-wechat-validation.md`，补充标准测试话术、
  `travel_intent_parser.py parse`、`trip_planner.py draft`、
  `trip_planner.py set-field`、`trip_planner.py confirm` 日志关键字、
  三轮微信确认流程、成功判断标准、失败排查和测试数据清理方法
- Phase 49 计划 Trip 与飞行计划/酒店/高铁自动合并：
  新增 `flight_plan_reader.py`、`trip_flight_matcher.py` 和
  `docs/trip-flight-plan-merge.md`，从 Apple Calendar `飞行计划` 只读关联航班，
  机票截图只作为匹配线索，不创建航班日程；`trip_flow.py confirm` 只写酒店、
  高铁、客户拜访等非航班事件
- Phase 50 真实订单替换 Trip 计划占位：
  增强 `trip_aggregator.py add --trip-id <id>`，真实酒店订单替换
  `hotel_placeholder`，真实高铁订单替换去程/返程 placeholder；
  日期不一致时标记 `date_conflict` 并等待用户确认；新增
  `docs/trip-plan-order-merge.md`，并为 `flight_plan_reader.py` 增加
  `diagnose --days 30` 诊断输出
- Phase 51 微信端多 Trip 候选选择与合并实测收口：
  新增 `docs/trip-merge-wechat-validation.md`，固化多个 Trip 候选时的微信端流程：
  先列出候选并让用户选择，再使用 `trip_aggregator.py add --trip-id <id>` 合并；
  记录酒店/高铁替换 placeholder、日期冲突追问、航班只关联 `飞行计划` 的验收标准
- Phase 52 出差行程摘要日报 / 行前提醒：
  新增 `trip_briefing_worker.py`、`data/trip_briefing_seen.json` 和
  `docs/trip-briefing-worker.md`，扫描未来 24-48 小时内的 Trip，生成行前摘要并写入
  Hermes outbox；只写 outbox，不修改 Calendar、不直连微信
- Phase 53 Trip Briefing 定时推送接入：
  新增 `deploy/launchd/com.adoramon.hermes-apple-calendar-trip-briefing-worker.plist`，
  提供每 30 分钟运行 `trip_briefing_worker.py scan --hours 48` 的用户级 launchd
  模板；不自动安装，只记录安装、卸载、日志和完整 outbox 推送链路
- Phase 54 微信端一句话查询行程：
  新增 `schedule_query_router.py` 和 `docs/wechat-schedule-query.md`，支持“今天/明天
  什么安排”“下周上海出差怎么样”“这个月还有哪些出差”等自然语言查询；
  只读调用 Calendar 和 Trip 查询能力，输出秘书式摘要
- Phase 55 微信语音秘书模式：
  新增 `docs/wechat-voice-secretary.md`，记录微信语音 -> Hermes ASR 转写 ->
  Calendar / Trip / reminder 路由 -> 文字 + 可选 TTS 回复的标准链路；
  复用 Hermes 原生 voice pipeline，不读取微信 token、不改现有 profile 配置；
  新增 `voice_mode=off|smart|always` 行为约定和 persona 语音回复文案函数
- Phase 56 微信语音秘书实测收口：
  新增 `docs/wechat-voice-validation.md`，固化语音测试流程、`voice` / `ASR` /
  `TTS` / `schedule_query_router.py` / `reminder_action_flow.py` / `trip_flow.py`
  日志关键字、`voice_mode` 验收、失败排查和安全边界
- WeChat voice attachment sealed：
  当前 Weixin iLink bot 出站原生 voice 气泡会被客户端静默丢弃，因此封板为
  “默认文字回复；用户明确要求语音时发送可见音频附件”。附件不带
  `voice message as attachment` 英文提示，文件名使用中文；`开车模式` /
  `安静模式` / `只文字回复` 不追加语音附件
- 删除日程误报修复：
  新增 `delete_event_flow.py` 和 `docs/delete-event-flow.md`，删除请求先查询候选并生成
  二次确认草稿，确认后按 `calendar + title + start + end` 精确身份删除，避免
  “删除游泳计划”这类标题别名导致未删除却回复成功
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
