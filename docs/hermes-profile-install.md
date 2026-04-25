# Hermes Profile Install

本文说明如何把 `hermes-apple-calendar-assistant` 接入
`sunny-wechat-lite` Hermes profile。当前 v2.0-beta 仍是本地 dry-run 阶段：
提醒 outbox 不真实发送微信、Telegram，也不访问外部网络。

## 推荐安装路径

推荐把仓库保留在固定路径：

```bash
/Users/administrator/Code/hermes-apple-calendar-assistant
```

当前 `SKILL.md` 和 launchd 模板都使用这个路径。若移动仓库，需要同步更新文档、
launchd plist 和 Hermes profile 配置中的路径。

## 安装或链接到 sunny-wechat-lite

先确认仓库存在：

```bash
cd /Users/administrator/Code/hermes-apple-calendar-assistant
python3 -m py_compile scripts/*.py
```

然后把 `SKILL.md` 放入 `sunny-wechat-lite` profile 的 custom skill 目录。不同
Hermes 安装方式的目录可能不同，建议优先使用软链接，便于后续仓库更新自动生效：

```bash
ln -s /Users/administrator/Code/hermes-apple-calendar-assistant/SKILL.md \
  "<sunny-wechat-lite-profile-skills-dir>/apple-calendar-assistant.SKILL.md"
```

如果 profile 不支持软链接，也可以复制：

```bash
cp /Users/administrator/Code/hermes-apple-calendar-assistant/SKILL.md \
  "<sunny-wechat-lite-profile-skills-dir>/apple-calendar-assistant.SKILL.md"
```

请把 `<sunny-wechat-lite-profile-skills-dir>` 替换成你的 Hermes profile 实际
skills 目录。

## 验证 Hermes 能读取 SKILL.md

在 Hermes / WeChat 对话里询问一个明确的日程查询，例如：

```text
今天有什么安排？
```

期望行为：

- Hermes 使用 `calendar_ops.py events` 查询。
- 如果没有明确时间范围，Hermes 会先追问。
- Hermes 不应直接编造 Calendar 结果。

也可以让 Hermes 解释当前日历能力，确认它知道：

- 创建日程必须先生成草稿。
- 创建草稿默认做冲突检测。
- confirm 前必须展示给用户确认。
- reminder/outbox 当前不真实发送。

## 手动测试自然语言创建日程

先本地验证解析器：

```bash
python3 scripts/nlp_event_parser.py parse "明天下午三点和王总开会"
```

在 Hermes 对话中说：

```text
明天下午三点和王总开会
```

期望行为：

- Hermes 先调用 `nlp_event_parser.py parse`。
- Hermes 再调用 `interactive_create.py create-draft --check-conflict`。
- Hermes 展示草稿、冲突情况和建议时间。
- 只有用户明确确认后，才调用 `interactive_create.py confirm`。

## 手动测试 pending outbox

查看本地 pending outbox：

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

在 Hermes 对话中询问：

```text
有什么待处理提醒？
```

期望行为：

- Hermes 调用 `hermes_outbox_cli.py pending --limit 10`。
- Hermes 展示 pending messages。
- Hermes 不自动标记 `sent_dry_run`。

当用户明确说“这条提醒已处理”并指定 record id 后，Hermes 才调用：

```bash
python3 scripts/hermes_outbox_cli.py mark-dry-run-sent --id "<record_id>"
```

## 启用 reminder worker dry-run outbox 链路

`reminder_worker.py` 已支持作为 dry-run outbox 链路的上游 Worker。启用该模式时，
它只读取 Calendar.app，生成 outbound message，并写入
`data/outbox_messages.jsonl`；它不会真实发送微信、Telegram，也不会访问外部网络。

建议用于 outbox 链路的命令是：

```bash
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
```

如果要让 launchd 后台运行该链路，请确认
`com.adoramon.hermes-apple-calendar-reminder-worker.plist` 的
`ProgramArguments` 使用上面的参数。该任务每 1 分钟运行一次，stdout/stderr 写入：

```text
/Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.out.log
/Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.err.log
```

安装：

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-reminder-worker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

卸载：

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

查看日志：

```bash
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/reminder_worker.err.log
```

通过 Hermes 查询 pending outbox：

```bash
python3 scripts/hermes_outbox_cli.py pending --limit 10
```

Hermes 应展示 pending messages，但不要自动标记为 `sent_dry_run`；只有用户明确确认
已处理指定 record id 后，才调用 `mark-dry-run-sent`。

## 不启用真实发送

当前配置应保持：

```json
{
  "outbox": {
    "send_mode": "dry_run",
    "allowed_channels": ["hermes"],
    "default_channel": "hermes",
    "default_recipient": "default",
    "max_messages_per_run": 10
  }
}
```

不要配置 Telegram token、微信发送接口或外部 webhook。当前阶段的 outbox 只用于
本地 dry-run 消费。

## launchd 可选项

可以按需安装：

- `com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist`
- `com.adoramon.hermes-apple-calendar-reminder-worker.plist`
- `com.adoramon.hermes-apple-calendar-outbox-consumer.plist`

安装前请先阅读对应文档：

- `docs/flight-auto-enhancer.md`
- `docs/reminder-worker.md`
- `docs/outbox-consumer.md`

## 回滚方法

如需从 `sunny-wechat-lite` profile 中移除本 skill：

```bash
rm "<sunny-wechat-lite-profile-skills-dir>/apple-calendar-assistant.SKILL.md"
```

如果安装过 launchd，请卸载对应 LaunchAgent：

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

再删除 plist：

```bash
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-flight-auto-enhancer.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

回滚不会删除仓库数据文件。若需要清理运行状态，请先备份 `data/` 后再手动处理。
