# Trip Aggregator

Status: Phase 45 Pro.

`scripts/trip_aggregator.py` 将机票、酒店、高铁订单聚合为一次出行 Trip。它只写入
`data/trip_drafts.json`，不写 Apple Calendar。

## 输入流程

```bash
python3 scripts/travel_order_parser.py parse --text "<订单文字>"
python3 scripts/trip_aggregator.py add --text "<订单文字>"
python3 scripts/trip_aggregator.py list
python3 scripts/trip_aggregator.py show --trip-id <id>
python3 scripts/trip_aggregator.py cancel --trip-id <id>
```

截图场景中，本 Skill 不做 OCR。Hermes / 多模态模型先提取文字，再把文字传给
`travel_order_parser.py` 或 `trip_aggregator.py`。

## 聚合规则

- 同一目的地城市优先合并。
- 订单日期与 Trip 起止日期相差不超过 3 天时优先合并。
- 酒店入住日期与交通到达日期接近时合并。
- 回程交通从目的地返回北京或原出发城市时合并。
- 无法判断时创建新 Trip，并由 Hermes 询问用户是否归并。

## Trip 结构

```json
{
  "trip_id": "trip_YYYYMMDD_city_hash",
  "status": "draft",
  "title": "上海商务出行",
  "destination_city": "上海",
  "start_date": "2026-05-01",
  "end_date": "2026-05-03",
  "orders": [],
  "calendar": null,
  "suggested_calendar": "商务计划",
  "needs_calendar_choice": true,
  "missing_fields": ["calendar"]
}
```

## 安全边界

- 不直接写 Calendar。
- 不请求外部网络。
- 不读取微信 token。
- 不保存截图原图。
- 不写 Apple Reminders。
