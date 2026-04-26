# Release Notes

## v2.0-rc Local Dispatch Dry-run

当前状态是 `v2.0-rc local dispatch dry-run`。本阶段新增 Hermes 本机 dispatch
占位接口，并把 dry-run 链路收口为：

```text
Apple Calendar
  -> reminder_worker
  -> message_adapter
  -> outbox_messages.jsonl
  -> outbox_consumer
  -> channel_sender
  -> hermes_dispatcher dry-run
  -> sent_dry_run
```

仍不真实发送微信、Telegram 或任何外部网络消息。

### Phase 25 Safety Gate

- 新增 `real_send_gate`，默认 `enabled=false`。
- 真实发送需要 `real_send_enabled=true`、gate enabled、channel 白名单和确认短语。
- 本阶段即使全部满足仍返回 `real send adapter not implemented`。
- `outbox_consumer --mode real` 不会标记 sent；如有 pending，会标记
  `failed_real_send_blocked` 并记录 reason。
- 新增回滚文档：`docs/rollback.md`。

### Phase 26 Real-send Channel Decision

- 新增方案对比：`docs/real-send-channel-options.md`。
- 新增 ADR：`docs/decision-records/ADR-001-real-send-channel.md`。
- 推荐方案 A：Hermes 本地回调 / 本地 CLI。
- 暂不选择方案 B Telegram Bot API。
- 暂不选择方案 C 微信通道。
- 实现前必须确认 Hermes local dispatch CLI、`sunny-wechat-lite` outbound
  API、profile 内部 tool 和用户二次确认策略。

### Phase 28 WeChat Dispatch Capability Discovery

- 新增 discovery 文档：`docs/wechat-dispatch-discovery.md`。
- 新增 ADR：`docs/decision-records/ADR-002-wechat-dispatch-discovery.md`。
- 已记录只读发现：
  `sunny-wechat-lite` profile 下存在 `weixin/accounts/*.json`；
  account JSON 包含 `base_url`、`user_id`、`token`；
  `channel_directory.json` 中存在 Weixin DM channel。
- 文档明确：不把 token 写入本项目，不读取或复制 profile token。
- 文档明确：不实现直接请求 `ilinkai.weixin.qq.com` 的发送逻辑。
- 文档明确：直接请求 WeChat API 会绕过 Hermes 的权限、审计和统一调度边界。
- 文档明确：尚未确认 Hermes 官方/本地安全 dispatch 接口，因此当前不能实现
  WeChat 真实发送。
- 当前推荐链路继续保持：
  `reminder_worker -> outbox -> outbox_consumer -> dry-run`。
- 下一步建议：
  继续探查 Hermes Python 包中的正式 send/dispatch 函数，或通过 Hermes 自身
  webhook/cron 机制唤醒 profile 读取 outbox。

### Phase 29 Hermes DeliveryRouter Technical Research

- 新增预研文档：`docs/hermes-delivery-router-research.md`。
- 新增 ADR：`docs/decision-records/ADR-003-hermes-delivery-router.md`。
- 已记录 Hermes 内部结构发现：
  `gateway.delivery.DeliveryRouter`、
  `DeliveryTarget.parse("weixin:<chat_id>")`、
  `deliver(content, targets, metadata)`、
  `_deliver_to_platform -> adapter.send(...)`。
- 已记录 gateway runtime 约束：
  `gateway/run.py` 会把 live adapters 注入 `delivery_router.adapters`。
- 文档明确：独立 Skill 脚本当前无法获得 live adapters，因此不能直接调用真实发送。
- 文档明确：本项目不能读取 profile token，不能复制 Weixin adapter 初始化逻辑，
  也不能绕过 Hermes gateway 的权限和审计。
- 当前推荐路线：
  优先让 Hermes gateway/cron 原生调用 `DeliveryRouter` 发送 outbox；
  次选由 Hermes profile 内部 webhook/cron job 读取 outbox 后再调用 gateway
  delivery；
  不推荐 Calendar Skill 直接读取 `weixin/accounts` token 并调用 ilink API。
- 当前 dry-run 链路继续保持：
  `reminder_worker -> outbox -> outbox_consumer -> channel_sender -> hermes_dispatcher dry-run`。
- Phase 30 建议：
  探查 hermes cron 是否支持 delivery targets，并尝试用 hermes cron/webhook
  触发“读取 outbox 并回复到 weixin home channel”。

### Phase 30 Hermes Cron Delivery Validation

