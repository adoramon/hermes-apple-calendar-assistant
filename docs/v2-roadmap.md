# v2 Roadmap

本文档记录 v2.0-alpha 已完成内容和后续 v2.0-beta 建议方向。项目边界仍保持在
Apple Calendar 工作流内。

## 已完成 v2.0-alpha 阶段

已完成：

- shared settings/util helpers
- 自然语言日程草稿解析：`scripts/nlp_event_parser.py`
- 确认优先的创建流程：`scripts/interactive_create.py`
- 创建草稿默认可接入冲突检测：`--check-conflict`
- 单日历冲突检测：`scripts/conflict_checker.py`
- 提醒候选扫描：`scripts/reminder_worker.py scan`
- 提醒幂等标识：`data/reminder_seen.json`
- reminder worker launchd 模板
- 飞行计划 location 自动增强 launchd 模板

安全边界：

- All normal writes still require confirmation
- `飞行计划` is not writable through normal create, update, or delete
- Flight location enhancement only writes the original event `location`
- Reminder worker does not send WeChat, Telegram, network calls, system
  notifications, or Calendar alarms
- Hermes conversations do not perform continuous monitoring

## v2.0-beta 建议方向

建议方向：

- Hermes 主动提醒发送
- 更精准的中文时间解析
- 候选事件选择式修改/删除
- 多日历联合冲突检测
- 周报/月报总结

仍然不在当前阶段范围：

- Contacts integration
- Birthday and lunar birthday workflows
- Travel Time automation
- Extra flight preparation events
- Native Swift helper work
