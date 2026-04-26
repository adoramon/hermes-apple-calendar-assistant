# Hotel Order Flow

当前状态：`Phase 43 酒店订单识别与行程写入`。

本流程用于处理用户在微信中复制酒店订单文字，或截图经 Hermes/OCR 提取后的订单文
字。仓库本身不实现 OCR，不请求外部网络，不读取微信 token。

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

如果没有文字内容，应提示用户：

```text
我需要先看到订单里的文字信息，您可以把截图里的订单文字复制给我，或者让我读取截图文字后再整理。
```

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

## 确认写入

```bash
python3 scripts/hotel_order_flow.py confirm --session-key <key>
```

confirm 会读取 pending draft，确认 `calendar` 与 `checkin_time` 已存在后调用
现有 Apple Calendar 创建逻辑。写入前不会创建提醒事项，不操作 Apple Reminders。

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
