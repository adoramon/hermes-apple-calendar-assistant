# Hermes Profile Install

本文说明如何把 `hermes-apple-calendar-assistant` 接入
`sunny-wechat-lite` Hermes profile。当前状态是
`v2.0-rc Hermes Cron bridge enabled`：提醒 outbox 由 Hermes Cron Delivery 负责
真实投递到微信，但 Calendar Skill 本身不读取 token、不直连微信，也不访问外部网
络。

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

## 启用 Trip Briefing launchd

`trip_briefing_worker.py` 是整趟出行摘要 Worker。它读取 `data/trip_drafts.json`，
为未来 24-48 小时内开始的 Trip 生成行前摘要，并写入 `data/outbox_messages.jsonl`。
它不会真实发送微信、Telegram，也不会访问外部网络。

launchd 模板：

```text
deploy/launchd/com.adoramon.hermes-apple-calendar-trip-briefing-worker.plist
```

该任务每 30 分钟运行一次：

```bash
python3 scripts/trip_briefing_worker.py scan --hours 48
```

安装：

```bash
mkdir -p /Users/administrator/Code/hermes-apple-calendar-assistant/logs
mkdir -p ~/Library/LaunchAgents
cp /Users/administrator/Code/hermes-apple-calendar-assistant/deploy/launchd/com.adoramon.hermes-apple-calendar-trip-briefing-worker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-trip-briefing-worker.plist
```

卸载：

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-trip-briefing-worker.plist
rm ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-trip-briefing-worker.plist
```

查看日志：

```bash
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/trip_briefing_worker.out.log
tail -n 100 /Users/administrator/Code/hermes-apple-calendar-assistant/logs/trip_briefing_worker.err.log
```

完整链路：

```text
Apple Calendar / trip_drafts.json
  -> trip_briefing_worker launchd
  -> outbox_messages.jsonl
  -> Hermes Cron bridge script
  -> Hermes Cron Delivery
  -> Weixin Adapter
  -> 微信
```

区别：

- `reminder_worker`：单个日程提醒。
- `trip_briefing_worker`：整趟出行摘要。

## 当前真实发送路径

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

不要配置 Telegram token、微信发送接口或外部 webhook。真实发送当前由 Hermes
Cron Delivery 负责，而不是由本项目直接调用外部接口。

正式启用命令：

先创建 `sunny-wechat-lite` profile 的 Python wrapper：

```bash
mkdir -p ~/.hermes/profiles/sunny-wechat-lite/scripts
cat > ~/.hermes/profiles/sunny-wechat-lite/scripts/calendar_outbox_bridge.py <<'PY'
#!/usr/bin/env python3
import sys
import subprocess

PROJECT = "/Users/administrator/Code/hermes-apple-calendar-assistant"

cmd = [
    sys.executable,
    "scripts/hermes_cron_outbox_bridge.py",
    "read-pending",
    "--limit", "1",
    "--mark-sent",
    "--empty-mode", "silent",
]

proc = subprocess.run(
    cmd,
    cwd=PROJECT,
    capture_output=True,
    text=True,
)

if proc.stdout:
    print(proc.stdout.strip())

if proc.stderr:
    print(proc.stderr.strip(), file=sys.stderr)

sys.exit(proc.returncode)
PY
chmod +x ~/.hermes/profiles/sunny-wechat-lite/scripts/calendar_outbox_bridge.py
```

不同 profile 应使用各自 profile 的 `scripts/` 目录。这里不是全局
`~/.hermes/scripts/`，而是：

```bash
~/.hermes/profiles/sunny-wechat-lite/scripts/
```

然后创建 cron job：

```bash
sunny-wechat-lite cron create "every 5m" \
  "请将脚本输出内容原样发送给我；如果为空则不要回复。" \
  --name "calendar-outbox-wechat-bridge" \
  --script "calendar_outbox_bridge.py" \
  --deliver "weixin:<chat_id>"
```

说明：

- wrapper 脚本不放在仓库中。
- wrapper 脚本属于 Hermes profile 本地运行配置。
- 不应提交 token，`chat_id` 使用占位符即可。

完整链路：

```text
Apple Calendar
  -> reminder_worker launchd
  -> trip_briefing_worker launchd
  -> outbox_messages.jsonl
  -> Hermes Cron bridge script
  -> Hermes Cron Delivery
  -> Weixin Adapter
  -> 微信
```

`sent_via_hermes_cron` 表示该记录已经交给 Hermes Cron stdout 进入 Delivery 链
路，不会再被 bridge 重复发送。它不保证后续微信投递一定成功。

## 暂停 outbox_consumer dry-run launchd

`outbox_consumer.py` dry-run launchd 已暂停，原因是它会把 `pending` 先改成
`sent_dry_run`，从而抢占 Hermes Cron bridge 需要读取的待发送消息。

在正式启用 Hermes Cron bridge 后，不应同时运行 `outbox_consumer` dry-run
launchd。

如果此前已安装过该 launchd，可保持 unload 状态：

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-outbox-consumer.plist
```

当前限制：

- Hermes Cron Delivery 失败后无法自动回滚 `sent_via_hermes_cron`
- 微信消息会带 `Cronjob Response` 包装
- 初期建议 `limit=1`、`every 5m`

## 微信提醒后续操作测试

Phase 39 已记录 reminder action draft flow 的 Hermes 微信交互测试。用户收到日历
提醒后，可在微信中回复：

- `延后30分钟`
- `取消这个日程`
- `改到明天上午10点`

预期行为：

- Hermes 先调用项目脚本生成操作草稿：

```bash
python3 scripts/reminder_action_flow.py draft --text "延后30分钟"
```

- draft 阶段不直接修改 Calendar。
- 删除和改期必须等待用户二次确认。

如果微信回复没有生成草稿，优先排查：

- `tail -n 100 ~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log`
- `tail -n 100 ~/.hermes/profiles/sunny-wechat-lite/logs/gateway.error.log`
- `python3 scripts/outbox.py list --limit 20`

## 验收与回滚

完整验收清单见：

```text
docs/v2-rc-local-dispatch-acceptance.md
```

如需回滚当前启用链路，建议先停用 reminder worker 和 Hermes Cron bridge；
`outbox_consumer` dry-run launchd 只有在明确回退到本地 dry-run 消费模式时才考虑恢
复。保留 flight auto enhancer：

```bash
launchctl unload ~/Library/LaunchAgents/com.adoramon.hermes-apple-calendar-reminder-worker.plist
```

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
