# Flight Auto Enhancer

`scripts/flight_auto_enhancer.py` 只做一件事：扫描未来一段时间内的 `飞行计划`
日程，自动把可解析出的出发机场/航站楼写回原事件的 `location` 字段，并在
`data/flight_seen.json` 中记录处理结果，避免重复增强同一条日程。

## 功能说明

- 每次运行读取 `config/settings.json`
- 只扫描 `flight_calendar`，并强制要求它是 `飞行计划`
- 只扫描未来 `flight_scan_days` 天
- 用 `calendar + title + start + end` 生成稳定 `event_fingerprint`
- 已经 `enhanced`、`skipped_has_location`、`skipped_no_parse` 的记录不会重复处理
- `failed` 会在后续运行时再次尝试
- 只允许写原事件的 `location`
- 不修改标题、开始时间、结束时间、备注
- 不创建或删除任何日程

## 手动运行

```bash
cd /Users/administrator/Code/hermes-apple-calendar-assistant
python3 scripts/flight_auto_enhancer.py run
```

输出统一为 JSON：

```json
{"ok": true, "data": {...}}
```

或

```json
{"ok": false, "error": "..."}
```

## 安装 launchd

先确保日志目录存在：

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
```

复制模板并加载：

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
```

模板每 5 分钟运行一次，并在加载时立即执行一次。

检查任务状态：

```bash
launchctl list com.adoramon.hermes-apple-calendar-flight-auto-enhancer
```

## 卸载 launchd

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
rm -f ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
```

## 查看日志

```bash
tail -f /Users/administrator/Code/hermes-apple-calendar-assistant/logs/flight_auto_enhancer.out.log
tail -f /Users/administrator/Code/hermes-apple-calendar-assistant/logs/flight_auto_enhancer.err.log
```

最近一次运行结果通常在标准输出日志中；AppleScript、权限或 Python 异常会进入错误日志。

## 查看处理标识 `flight_seen.json`

```bash
cd /Users/administrator/Code/hermes-apple-calendar-assistant
python3 -m json.tool data/flight_seen.json
```

`data/flight_seen.json` 使用 fingerprint 格式保存处理记录：

```json
{
  "events": {
    "<fingerprint>": {
      "fingerprint": "<fingerprint>",
      "calendar": "飞行计划",
      "title": "...",
      "start": "...",
      "end": "...",
      "location_written": "北京首都T3",
      "status": "enhanced",
      "processed_at": "2026-04-24T12:51:13+08:00",
      "source": "flight_auto_enhancer"
    }
  }
}
```

其中 `events.<fingerprint>.status` 可能包括：

- `enhanced`
- `skipped_has_location`
- `skipped_no_parse`
- `failed`

`failed` 会在后续运行时重试。`enhanced`、`skipped_no_parse` 会跳过。
`skipped_has_location` 只有在原事件已有真实非空 location 时才会写入。

## 如何重置某条处理记录

先找到目标事件的 `fingerprint`，然后删除对应记录。删除后，下次自动任务会再次尝试处理。

```bash
cd /Users/administrator/Code/hermes-apple-calendar-assistant
python3 -m json.tool data/flight_seen.json
```

手动编辑 `data/flight_seen.json`，删除对应的条目：

```json
"<fingerprint>": {
  "...": "..."
}
```

也可以清理历史上因为 AppleScript `missing value` 被误判而产生的错误跳过记录：

```bash
python3 scripts/flight_auto_enhancer.py clean-bad-location-skips
```

删除完成后再次运行：

```bash
python3 scripts/flight_auto_enhancer.py run
```
