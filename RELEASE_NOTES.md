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
