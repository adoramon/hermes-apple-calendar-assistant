# Trip Aggregator

Status: Phase 49 flight-plan merge.

`scripts/trip_aggregator.py` 将酒店、高铁订单和机票匹配线索聚合为一次出行 Trip。它只写入
`data/trip_drafts.json`，不写 Apple Calendar。

航班由航旅纵横统一管理，并自动写入 Apple Calendar 的 `飞行计划`。本项目不创建航班
日程，机票截图只用于匹配和关联 `飞行计划`。

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
- `source=travel_intent` 的计划 Trip 优先接收后续酒店/高铁/机票线索。
- `order_type=flight` 不进入待创建事件，只尝试关联 `飞行计划`。
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
  "linked_flights": {},
  "flight_link_status": "flight_pending_sync",
  "planning_status": "planned_only",
  "calendar": null,
  "suggested_calendar": "商务计划",
  "needs_calendar_choice": true,
  "missing_fields": ["calendar"]
}
```

## 安全边界

- 不直接写 Calendar。
- 不创建航班日程。
- 不写 `飞行计划`。
- 不修改 `飞行计划`。
- 不删除 `飞行计划`。
- 不重复写航班。
- 不请求外部网络。
- 不读取微信 token。
- 不保存截图原图。
- 不写 Apple Reminders。

## 微信端标准测试流程

1. 用户连续发送：
- 机票订单截图
- 酒店订单截图
- 高铁或返程订单截图

2. Hermes / 多模态模型先提取每张截图中的 OCR 文本。
3. 每段订单文字先调用：

```bash
python3 scripts/travel_order_parser.py parse --text "<订单文字>"
```

4. 解析成功后继续调用：

```bash
python3 scripts/trip_aggregator.py add --text "<订单文字>"
```

5. 聚合结果交给：

```bash
python3 scripts/trip_flow.py draft --trip-id <id>
```

6. Hermes 展示统一 Trip 草稿，并追问写入：
- 商务计划
- 个人计划
- 夫妻计划

7. 用户确认日历后调用：

```bash
python3 scripts/trip_flow.py set-calendar --trip-id <id> --calendar "商务计划"
```

8. 用户明确确认后才调用：

```bash
python3 scripts/trip_flow.py confirm --trip-id <id>
```

9. 一次性写入 Apple Calendar 中对应的多条日程。

## 预期日志关键字

- `travel_order_parser.py parse`
- `trip_aggregator.py add`
- `trip_flow.py draft`
- `trip_flow.py set-calendar`
- `trip_flow.py confirm`

## 成功判断标准

- Trip 中包含去程交通、酒店入住、返程交通。
- 写入前已展示统一 Trip 草稿。
- 日历选择已被用户明确确认。
- 确认后 Apple Calendar 中出现多条对应日程。
- 不写 `飞行计划`。
- 不写 Apple Reminders。
- 不直接跳过确认。

## 失败排查

### A. 截图未识别

- 检查 Hermes 是否提取出 OCR 文本。
- 如果没有可用文字，让用户复制订单文字重试。

### B. 没进入 Trip 流程

- 检查 `SKILL.md` 是否仍要求优先 `travel_order_parser.py`。
- 检查 `gateway.log` 是否有 parser 调用。

### C. 三张订单没有聚合到同一 Trip

- 检查 `destination_city` 是否一致或合理。
- 检查日期是否相差超过 3 天。
- 检查 `python3 scripts/trip_aggregator.py list` 输出。

### D. 没追问日历

- 检查 `trip_flow.py draft` 返回的 `missing_fields` 是否包含 `calendar`。

### E. 直接写入

- 属于严重错误，必须修正 `SKILL.md`。
- 所有写入前必须先 `confirm`。
