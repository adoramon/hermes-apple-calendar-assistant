# Rollback

本文说明如何回滚 reminder/outbox dry-run 链路，同时保留飞行计划自动增强。

## 卸载 reminder_worker launchd

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

## 卸载 outbox_consumer launchd

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

## 保留 flight_auto_enhancer

建议保留：

```bash
~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
```

它只服务 `飞行计划` location 自动增强，和 reminder/outbox dry-run 链路相互独立。

## 回滚 Skill 软链接

如果 `sunny-wechat-lite` profile 使用软链接接入本仓库的 `SKILL.md`，可删除软链接：

```bash
rm "<sunny-wechat-lite-profile-skills-dir>/apple-calendar-assistant.SKILL.md"
```

请将 `<sunny-wechat-lite-profile-skills-dir>` 替换为实际 profile skills 目录。

## 恢复旧 Skill 备份

如果接入前备份过旧 skill：

```bash
cp "<backup-dir>/apple-calendar-assistant.SKILL.md" \
  "<sunny-wechat-lite-profile-skills-dir>/apple-calendar-assistant.SKILL.md"
```

恢复后重启或刷新 Hermes profile，使旧 skill 生效。

## 检查日志

```bash
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.err.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/outbox_consumer.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/outbox_consumer.err.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/flight_auto_enhancer.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/flight_auto_enhancer.err.log
```

## 验证回滚

```bash
launchctl list | grep com.adoramon.hermes-apple-calendar
```

期望只保留 flight auto enhancer，或明确知道哪些任务仍处于加载状态。
