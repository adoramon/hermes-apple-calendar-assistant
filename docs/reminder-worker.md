# Reminder Worker

事件读取依赖 `scripts/calendar_ops.py events`。提醒实测中曾发现一个 Calendar 查询
Bug：Calendar.app 中存在 `个人计划 / 再次测试 / 2026-04-26 13:00`，但因
AppleScript 时间过滤、多行地点和空字段解析问题，旧查询路径没有把该事件交给
`reminder_worker.py`。修复记录见
[`docs/calendar-event-query-bugfix.md`](calendar-event-query-bugfix.md)。

`scripts/reminder_worker.py` scans upcoming Calendar.app events and emits JSON
reminder candidates. It does not send WeChat, Telegram, system notifications, or
Calendar alarms.

## 功能说明

- Reads `read_calendars`, `reminder_scan_minutes`, and
  `reminder_default_offsets_minutes` from `config/settings.json`
- Scans future events within `reminder_scan_minutes`
- Emits a reminder candidate when the current time is inside an offset window
- Uses `data/reminder_seen.json` so the same event and same offset are emitted
  only once
- Only reads Calendar.app
- Does not modify, create, or delete events
- Does not access external networks
- 当前阶段不负责主动发送消息，不发送微信、Telegram、系统通知或 Calendar alarm

## 手动运行

```bash
cd /Users/administrator/Code/hermes-apple-calendar-assistant
python3 scripts/reminder_worker.py scan
```

Output shape:

```json
{
  "ok": true,
  "data": {
    "reminders": [
      {
        "fingerprint": "abc123:15",
        "calendar": "商务计划",
        "title": "客户会议",
        "start": "2026年4月27日 星期一 15:00:00",
        "offset_minutes": 15,
        "message": "15分钟后：客户会议"
      }
    ],
    "skipped": []
  },
  "error": null
}
```

## 安装 launchd

先确保日志目录存在：

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
```

复制模板并加载：

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-reminder-worker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

模板每 1 分钟运行一次，并在加载时立即执行一次。

检查任务状态：

```bash
launchctl list com.adoramon.hermes-apple-calendar-reminder-worker
```

## 卸载 launchd

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
rm -f ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

## 查看日志

```bash
tail -f /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.out.log
tail -f /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.err.log
```

## 手动触发一次

安装 launchd 后，可以立即触发一次，不需要等待下一分钟：

```bash
launchctl kickstart -k "gui/$(id -u)/com.adoramon.hermes-apple-calendar-reminder-worker"
```

## 查看 `reminder_seen.json`

View idempotency records:

```bash
python3 -m json.tool data/reminder_seen.json
```

## 重置提醒记录

重置全部提醒记录：

```bash
printf '{\n  "reminders": {}\n}\n' > data/reminder_seen.json
```

重置单条提醒记录：

打开 `data/reminder_seen.json`，删除对应的
`reminders.<fingerprint>:<offset>` 条目。删除后，下次扫描会重新判断该事件和
offset 是否需要提醒。

## Verification

```bash
python3 scripts/reminder_worker.py scan
python3 -m py_compile scripts/*.py
python3 -m json.tool data/reminder_seen.json
```