- 新增验证文档：`docs/hermes-cron-delivery-test.md`。
- 新增 ADR：`docs/decision-records/ADR-004-hermes-cron-delivery.md`。
- 已记录验证命令模板：
  `sunny-wechat-lite cron create ... --deliver "weixin:<chat_id>"`、
  `sunny-wechat-lite cron tick`、
  `sunny-wechat-lite cron list`。
- 成功判断标准已记录为：微信收到 `Cronjob Response`。
- 本机验证成功结论已记录：
  `Hermes Cron -> DeliveryRouter -> Weixin Adapter -> 微信`。
- 文档明确：Hermes Cron Delivery 可以作为真实微信提醒发送路径。
- 文档明确：Calendar Skill 仍不直接读取 `weixin` token，也不直连
  `ilink` / Weixin API。
- 已记录推荐后续真实发送架构：
  `Calendar Skill -> outbox -> Hermes Cron job -> cron script stdout -> Hermes Cron --deliver -> weixin:<chat_id>`。
- 已记录优先原因：
  token 留在 Hermes profile 内、使用 Hermes 原生 `DeliveryRouter`、支持审计与
  job 管理、不绕过 gateway。
- 已记录风险：
  Cronjob Response 包装、消息频率控制、重复发送、empty outbox。
- Phase 31 建议：
  新增 cron 脚本只输出 pending outbox 文本，并用
  `sunny-wechat-lite cron create --script ... --deliver weixin:<chat_id>`
  验证；先保持 dry-run 消费，再评估是否引入 `sent_via_hermes_cron`。

### Phase 31 Hermes Cron Outbox Bridge

- 新增脚本：`scripts/hermes_cron_outbox_bridge.py`。
- 新增文档：`docs/hermes-cron-outbox-bridge.md`。
- 新增 CLI：
  `python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5`。
- bridge 当前行为：
  只读取 `data/outbox_messages.jsonl` 中 `status=pending` 的记录，
  按 `created_at` 升序输出，最多 `limit` 条。
- 输出为适合 Hermes Cron Delivery 的纯文本，默认使用
  `--empty-mode silent`，无 pending 时 stdout 为空。
- 新增 `--empty-mode silent|message`：
  `silent` 避免无意义通知；
  `message` 输出 `当前没有待发送日历提醒。`，用于手动验证。
- 本阶段明确保持只读：
  不修改 outbox 状态、不删除 outbox、不读取 token、不请求网络、不直连
  WeChat/Telegram。
- 文档已记录 Hermes cron 创建模板：
  `sunny-wechat-lite cron create "every 5m" "请将脚本输出内容原样发送给我；如果为空则不要回复。" --name "calendar-outbox-wechat-bridge" --script "calendar_outbox_bridge.py" --deliver "weixin:<chat_id>"`。
- 风险已记录：
  如果只读不标记，pending 会重复发送，因此正式启用前必须进入 Phase 32。

### Phase 32 Hermes Cron Outbox Bridge Mark-after-output

- 更新 `scripts/hermes_cron_outbox_bridge.py`，新增 `--mark-sent`。
- 当执行
  `python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent`
  时，bridge 会：
  读取 `pending`、输出提醒文本到 stdout、并把这些记录标记为
  `sent_via_hermes_cron`。
- 写入 result：
  `mode=hermes_cron`、`processed_at=<ISO时间>`、
  `note="Message handed to Hermes Cron stdout for delivery"`。
- 幂等规则已明确：
  只处理 `pending`；
  `sent_via_hermes_cron`、`sent_dry_run` 和失败状态当前都不再输出。
- 不传 `--mark-sent` 时，保持 Phase 31 只读行为。
- `scripts/outbox.py list --limit 20` 现在可直接展示
  `sent_via_hermes_cron` 状态，并显示 result.note。
- 文档新增正式启用命令：
  `sunny-wechat-lite cron create "every 5m" "请将脚本输出内容原样发送给我；如果为空则不要回复。" --name "calendar-outbox-wechat-bridge" --script "calendar_outbox_bridge.py" --deliver "weixin:<chat_id>"`。
- 风险已记录：
  bridge 标记发生在 Hermes Cron stdout handoff 后，
  如果后续 Delivery 失败，目前无法自动回滚。

### Phase 33 Hermes Cron Outbox Bridge Enabled

- 当前正式启用链路已记录：
  `Apple Calendar -> reminder_worker launchd -> outbox_messages.jsonl -> Hermes Cron bridge script -> Hermes Cron Delivery -> Weixin Adapter -> 微信`。
