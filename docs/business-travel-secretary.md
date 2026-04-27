# Business Travel Secretary

Status: Phase 47 one-sentence travel planning + WeChat validation closure.

本阶段把“单个酒店订单写入”升级为“多订单出行聚合”。当用户连续发送机票、酒店、
高铁订单文字或截图 OCR 文本时，系统应自动整理为一次 Trip，并在确认后一次性写入
Apple Calendar。

Phase 47 在此基础上新增“一句话出差模式”：用户还可以先只说出差/旅行意图，由
`travel_intent_parser.py` 和 `trip_planner.py` 生成本地计划草稿；后续如果用户再发
机票、酒店、高铁订单截图，应继续转回真实订单聚合流程，逐步替换成准确行程。

## 一句话出差模式

当用户只说自然语言意图、还没有订单时，先调用：

```bash
python3 scripts/travel_intent_parser.py parse "下周去上海见客户，两天"
```

识别为出差/旅行意图后，再调用：

```bash
python3 scripts/trip_planner.py draft --text "下周去上海见客户，两天"
```

系统应输出计划草稿，并明确说明：

- 这是计划草稿
- 不代表真实订票或订房
- 后续可用订单截图替换准确行程

用户确认后，才允许：

```bash
python3 scripts/trip_planner.py confirm --trip-id <id>
```

## 一句话模式示例

```text
高先生，我先按您的意思整理了一个上海出行草稿 ✈️

📍 目的地：上海
📅 时间：5月4日 - 5月5日
🎯 目的：见客户
📅 建议写入：商务计划

我先这样规划：

1. 🚄/✈️ 去程计划
   5月4日上午：北京 → 上海

2. 🤝 客户拜访
   5月4日下午：上海客户拜访

3. 🏨 住宿计划
   5月4日晚：上海住宿

4. 🚄/✈️ 返程计划
   5月5日下午：上海 → 北京

这些是计划草稿，还不是实际订单。
您确认后，我先写入 Apple Calendar，后面等您发机票/酒店订单截图，我再帮您替换成准确行程。
```

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
- 不订票。
- 不查价格。
- 不查实时航班。
- 不请求外部网络。
- 不覆盖旧日程。
- 不删除旧日程。
- 不读取微信 token。
- 不保存截图原图。

## 微信端测试话术

- `我发你几张订单截图，帮我整理成一次出行`
- `放到商务计划`
- `确认写入`
- `取消这次出行草稿`

## 微信端成功判断

- Trip 草稿中同时出现去程交通、酒店入住、返程交通。
- 在写入前，Hermes 明确展示统一 Trip 草稿。
- Hermes 明确追问并收到日历选择：`商务计划`、`个人计划` 或 `夫妻计划`。
- 用户确认后，Apple Calendar 中生成多条对应日程。
- 全流程不写 `飞行计划`。
- 全流程不写 Apple Reminders。
- 全流程不允许跳过确认直接写入。

## 回滚与清理

查看当前 Trip 草稿：

```bash
cat data/trip_drafts.json
```

取消某次 Trip 草稿：

```bash
python3 scripts/trip_flow.py cancel --trip-id <trip_id>
```

或：

```bash
python3 scripts/trip_aggregator.py cancel --trip-id <trip_id>
```

查看已写入去重记录：

```bash
cat data/trip_seen.json
```

删除测试日程的方法：

- 必须通过 Apple Calendar 手动删除，或走现有安全删除流程。
- 不要直接手改 `data/trip_seen.json` 来假装回滚。
