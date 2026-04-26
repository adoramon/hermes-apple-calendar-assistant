# Hermes Cron Outbox Bridge

当前状态：`v2.0-rc Hermes Cron bridge enabled`。

`scripts/hermes_cron_outbox_bridge.py` 是一个专门给 Hermes cron `--script` 调用的
outbox bridge。它读取本地 `pending` outbox，输出适合 Hermes Cron Delivery 发送
的纯文本；在显式传入 `--mark-sent` 时，会把已输出记录标记为
`sent_via_hermes_cron`。

## 功能说明

CLI：

```bash
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent
```

行为：

- 读取 `data/outbox_messages.jsonl`
- 找出 `status=pending` 的记录
- 按 `created_at` 升序输出
- 最多输出 `limit` 条
- 输出适合 Hermes Cron Delivery 的纯文本
- 默认 `--empty-mode silent`，无 pending 时 stdout 为空，避免无意义通知
- 仅在传入 `--mark-sent` 时，才把已输出记录标记为 `sent_via_hermes_cron`

可选参数：

```bash
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode silent
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode message
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent --empty-mode silent
```

- `silent`：无 pending 时 stdout 为空
- `message`：无 pending 时输出 `高总，当前没有待发送的日程提醒。`
- `--mark-sent`：输出后把这些记录标记为 `sent_via_hermes_cron`

示例输出：

```text
高先生，提醒您一下 ⏰

您还有 60 分钟有个安排：

📌 再次测试
🕐 今天 13:00
📍 望京北路9号叶青大厦D座7层

您可以直接回复：
- 推迟30分钟
- 改到明天上午10点
- 取消这个日程
```

多条提醒时：

```text
高总，接下来有 2 个安排，我帮您盯着时间 📅

1. 🕐 今天 13:00
   📌 再次测试
   📍 望京北路9号叶青大厦D座7层

2. 🕐 今天 15:00
   📌 客户会议

需要调整的话，直接回复我就行。
```

输出要求：

- 中文自然，适当使用 emoji，不输出 JSON。
- 不输出内部 fingerprint。
- 不输出 outbox id。
- 地点为空时不显示地点行。
- 时间尽量显示为 `今天 13:00`、`明天 09:30`。

## 手动测试命令

```bash
python3 -m py_compile scripts/*.py
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode message
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --mark-sent --empty-mode message
python3 scripts/outbox.py list --limit 20
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 5 --empty-mode message
python3 scripts/flight_auto_enhancer.py run
```

## 如何创建 Hermes cron job

先在 `sunny-wechat-lite` profile 的专属脚本目录安装 Python wrapper：

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

注意：不同 Hermes profile 应使用各自的 profile 专属脚本目录，而不是全局
`~/.hermes/scripts/`。例如这里使用的是：

```bash
~/.hermes/profiles/sunny-wechat-lite/scripts/
```

```bash
sunny-wechat-lite cron create "every 5m" \
  "请将脚本输出内容原样发送给我；如果为空则不要回复。" \
  --name "calendar-outbox-wechat-bridge" \
  --script "calendar_outbox_bridge.py" \
  --deliver "weixin:<chat_id>"
```

推荐在 Hermes profile 内部使用 cron `--script` 读取 outbox，并把 stdout 通过
`--deliver` 投递到 `weixin:<chat_id>`。

当前正式启用命令即为上面的 cron create 命令。

说明：

- wrapper 脚本不放在仓库中。
- wrapper 脚本属于 Hermes profile 本地运行配置。
- 不应提交 token，`chat_id` 应继续使用占位符。
- 不同 profile 要放到各自 `~/.hermes/profiles/<profile>/scripts/` 目录。

## 正式启用链路

```text
Apple Calendar
  -> reminder_worker launchd
  -> outbox_messages.jsonl
  -> Hermes Cron bridge script
  -> Hermes Cron Delivery
  -> Weixin Adapter
  -> 微信
```

在这条链路中：

- Calendar Skill 不读取 Hermes token。
- Calendar Skill 不直连微信。
- 真实发送由 Hermes Cron Delivery 完成。
- `sent_via_hermes_cron` 表示记录已经交给 Hermes Cron stdout 进入 Delivery 链路，
  bridge 不再重复发送。

## 为什么需要暂停 outbox_consumer dry-run launchd

`outbox_consumer.py` dry-run launchd 会读取 `pending` 并把状态改成
`sent_dry_run`。如果它保持运行，Hermes Cron bridge 可能在读取前就失去这些待发送
记录，从而造成真实投递链路读不到消息。

因此，在 Hermes Cron bridge 正式启用后，`outbox_consumer` dry-run launchd 必须
保持暂停，避免抢占 `pending` 消息。

## 当前阶段边界

- 默认行为仍可只读 `pending`，不标记 `sent`。
- 传入 `--mark-sent` 时，bridge 会在输出后将这些记录标记为
  `sent_via_hermes_cron`。
- 本阶段不删除 outbox。
- 本阶段不发送网络请求。
- 本阶段不读取 Hermes token。
- 本阶段不直连 WeChat / Telegram。

bridge 写入的 result 结构为：

```json
{
  "mode": "hermes_cron",
  "processed_at": "ISO时间",
  "note": "Message handed to Hermes Cron stdout for delivery"
}
```

## 为什么默认使用 empty-mode silent

`--empty-mode silent` 的作用是：当当前没有 `pending` outbox 时，bridge 输出空字
符串，从而避免 Hermes Cron Delivery 发送“没有提醒”的无意义通知。

如果需要手动验证 bridge 是否正常工作，可在测试时使用
`--empty-mode message`。

## 正式启用建议

- `--mark-sent` 表示交给 Hermes Cron stdout 后即标记 `sent_via_hermes_cron`。
- 如果 Hermes Cron Delivery 之后失败，目前无法自动回滚。
- 初期建议先用低频率、`limit=1`、`every 5m` 验证。

## 风险说明

- `--mark-sent` 的标记时点早于 Hermes 最终投递结果。
- 如果 Hermes Cron Delivery 之后失败，目前无法自动回滚。
- 如果不传 `--mark-sent`，`pending` 会重复发送。
- 微信消息会带 `Cronjob Response` 包装。
- 当前 bridge 已优化正文文案，但 Hermes Cron Delivery 外层仍可能添加
  `Cronjob Response` / `job_id` 包装；正文应保持个人助理式中文提醒。
- 正式启用时仍建议从低频率、小 `limit` 开始。
