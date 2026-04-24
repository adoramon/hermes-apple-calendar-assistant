# Reminder Worker

`scripts/reminder_worker.py` scans upcoming Calendar.app events and emits JSON
reminder candidates. It does not send WeChat, Telegram, system notifications, or
Calendar alarms.

## Behavior

- Reads `read_calendars`, `reminder_scan_minutes`, and
  `reminder_default_offsets_minutes` from `config/settings.json`
- Scans future events within `reminder_scan_minutes`
- Emits a reminder candidate when the current time is inside an offset window
- Uses `data/reminder_seen.json` so the same event and same offset are emitted
  only once
- Only reads Calendar.app
- Does not modify, create, or delete events
- Does not access external networks

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
