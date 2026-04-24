# Release Notes

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
