# Hotel Order Image Detection

当前状态：`Phase 44 酒店订单截图微信实测文档收口`。

本项目不直接实现 OCR。酒店订单截图的识别入口由 Hermes / 多模态模型负责：先从
图片中提取文字，再把提取出的文字交给本 Skill 的酒店订单流程。

## 处理链路

```text
用户发送酒店订单截图
  -> Hermes / 多模态模型读取截图文字
  -> 判断文字是否疑似酒店订单
  -> hotel_order_flow.py draft --text "<截图中提取出的订单文字>"
  -> 生成待确认入住行程草稿
  -> 继续追问缺失字段
  -> hotel_order_flow.py update-draft --session-key <key> ...
  -> 用户确认后才写入 Apple Calendar
```

微信端验收时，Hermes 不应只回复订单摘要，也不应询问“是否备注到航班行程”。疑似
酒店订单必须进入 `hotel_order_flow.py draft`。

## 酒店订单线索

图片文字中包含以下信息时，应视为酒店订单候选：

- 酒店 / 宾馆 / 民宿 / 公寓 / 入住 / 离店 / 入住人
- 订单号 / 确认号 / 预订号
- 房型 / 间夜 / 到店 / 离店
- 携程 / 飞猪 / 美团 / Booking / Agoda / Airbnb / Trip.com

Hermes 不需要用户再说明“这是酒店订单”。只要截图文字疑似酒店订单，就应自动进入
`hotel_order_flow.py draft`。

## 自动草稿命令

```bash
python3 scripts/hotel_order_flow.py draft --text "<截图中提取出的订单文字>"
```

如果 `hotel_order_flow.py` 返回酒店订单草稿，应展示 `data.display_message`。

如果缺少字段，必须继续追问：

- 缺少 `calendar`：询问写入 `个人计划` 还是 `夫妻计划`
- 缺少 `checkin_time`：询问入住当天几点记录，例如 `15:00`

用户补充字段后：

```bash
python3 scripts/hotel_order_flow.py update-draft \
  --session-key <key> \
  --calendar "个人计划" \
  --checkin-time "23:30"
```

用户明确确认后：

```bash
python3 scripts/hotel_order_flow.py confirm --session-key <key>
```

预期日志关键字：

- `hotel_order_flow.py draft`
- `hotel_order_flow.py update-draft`
- `hotel_order_flow.py confirm`

## 用户回复示例

```text
高先生，我看这张截图像是一条酒店订单，我先帮您整理成入住行程草稿了 🏨

🏨 酒店：上海外滩悦榕庄
📍 地址：上海市虹口区海平路 19 号
🛏️ 入住：2026-05-01
🚪 离店：2026-05-03

写入日历前，我还需要您确认两件事：
1. 写入「个人计划」还是「夫妻计划」？
2. 入住当天几点记录比较合适？例如 15:00。
```

如果图片无法识别文字：

```text
高先生，这张截图我暂时没读清订单文字。您可以把酒店订单里的文字复制给我，我来帮您整理入住行程。
```

## 验证场景

1. 用户发送酒店订单截图 -> 自动识别 -> 进入酒店行程草稿。
2. 用户发送非酒店截图 -> 不进入酒店订单流程。
3. 用户发送酒店截图但缺入住时间 -> 追问入住时间。
4. 用户发送酒店截图但缺日历选择 -> 追问 `个人计划` / `夫妻计划`。
5. 用户回复“创建日程”但未选日历 -> 继续追问日历，不默认 `个人计划`。
6. 用户回复“确认”且草稿完整 -> 调用 `hotel_order_flow.py confirm` 写入
   Apple Calendar。

## 失败排查

图片文字识别失败：

- 日志中通常只有 vision/image analysis，没有可用订单文字。
- 应提示用户复制订单文字，或重新发送更清晰截图。

未进入 `hotel_order_flow`：

- 日志中没有 `hotel_order_flow.py draft`。
- 常见错误表现：只总结订单、询问是否写入航班备注、或调用
  `interactive_create.py create-draft`。

缺少入住时间：

- `hotel_order_flow.py draft` 返回 `missing_fields=["checkin_time", ...]`。
- 应追问具体时间，例如 `23:30`，再调用 `update-draft`。

缺少日历选择：

- `hotel_order_flow.py draft` 返回 `missing_fields=["calendar", ...]`。
- 应追问 `个人计划` / `夫妻计划`，不得写 `商务计划`、`家庭计划` 或 `飞行计划`。

## 安全边界

- Skill 不实现 OCR。
- Skill 只接收 Hermes / 多模态模型提取后的文字。
- 不引入第三方 OCR 依赖。
- 不请求外部网络。
- 不直接写 Calendar。
- 用户确认后才写入 Apple Calendar。
- 不写 `商务计划`、`家庭计划`、`飞行计划`。
- 不写 Apple Reminders。
- 不创建提醒事项。