- 已记录正式启用命令：
  `sunny-wechat-lite cron create "every 5m" "请将脚本输出内容原样发送给我；如果为空则不要回复。" --name "calendar-outbox-wechat-bridge" --script "calendar_outbox_bridge.py" --deliver "weixin:<chat_id>"`。
- 已补充说明：`cron --script` 使用的是 profile 专属脚本目录
  `~/.hermes/profiles/sunny-wechat-lite/scripts/`，不同 profile 应使用各自 profile
  的 `scripts/` 目录。
- 已修正：wrapper 必须是 Python 脚本
  `~/.hermes/profiles/sunny-wechat-lite/scripts/calendar_outbox_bridge.py`，
  不能使用 `.sh` shell wrapper。
- 已记录为什么需要暂停 `outbox_consumer` dry-run launchd：
  它会把 `pending` 抢先消费为 `sent_dry_run`，导致 Hermes Cron bridge 读不到待发送
  消息。
- 已记录 `sent_via_hermes_cron` 的含义：
  记录已交给 Hermes Cron stdout 进入 Delivery 链路，bridge 不会再次发送。
- 已明确：Calendar Skill 不读取 token，不直连微信，真实发送仍由 Hermes Cron
  Delivery 完成。
- 已记录当前限制：
  Hermes Cron Delivery 失败后无法自动回滚 `sent_via_hermes_cron`；
  微信消息会带 `Cronjob Response` 包装；
  初期建议 `limit=1`、`every 5m`。

### Phase 38 Reminder Follow-up Actions

- 新增 `scripts/reminder_context.py`：
  只读 `data/outbox_messages.jsonl`，读取最近 calendar reminder outbox 记录，
  并提取 `calendar/title/start/end/location/fingerprint/offset_minutes`。
- 新增 `scripts/reminder_action_parser.py`：
  支持 `snooze`、`cancel`、`reschedule`、`arrived`、`disable_reminder`、
  `change_offset`、`unknown`。
- 新增 `scripts/reminder_action_flow.py`：
  `draft --text "<用户原文>"` 生成确认草稿并写入
  `data/pending_confirmations.json`；
  `confirm --session-key <key>` 在确认后执行或记录动作。
- 新增文档：`docs/reminder-action-flow.md`。
- 安全边界：
  draft 阶段不修改 Calendar；
  删除和改期必须 confirm；
  不读取微信 token，不直连微信 API，不请求外部网络；
  不删除 outbox，不修改 outbox message 内容。
- 当前限制：
  `snooze`、`arrived`、`disable_reminder`、`change_offset` 本阶段先记录状态或偏好，
  不直接修改 Calendar 或全局提醒配置。

### Phase 39 Reminder Follow-up WeChat Test Documentation

- 已记录 Hermes 微信交互测试用例：
  `延后30分钟`、`取消这个日程`、`改到明天上午10点`。
- 已明确预期行为：
  微信回复先进入 `reminder_action_flow.py draft --text "<用户原文>"` 生成操作草稿；
  draft 阶段不直接修改 Calendar；
  删除和改期必须等待二次确认后才可执行。
- 已补充排查入口：
  `~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log`、
  `~/.hermes/profiles/sunny-wechat-lite/logs/gateway.error.log`、
  `python3 scripts/outbox.py list --limit 20`。

### Calendar Event Query Bugfix

- 修复提醒实测中发现的 Calendar 事件读取问题：
  `个人计划` 中存在 `再次测试 / 2026-04-26 13:00`，但旧查询路径没有生成提醒。
- 根因包括：
  Calendar AppleScript 时间窗口过滤需要使用 `whose its start date/end date`；
  旧变量名容易与 Calendar AppleScript 术语冲突；
  多行地点或备注会破坏以换行分隔的事件输出；
  stdout `.strip()` 会丢失 tab 分隔输出中的空尾字段。
- `scripts/calendar_ops.py` 已修复：
  使用验证过的时间过滤语法；
  清洗字段中的 tab/换行/return；
  将 `missing value` 归一为空字符串；
  保留 tab 分隔中的空字段。
- 已新增文档：`docs/calendar-event-query-bugfix.md`。

### Phase 40 Reminder Copy And Hermes Behavior Constraints

- `scripts/hermes_cron_outbox_bridge.py` 的提醒正文已优化为更自然的中文个人助理
  文案，适当使用 emoji，并展示时间、事项、地点和可直接回复的操作。
