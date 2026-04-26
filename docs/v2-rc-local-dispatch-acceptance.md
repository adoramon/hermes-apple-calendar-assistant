# v2.0-rc Local Dispatch Acceptance

当前状态：`v2.0-rc Hermes Cron bridge enabled`。

本阶段已完成 Hermes Cron bridge 正式启用文档收口。当前真实微信提醒链路由
Hermes Cron Delivery 负责；Calendar Skill 本身仍不读取 token、不直连微信，也
不请求外部网络。

## 完整链路

```text
Apple Calendar
  -> reminder_worker launchd
  -> outbox_messages.jsonl
  -> Hermes profile script calendar_outbox_bridge.py
  -> Hermes Cron Delivery
  -> Weixin Adapter
  -> 微信
```

`sent_via_hermes_cron` 只表示记录已交给 Hermes Cron stdout 进入 Delivery 链
路，不代表下游微信投递一定成功。

## 安全边界

- 不请求外部网络
- 不修改 Calendar
- 不删除 outbox
- 不修改 message 内容
- 不引入第三方依赖
- Calendar Skill 不读取 token
- Calendar Skill 不直连微信

## 验收命令

```bash
python3 -m py_compile scripts/*.py
python3 -m json.tool config/settings.json
python3 -m json.tool data/outbox_messages.jsonl || true
python3 scripts/reminder_worker.py scan --format outbound --channel hermes --recipient default --write-outbox
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 1 --empty-mode message
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 1 --mark-sent --empty-mode message
python3 scripts/outbox.py list --limit 20
python3 scripts/flight_auto_enhancer.py run
```

`data/outbox_messages.jsonl` 是 JSONL，不是单个 JSON 文档；当文件为空或多行时，
`json.tool` 可能失败，因此验收命令允许 `|| true`。

## 如果没有 pending 记录

如果当前没有即将到来的提醒，`reminder_worker` 可能不会写入 pending outbox。可以
用以下本地命令制造一条测试 pending 记录：

```bash
python3 - <<'PY'
from scripts import outbox

message = {
    "channel": "hermes",
    "recipient": "default",
    "message": "dry-run 测试提醒",
    "metadata": {
        "type": "calendar_reminder",
        "fingerprint": "local-dispatch-test:15",
        "offset_minutes": 15,
    },
}
print(outbox.append_outbox_message(message))
PY
```

随后运行：

```bash
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 1 --empty-mode message
python3 scripts/hermes_cron_outbox_bridge.py read-pending --limit 1 --mark-sent --empty-mode message
python3 scripts/outbox.py list --limit 20
```

## 为什么需要暂停 outbox_consumer dry-run launchd

`outbox_consumer.py` dry-run launchd 会把 `pending` 直接改成 `sent_dry_run`。如果
它继续运行，就会在 Hermes Cron bridge 读取之前抢占这些消息，导致真实发送链路读
不到待投递记录。

因此，在当前正式启用状态下，`outbox_consumer` dry-run launchd 必须保持暂停。

## 正式启用命令

```bash
sunny-wechat-lite cron create "every 5m" \
  "请将脚本输出内容原样发送给我；如果为空则不要回复。" \
  --name "calendar-outbox-wechat-bridge" \
  --script "calendar_outbox_bridge.py" \
  --deliver "weixin:<chat_id>"
```

其中 `calendar_outbox_bridge.py` 必须放在 profile 专属目录：

```bash
~/.hermes/profiles/sunny-wechat-lite/scripts/
```

wrapper 必须是 Python 脚本，不能是 shell。

初期建议 `limit=1`、`every 5m`。

## 自动运行判断

已验证 `calendar-outbox-wechat-bridge` 会自动运行。

当前环境下，`sunny-wechat-lite cron list` 可能仍显示 `Gateway is not running`，
但这条提示不能单独作为失败判断。更可靠的判断依据是：

- `Last run` 是否更新为 `ok`
- `Next run` 是否持续自动滚动

## 后续真实发送前缺口

- `real_send_enabled` 必须继续保持 `false`。
- Hermes Cron Delivery 失败后仍无法自动回滚 `sent_via_hermes_cron`。
- 微信消息仍会带 `Cronjob Response` 包装。
- 还需要继续完善失败处理、失败重试和更细粒度审计策略。
