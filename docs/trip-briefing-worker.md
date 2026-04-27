# Trip 行前摘要 Worker

Status: Phase 52.

`scripts/trip_briefing_worker.py` 用于在出差或旅行前生成微信行前摘要。它只读取 Trip
草稿和确认状态，只写本地 outbox，由现有 Hermes Cron bridge 统一推送微信。

## 功能说明

当未来 24-48 小时内有已确认或部分确认的 Trip 时，Worker 会生成一条 briefing：

- 出行目的地
- 去程航班或高铁
- 酒店入住
- 客户拜访或会议
- 返程
- 待确认事项
- 出发前建议

Trip 来源包括：

- 一句话出差模式生成的 `travel_intent` Trip。
- Trip Aggregator 聚合的酒店/高铁订单。
- 与 Apple Calendar「飞行计划」只读关联的航班。

## 手动扫描

```bash
python3 scripts/trip_briefing_worker.py scan --hours 48
```

扫描规则：

- 读取 `data/trip_drafts.json`。
- 只处理 `status=draft` 或 `status=confirmed` 的 Trip。
- 只处理 `planning_status` 不为空的 Trip。
- Trip 开始时间必须在未来 `--hours` 小时内。
- 每次扫描最多为同一个 Trip 生成当前窗口对应的一种 briefing。

briefing 类型：

- `pre_trip_48h`
- `pre_trip_24h`
- `travel_day_morning`

## Outbox 推送机制

Worker 不直连微信，不读取微信 token，也不发送网络请求。它只调用 `outbox.py` 写入：

```json
{
  "channel": "hermes",
  "recipient": "default",
  "message": "高先生，明天这趟上海出差我帮您整理好了...",
  "metadata": {
    "type": "trip_briefing",
    "trip_id": "...",
    "briefing_type": "pre_trip_24h"
  }
}
```

随后由现有 Hermes Cron bridge 读取 `data/outbox_messages.jsonl` 并推送微信。

查看最近 outbox：

```bash
python3 scripts/outbox.py list --limit 20
```

## 幂等文件

幂等状态保存在 `data/trip_briefing_seen.json`：

```json
{
  "items": {
    "<trip_id>|pre_trip_24h": {
      "sent_at": "ISO时间",
      "outbox_id": "..."
    }
  }
}
```

同一 `trip_id + briefing_type` 只发送一次。`pre_trip_48h` 和 `pre_trip_24h` 是不同
briefing 类型，可以分别发送一次。

## 重置 Briefing

如果需要重发某条 briefing：

1. 打开 `data/trip_briefing_seen.json`。
2. 删除对应 key，例如 `<trip_id>|pre_trip_24h`。
3. 再运行：

```bash
python3 scripts/trip_briefing_worker.py scan --hours 48
```

如果 outbox 中已有完全相同消息，`outbox.py` 仍可能按自身 idempotency 跳过重复记录。

## 后续定时运行

本阶段只提供手动命令和文档，不安装 launchd，不改 Hermes Cron 配置。

后续可接入：

- 用户级 launchd 定时任务。
- Hermes Cron 脚本。
- 与现有 reminder worker 同频运行。

## 安全边界

- 不修改 Calendar。
- 不创建日程。
- 不删除日程。
- 不请求外部网络。
- 不读取微信 token。
- 不直连微信。
- 只写 outbox。
- 由 Hermes Cron bridge 统一推送。
