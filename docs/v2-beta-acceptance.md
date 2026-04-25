# v2.0-beta Dry-run Acceptance

当前状态：`v2.0-beta dry-run accepted`。

本验收说明只覆盖本地 dry-run 链路。项目仍不真实发送微信、Telegram、Hermes
push，也不访问任何外部网络发送接口。

## 已启用的 launchd

本阶段记录以下 launchd 可作为当前链路启用：

- `flight_auto_enhancer`
- `reminder_worker`
- `outbox_consumer`

对应模板：

- `deploy/launchd/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist`
- `deploy/launchd/com.adoramon.hermes-apple-calendar-reminder-worker.plist`
- `deploy/launchd/com.adoramon.hermes-apple-calendar-outbox-consumer.plist`

## 完整 dry-run 链路

```text
Apple Calendar
  -> reminder_worker
  -> message_adapter
  -> outbox_messages.jsonl
  -> outbox_consumer dry-run
  -> sent_dry_run
```

`sent_dry_run` 只表示 outbox 记录已被本地 dry-run consumer 消费，不代表真实消息
已发送给微信、Telegram 或 Hermes。

Hermes 仍可以通过本地 CLI 读取 pending outbox：

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

如果 `outbox_consumer` launchd 自动消费很快，pending 查询可能为空。这通常表示
pending 记录已经变成 `sent_dry_run`，不代表真实发送。

## 验收命令

从仓库根目录执行：

```bash
cd /Users/administrator/Code/hermes-apple-calendar-assistant
```

Python 编译：

```bash
python3 -m py_compile scripts/*.py
```

JSON 检查：

```bash
python3 -m json.tool config/settings.json
python3 -m json.tool data/flight_seen.json
python3 -m json.tool data/reminder_seen.json
python3 -m json.tool data/pending_confirmations.json
```

launchd 状态：

```bash
launchctl list | grep com.adoramon.hermes-apple-calendar-flight-auto-enhancer
launchctl list | grep com.adoramon.hermes-apple-calendar-reminder-worker
launchctl list | grep com.adoramon.hermes-apple-calendar-outbox-consumer
```

查看日志：

```bash
tail -n 100 logs/flight_auto_enhancer.out.log
tail -n 100 logs/flight_auto_enhancer.err.log
tail -n 100 logs/reminder_worker.out.log
tail -n 100 logs/reminder_worker.err.log
tail -n 100 logs/outbox_consumer.out.log
tail -n 100 logs/outbox_consumer.err.log
```

手动扫描并写入 outbox：

```bash
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

查看 outbox：

```bash
python3 scripts/outbox.py list --limit 20
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

dry-run 消费：

```bash
python3 scripts/outbox_consumer.py dry-run --limit 10
```

飞行计划自动增强回归：

```bash
python3 scripts/flight_auto_enhancer.py run
```

## 期望结果

- 所有 Python 文件可编译。
- JSON 文件格式有效。
- launchd list 可看到已启用的任务，或明确知道未安装。
- reminder worker 输出统一 JSON。
- outbox list 能展示本地队列状态。
- outbox consumer 只把 pending 标记为 `sent_dry_run`。
- flight auto enhancer 只处理 `飞行计划` 的 `location` 字段，已处理事件应幂等跳过。

## 回滚方法

如需回滚 dry-run outbox 链路，卸载 reminder worker 和 outbox consumer launchd：

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

可选删除 LaunchAgent 文件：

```bash
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

建议保留 `flight_auto_enhancer`，因为它只服务 `飞行计划` location 自动增强，和
dry-run outbox 消费链路相互独立。

## 仍不包含

- 不真实发送微信。
- 不真实发送 Telegram。
- 不调用外部网络发送接口。
- 不创建 Calendar alarm。
- 不自动修改 outbox message 内容。
