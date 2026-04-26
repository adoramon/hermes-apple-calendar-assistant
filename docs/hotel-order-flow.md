# Hotel Order Flow

当前状态：`Phase 44 酒店订单截图微信实测文档收口`。

本流程用于处理用户在微信中复制酒店订单文字，或截图经 Hermes/OCR 提取后的订单文
字。仓库本身不实现 OCR，不请求外部网络，不读取微信 token。

截图自动识别入口见：[`docs/hotel-order-image-detection.md`](hotel-order-image-detection.md)。

## 识别

```bash
python3 scripts/hotel_order_parser.py parse --text "<订单文字>"
```

解析字段：

- 酒店名称
- 酒店地址
- 入住日期
- 离店日期
- 入住时间
- 离店时间
- 入住人
- 房型
- 订单号 / 确认号
- 平台来源，例如携程、美团、飞猪、Booking、Agoda、Airbnb

如果不是酒店订单，返回 `is_hotel_order=false`。如果无法确定写入日历或入住时间，
`missing_fields` 必须包含 `calendar` / `checkin_time`。

## 截图规则

本项目不直接实现 OCR。如果 Hermes 已经从截图提取出文字，应将提取后的文字传给
`hotel_order_parser.py` 或 `hotel_order_flow.py`。

当用户发送图片/截图时，Hermes 应先提取图片中文字。如果文字中包含酒店、宾馆、
民宿、公寓、入住、离店、订单号、确认号、房型、携程、飞猪、美团、Booking、Agoda、
Airbnb、Trip.com 等线索，应自动进入：

```bash
python3 scripts/hotel_order_flow.py draft --text "<截图中提取出的订单文字>"
```

不需要用户再说明“这是酒店订单”。不要只总结订单内容，应进入日程草稿流程。

如果没有文字内容，应提示用户：

```text
高先生，这张截图我暂时没读清订单文字。您可以把酒店订单里的文字复制给我，我来帮您整理入住行程。
```

## 微信端实测流程

Phase 44 记录的微信端验收链路如下：

```text
微信发送酒店订单截图
  -> Hermes / 多模态模型提取图片文字
  -> 自动调用 hotel_order_flow.py draft
  -> 如果缺少日历，追问 个人计划 / 夫妻计划
  -> 如果缺少入住时间，追问具体 HH:MM 入住时间
  -> 用户补充字段后调用 hotel_order_flow.py update-draft
  -> 用户确认后调用 hotel_order_flow.py confirm
  -> 写入 Apple Calendar
```

预期日志中应能看到这些关键字：

- `hotel_order_flow.py draft`
- `hotel_order_flow.py update-draft`
- `hotel_order_flow.py confirm`

如果只看到 `interactive_create.py create-draft`，说明错误地走了普通日程创建流程，
不是酒店订单专用流程。

## 生成草稿

```bash
python3 scripts/hotel_order_flow.py draft --text "<订单文字>"
```

行为：

- 调用规则解析器。
- 判断是否为酒店订单。
- 生成待补充/待确认草稿。
- 写入 `data/pending_confirmations.json`。
- 不直接写 Apple Calendar。

允许写入的日历只有：

- `个人计划`
- `夫妻计划`

如果缺少 calendar，提示：

```text
这条酒店行程您想写入个人计划还是夫妻计划？
```

如果缺少 checkin_time，提示：

```text
入住当天您希望几点开始提醒/记录？例如 15:00。
```

## 补充信息

```bash
python3 scripts/hotel_order_flow.py update-draft \
  --session-key <key> \
  --calendar "夫妻计划" \
  --checkin-time "15:00"
```

规则：

- `calendar` 只允许 `个人计划` / `夫妻计划`。
- `checkin-time` 必须是合法 `HH:MM`。
- 更新 pending draft。
- 返回待确认草稿。

微信中用户只说“创建日程”“同步到日历”时，如果草稿仍缺少 `calendar`，不能默认
写入 `个人计划`，必须继续追问：

```text
高先生，这条酒店行程我给您放到「个人计划」还是「夫妻计划」呀？
```

如果草稿仍缺少 `checkin_time`，必须继续追问具体入住时间，不要自行猜测。

## 确认写入

```bash
python3 scripts/hotel_order_flow.py confirm --session-key <key>
```

confirm 会读取 pending draft，确认 `calendar` 与 `checkin_time` 已存在后调用
现有 Apple Calendar 创建逻辑。写入前不会创建提醒事项，不操作 Apple Reminders。

确认前如果缺少 `calendar` 或 `checkin_time`，`confirm` 应失败或拒绝执行。Hermes
应把缺失字段继续问清楚，不得绕过确认。

## 取消

```bash
python3 scripts/hotel_order_flow.py cancel --session-key <key>
```

## 日程映射

- `title`：`入住｜{hotel_name}`
- `calendar`：用户确认后的 `个人计划` 或 `夫妻计划`
- `start`：`checkin_date + checkin_time`
- `end`：`checkout_date + checkout_time`
- 如果 `checkout_time` 缺失，默认 `12:00`，并写入 `assumptions`
- `location`：酒店地址
- `notes`：酒店名称、入住/离店日期、入住人、房型、订单号、平台来源

## 安全边界

- 不直接写入日历。
- 用户确认后才写入 Apple Calendar。
- 不写 `飞行计划`。
- 不写 `商务计划` / `家庭计划`。
- 不创建提醒事项。
- 不操作 Apple Reminders。
- 不请求外部网络。
- 不引入第三方依赖。

## 失败排查

图片文字识别失败：

- 表现：Hermes 无法提取酒店、入住、离店、地址等文字。
- 处理：提示用户复制订单文字，或重新发送清晰截图。

未进入 `hotel_order_flow`：

- 表现：回复只总结截图，或询问“是否备注到航班行程”，或直接生成普通
  `interactive_create.py` 草稿。
- 处理：检查 `~/.hermes/profiles/sunny-wechat-lite/logs/agent.log` 是否出现
  `hotel_order_flow.py draft`。

缺少入住时间：

- 表现：`missing_fields` 包含 `checkin_time`。
- 处理：追问用户入住当天几点记录，例如 `23:30`，再调用 `update-draft`。

缺少日历选择：

- 表现：`missing_fields` 包含 `calendar`。
- 处理：追问 `个人计划` / `夫妻计划`，不得默认 `个人计划`。