- 多条提醒会汇总为“您有 N 个即将开始的日程”，不输出 JSON、fingerprint 或
  outbox id；地点为空时不显示地点行。
- Hermes 微信后续操作规则已收紧：
  用户回复 `推迟30分钟`、`延后30分钟`、`稍后提醒`、`取消这个日程`、
  `改到明天上午10点`、`已到达`、`不再提醒` 时，必须优先调用
  `reminder_action_flow.py draft --text "<用户原文>"`。
- 如果 draft flow 能找到最近提醒，Hermes 不应先追问“是哪个日程”；只有没有最近
  提醒或返回多个候选时才询问用户选择。
- 明确禁止错误表述：
  本项目操作 Apple Calendar，不操作 Apple Reminders；
  不得回复“已同步至 Apple Reminders”。
- 推荐回复：
  draft 后说“已生成操作草稿，尚未修改日程。”；
  confirm 成功后说“已更新 Apple Calendar 日程。”。

### Phase 41 Apple Calendar Assistant Persona Style

- 新增 `scripts/response_style.py`，集中管理用户可见中文文案。
- 新增文档：`docs/persona-style.md`。
- 创建日程成功、修改日程成功、删除日程成功、日程提醒推送、冲突提醒、待确认草稿、
  迟到/出发提醒统一采用“高先生的私人行政助理”语气。
- 风格要求：
  温柔、自然、熟悉感、轻松、高效、贴心、稍微活泼；
  emoji 每次 0 到 2 个；
  禁止低幼撒娇、过度暧昧、网络土味、夸张表情包风和长篇废话。
- 输出层已尽量接入相关脚本，同时保留 JSON structured data 兼容 CLI 和 Hermes
  自动化。

### Phase 42 Dedicated Assistant Persona System

- 新增 `scripts/assistant_persona.py`，提供正式统一文案函数：
  `format_calendar_created`、`format_calendar_updated`、`format_calendar_deleted`、
  `format_calendar_draft`、`format_calendar_conflict`、`format_reminder_message`、
  `format_multi_reminder_message`、`format_reminder_action_draft`、
  `format_reminder_action_confirmed`、`format_no_pending_reminders`、
  `format_error_friendly`。
- 新增 `docs/persona-examples.md`，更新 `docs/persona-style.md`。
- `scripts/hermes_cron_outbox_bridge.py` stdout 改为使用 persona 格式。
- `scripts/message_adapter.py` 使用 persona 函数生成 reminder message。
- `scripts/reminder_action_flow.py` 的 draft/confirm 输出增加 `data.display_message`。
- `scripts/interactive_create.py` 的 create-draft/confirm 输出增加 `data.display_message`。
- Skill 规则新增：
  回复用户时优先使用 `display_message`；
  如果脚本返回 `display_message`，Hermes 应直接采用或轻微整理，不改变事实；
  创建/修改/删除成功只能基于脚本 `ok=true`；
  禁止编造 Apple Reminders 同步结果。

### Phase 43 Hotel Order Recognition And Calendar Drafts

- 新增 `scripts/hotel_order_parser.py`：
  规则解析酒店订单文字，识别酒店名称、地址、入住/离店日期、入住/离店时间、入住
  人、房型、订单号/确认号、平台来源和置信度。
- 新增 `scripts/hotel_order_flow.py`：
  `draft` 生成酒店行程待确认草稿；
  `update-draft` 补充 `calendar` / `checkin-time`；
  `confirm` 在信息完整并确认后写入 Apple Calendar；
  `cancel` 取消 pending 草稿。
- 新增文档：`docs/hotel-order-flow.md`。
- 安全边界：
  不直接写日历；
  只允许用户选择 `个人计划` / `夫妻计划`；
  必须确认具体入住时间；
  不写 `飞行计划`、不创建提醒事项、不操作 Apple Reminders、不请求外部网络、不实现 OCR。
- 截图场景：
  如果 Hermes 已提取 OCR 文本，则把文字传给 hotel order flow；
  如果没有文字内容，应请用户提供订单文字或先进行截图文字读取。

## v2.0-beta Dry-run Accepted

当前状态是 `v2.0-beta dry-run accepted`。v2.0-beta 在提醒候选扫描基础上，补齐了本地 outbound message、outbox 队列、
dry-run consumer、安全开关，以及 Hermes 本地读取接口。当前仍是 dry-run 阶段，
不会真实发送微信、Telegram 或任何外部网络请求。

### 当前状态

