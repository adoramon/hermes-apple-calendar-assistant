# Reminder Action Flow

当前状态：`v2.0-rc reminder action draft/confirm`。

本流程用于处理用户收到微信日历提醒后的后续回复，例如延后、取消、改时间、已到达
或不再提醒。Calendar Skill 不读取微信 token，不直连微信 API；真实提醒投递仍由
Hermes Cron Delivery 完成。

Phase 39 已将 reminder action draft flow 接入 Hermes 微信交互测试。用户在微信
收到日历提醒后，可以直接回复后续操作文本；Hermes 应先生成操作草稿并展示给用户，
不得在 draft 阶段直接修改 Calendar。

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

## 微信交互测试用例

在收到最近一条日历提醒后，使用以下微信回复进行测试：

- `延后30分钟`
- `取消这个日程`
- `改到明天上午10点`

预期行为：

- Hermes 调用 `reminder_action_flow.py draft --text "<用户原文>"`。
- 系统先生成操作草稿，并返回目标日程、动作类型和拟变更内容。
- draft 阶段不直接修改 Calendar。
- `取消这个日程` 和 `改到明天上午10点` 必须等待用户二次确认后才能执行。

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

## 失败排查

如果微信回复没有生成草稿，按以下顺序排查：

- 查看 Hermes gateway 日志：`tail -n 100 ~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log`
- 查看 Hermes gateway 错误日志：`tail -n 100 ~/.hermes/profiles/sunny-wechat-lite/logs/gateway.error.log`
- 查看最近 outbox 记录：`python3 scripts/outbox.py list --limit 20`
