# Reminder Action Flow

当前状态：`v2.0-rc reminder action draft/confirm`。

本流程用于处理用户收到微信日历提醒后的后续回复，例如延后、取消、改时间、已到达
或不再提醒。Calendar Skill 不读取微信 token，不直连微信 API；真实提醒投递仍由
Hermes Cron Delivery 完成。

## 支持的回复

- `延后30分钟` / `推迟30分钟` / `稍后提醒`
- `延后1小时`
- `取消` / `取消这个日程`
- `改到明天上午10点` / `改到下午3点`
- `已到达`
- `不再提醒`
- `提前30分钟提醒我`

## 解析

```bash
python3 scripts/reminder_action_parser.py parse "延后30分钟"
```

解析结果包含：

- `intent`
- `minutes`
- `target_time`
- `needs_confirmation`

## 生成草稿

```bash
python3 scripts/reminder_action_flow.py draft --text "延后30分钟"
```

draft 阶段会读取最近一条 calendar reminder outbox 记录，并把操作草稿写入
`data/pending_confirmations.json`。draft 阶段绝不修改 Calendar。

如果最近提醒上下文不明确，脚本会返回候选记录，Hermes 应询问用户选择。

## 确认执行

```bash
python3 scripts/reminder_action_flow.py confirm --session-key "<session_key>"
```

确认后行为：

- `cancel`：删除目标 Calendar 事件。
- `reschedule`：更新目标 Calendar 事件时间。
- `snooze`：本阶段只记录状态，不修改 Calendar 时间。
- `arrived`：只记录状态，不修改 Calendar。
- `disable_reminder`：只记录状态，不修改 Calendar。
- `change_offset`：当前只记录 pending preference，不修改全局配置。

## 安全边界

- draft 阶段绝不修改 Calendar。
- 删除和改期必须经过 confirm。
- 不读取微信 token。
- 不调用微信 API。
- 不请求外部网络。
- 不删除 outbox 记录。
- 不修改 outbox message 内容。
- 不引入第三方依赖。
