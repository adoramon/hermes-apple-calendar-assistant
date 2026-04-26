# Business Travel Secretary

Status: Phase 45 Pro.

本阶段把“单个酒店订单写入”升级为“多订单出行聚合”。当用户连续发送机票、酒店、
高铁订单文字或截图 OCR 文本时，系统应自动整理为一次 Trip，并在确认后一次性写入
Apple Calendar。

## 微信处理流程

1. 用户发送机票、酒店或高铁订单截图。
2. Hermes / 多模态模型提取截图文字。
3. 调用：

```bash
python3 scripts/travel_order_parser.py parse --text "<订单文字>"
```

4. 如果识别为 `flight`、`hotel` 或 `train`，调用：

```bash
python3 scripts/trip_aggregator.py add --text "<订单文字>"
```

5. 展示统一行程草稿：

```bash
python3 scripts/trip_flow.py draft --trip-id <id>
```

6. 如果缺少日历选择，询问：

- 商务计划
- 个人计划
- 夫妻计划

系统可以根据订单文字给出建议：包含“客户/会议/商务/出差”时建议 `商务计划`，
包含“双人/夫妻/太太/家人”时建议 `夫妻计划`，其他情况建议 `个人计划`。建议只
能用于提示，不能替用户默认确认。

7. 用户选择后调用：

```bash
python3 scripts/trip_flow.py set-calendar --trip-id <id> --calendar "商务计划"
```

8. 用户确认后调用：

```bash
python3 scripts/trip_flow.py confirm --trip-id <id>
```

## 日历写入规则

只允许写入：

- 商务计划
- 个人计划
- 夫妻计划

不允许写入：

- 飞行计划
- 家庭计划
- Apple Reminders

## 去重

`data/trip_seen.json` 记录已写入事件 fingerprint：

```text
event_type + title + start + end + confirmation_number
```

confirm 时如果 fingerprint 已存在，返回 `skipped_duplicate`，不会覆盖旧日程，也不会
删除旧日程。

## 草稿示例

```text
高先生，我把这几条订单整理成一次完整出行了 ✈️🏨

📍 目的地：上海
📅 时间：5月1日 - 5月3日

行程如下：

1. ✈️ 5月1日 08:30 - 10:45
   航班｜CA123 北京→上海
   📍 北京首都T3

2. 🏨 5月1日 15:00 - 5月3日 12:00
   入住｜上海外滩悦榕庄
   📍 上海市虹口区海平路19号

3. 🚄 5月3日 14:30 - 19:20
   高铁｜G12 上海虹桥→北京南
   📍 上海虹桥站

请您确认写入哪个日历：
- 商务计划
- 个人计划
- 夫妻计划
```

## 安全边界

- 不直接写 Calendar，必须确认。
- 不写商务/个人/夫妻以外的日历。
- 不写飞行计划。
- 不写 Apple Reminders。
- 不请求外部网络。
- 不覆盖旧日程。
- 不删除旧日程。
- 不读取微信 token。
- 不保存截图原图。
