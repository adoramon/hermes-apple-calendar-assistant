# 一句话出差模式

Status: Phase 48 WeChat validation closure.

本阶段支持用户不先发订单截图，只用自然语言表达出差或旅行意图，由系统先生成本地
Trip planning draft，确认后再写入 Apple Calendar。

## 适用输入

- `下周去上海见客户，两天`
- `周五广州出差，当天回`
- `和太太下月去东京玩五天`
- `下周三去深圳拜访客户，住一晚`

## 处理流程

1. 先调用：

```bash
python3 scripts/travel_intent_parser.py parse "下周去上海见客户，两天"
```

2. 识别为出行意图后，再调用：

```bash
python3 scripts/trip_planner.py draft --text "下周去上海见客户，两天"
```

3. Hermes 展示计划草稿，并明确说明：
- 这是计划草稿
- 不代表真实订票或订房
- 后续可用订单截图替换准确行程

4. 用户确认后，才允许调用：

```bash
python3 scripts/trip_planner.py confirm --trip-id <trip_id>
```

## 微信端实测流程

标准测试话术：

- `下周去上海见客户，两天`
- `周五广州出差，当天回`
- `和太太下月去东京玩五天`

Hermes 预期行为：

1. 调用 `travel_intent_parser.py parse`。
2. 调用 `trip_planner.py draft`。
3. 展示计划草稿。
4. 明确说明这是“计划草稿”，不是实际订单。
5. 询问是否写入 `商务计划`、`个人计划` 或 `夫妻计划`。
6. 用户确认日历后，必要时调用 `trip_planner.py set-field`。
7. 用户确认后调用 `trip_planner.py confirm`。
8. 写入 Apple Calendar。

三轮微信测试：

1. 用户：`下周去上海见客户，两天`
   助手：展示草稿。
2. 用户：`放到商务计划`
   助手：更新草稿，继续等待确认。
3. 用户：`确认写入`
   助手：调用 `confirm`，写入 Apple Calendar。

预期日志关键字：

- `travel_intent_parser.py parse`
- `trip_planner.py draft`
- `trip_planner.py set-field`
- `trip_planner.py confirm`

成功判断标准：

- 用户一句话被识别为出行意图。
- 系统没有直接普通回答。
- 系统没有请求外网查航班/酒店。
- 系统没有直接写 Calendar。
- 写入前展示草稿。
- 确认后才写入 Apple Calendar。
- 事件标题带“计划”或“待确认”。
- notes 说明“由一句话出差模式生成，交通/酒店信息待订单确认”。
- 不写 `飞行计划`。
- 不写 Apple Reminders。

失败排查：

- 没进入 `trip_planner`：检查 `SKILL.md` 是否要求 `travel_intent_parser.py` 优先；检查 `gateway.log` 是否出现 parser 调用。
- 缺少日期：`trip_planner.py` 应追问具体日期或时间范围。
- 直接写入：属于严重错误，应修正 `SKILL.md`。
- 去查外网航班/酒店：属于错误，本阶段不允许请求外网。

## Parser 输出要点

`travel_intent_parser.py` 只做规则解析：

- 不调用大模型
- 不请求外部网络
- 不引入第三方依赖
- 默认 `origin_city` 为 `北京`
- 会在 `assumptions` 中写明默认项

支持识别：

- 日期：`下周`、`下月`、`本周`、`明天`、`后天`、`周五`、`下周三`
- 时长：`两天`、`三天`、`住一晚`、`当天回`、`五天`
- 商务意图：`见客户`、`拜访客户`、`开会`、`出差`
- 夫妻出行：`和太太`、`夫妻`、`两个人`
- 个人出行：`个人`、`自己`、`独自`

## Plan Draft 规则

默认规划规则：

1. 商务两天：
- 第一天上午去程
- 第一天下午客户拜访
- 第一晚住宿
- 第二天下午返程

2. 当天回：
- 上午去程
- 下午会议或拜访
- 傍晚返程
- 不生成 `hotel_placeholder`

3. 夫妻或旅行：
- 第一天上午出发
- 酒店入住
- 最后一天中午退房
- 下午返程

4. 如果缺字段：
- 不生成完整事件
- `display_message` 中主动追问缺失信息

## Confirm 写入规则

`trip_planner.py confirm` 只允许写入：

- 商务计划
- 个人计划
- 夫妻计划

写入时必须满足：

- 用户已明确确认
- 不写 `飞行计划`
- 不写 Apple Reminders
- 每条标题保留计划性质，例如：
  `去程计划｜北京 → 上海`
  `客户拜访计划｜上海`
  `住宿计划｜上海`
  `返程计划｜上海 → 北京`
- notes 中必须包含：
  `由一句话出差模式生成，交通/酒店信息待订单确认。`

## 与 Trip Aggregator 的关系

- 一句话出差模式先写计划草稿，不代表真实订单。
- 用户后续发送机票、酒店、高铁订单截图时，应转交 `travel_order_parser.py` +
  `trip_aggregator.py` + `trip_flow.py` 处理真实订单聚合。
- 真实酒店/高铁订单优先替换计划草稿中的 placeholder；必要时使用
  `trip_aggregator.py add --trip-id <id>` 显式合并到指定 Trip。
- 酒店日期与 Trip 日期不一致时标记 `date_conflict`，等待用户确认后再处理。
- 航班以 Apple Calendar `飞行计划` 为准，机票截图只作为匹配线索。
- 匹配成功后写入 `linked_flights`，并作为只读航班展示。
- confirm 时不创建航班日程，只写客户拜访、酒店、高铁等非航班事件。
- 本阶段不自动订票，不自动查酒店，不请求航班或价格数据。

## 安全边界

- 不订票
- 不查价格
- 不查实时航班
- 不请求外部网络
- 不直接写入
- 必须确认
- 不写 Apple Reminders
- 不写飞行计划
- 不覆盖已有真实订单行程

## 清理测试数据

查看 Trip 草稿：

```bash
cat data/trip_drafts.json
```

取消 trip draft：

```bash
python3 scripts/trip_planner.py cancel --trip-id <trip_id>
```

删除已写入的测试日程：

- 使用 Apple Calendar 手动删除。
- 或使用现有安全删除流程清理测试日程。