- 已有本地提醒队列：`data/outbox_messages.jsonl`
- 已有 outbound message 适配：`scripts/message_adapter.py`
- 已有 dry-run outbox 写入：`reminder_worker.py --write-outbox`
- 已有 dry-run consumer：`scripts/outbox_consumer.py`
- 已有 Hermes 本地读取接口：`scripts/hermes_outbox_cli.py`
- 已记录并验收 launchd dry-run 链路：
  `flight_auto_enhancer`、`reminder_worker`、`outbox_consumer`
- 已有真实发送前通道适配抽象：`scripts/channel_sender.py`
- 已有 Hermes 真实发送保留配置：
  `real_send_enabled=false`、`send_modes_supported=["dry_run"]`、
  `hermes_channel.enabled=false`
- 暂不真实发送微信、Telegram 或外部网络消息

### 已验收 dry-run 链路

```text
Apple Calendar
  -> reminder_worker
  -> message_adapter
  -> outbox_messages.jsonl
  -> channel_sender dry-run
  -> outbox_consumer dry-run
  -> sent_dry_run
```

如果 `outbox_consumer` 已由 launchd 自动消费，Hermes 查询 pending outbox 时可能
返回空列表；这表示 pending 已被本地 dry-run consumer 消费，不代表真实发送。

### Hermes 本地接口

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
python3 scripts/hermes_outbox_cli.py status --id "<record_id>"
python3 scripts/hermes_outbox_cli.py mark-dry-run-sent --id "<record_id>"
```

### 安全边界

- outbox 当前只是本地 dry-run 队列。
- Hermes 不得删除 outbox 记录。
- Hermes 不得修改 message 内容。
- Hermes 不得调用外部网络发送接口。
- `sent_dry_run` 只表示本地 dry-run 消费完成，不代表真实发送。
- `channel_sender.py` 当前只支持 `mode=dry_run` 和 `channel=hermes`。
- `real` 发送分支已预留但强制返回 `real send is not implemented`。

### 下一步建议

- 接入 Hermes profile 的 tool/skill 配置。
- 让 Hermes 对话按 `SKILL.md` 调用 `hermes_outbox_cli.py`。
- 继续保持真实 sender 独立，等安全开关和确认流程稳定后再接入。

## v2.0-alpha

v2.0-alpha 在 v1.0 的 Apple Calendar CRUD、确认式写入和飞行计划 location
增强基础上，补充了自然语言草稿解析、冲突检测和提醒候选扫描能力。

### 功能摘要

- 共享工具层：`scripts/util.py` 和 `scripts/settings.py`
- 自然语言日程草稿解析：`scripts/nlp_event_parser.py`
- 单日历冲突检测：`scripts/conflict_checker.py`
- 创建草稿时可附带冲突检测：`interactive_create.py create-draft --check-conflict`
- 提醒候选扫描 Worker：`scripts/reminder_worker.py`
- reminder worker launchd 模板
- 飞行计划自动增强继续由 launchd 后台任务负责

### 新增命令

```bash
python3 scripts/nlp_event_parser.py parse "明天下午三点和王总开会"
python3 scripts/conflict_checker.py check --calendar "商务计划" --start "2026-04-27T15:00:00" --end "2026-04-27T16:00:00"
python3 scripts/interactive_create.py create-draft --session-key "wechat_user_001" --calendar "商务计划" --title "客户会议" --start "2026-04-27T15:00:00" --end "2026-04-27T16:00:00" --check-conflict
python3 scripts/reminder_worker.py scan
```

### 安全边界

- 普通 create/update/delete 仍必须确认。
- 删除仍需要二次确认。
- `飞行计划` 不允许普通 CRUD 写入。
- 飞行计划自动增强只允许写原事件 `location` 字段。
- reminder worker 只读 Calendar.app，不修改、不删除、不创建事件。
- 当前阶段不发送微信、Telegram、系统通知或 Calendar alarm。
- 不引入第三方依赖，不接外部网络。

### 已知限制

- 自然语言解析仍是规则解析，覆盖有限。
- 冲突检测当前只支持单日历。
- 建议时间段只做基础空闲窗口计算。
- reminder worker 只输出提醒候选 JSON，不主动投递消息。
- update/delete 仍依赖较基础的事件匹配能力。

### v2.0-beta 建议

- Hermes 主动提醒发送。
- 更精准的中文时间解析。
- 候选事件选择式修改/删除。
- 多日历联合冲突检测。
- 周报/月报总结。
