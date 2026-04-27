# 真实订单替换 Trip 计划占位

Status: Phase 51 WeChat validation closure.

本阶段用于收口一句话出差模式之后的真实订单合并：用户先说“下周去上海见客户，两天”
生成计划 Trip，后续再发送真实酒店或高铁订单时，系统应优先替换已有计划占位，而不是
追加重复日程。

## 替换目标

计划 Trip 中可能存在这些占位：

- `outbound_placeholder`：去程计划
- `hotel_placeholder`：住宿计划
- `meeting_placeholder`：客户拜访计划
- `return_placeholder`：返程计划

真实订单只替换对应类型：

- 酒店订单替换 `hotel_placeholder`。
- 高铁订单按路线替换 `outbound_placeholder` 或 `return_placeholder`。
- 高铁订单不得替换 `meeting_placeholder`。
- 机票订单不创建、不替换待写入事件，只尝试关联 Apple Calendar `飞行计划`。

## 显式指定 Trip

当候选 Trip 不唯一，Hermes 应询问用户选择，并使用显式 `trip_id` 合并：

```bash
python3 scripts/trip_aggregator.py add \
  --trip-id <trip_id> \
  --text "<酒店或高铁订单文字>"
```

如果 `trip_id` 不存在，返回 `ok=false`。如果订单与 Trip 目的地或日期明显不一致，
返回 `warning` 和 `needs_confirmation=true`，不得自动创建新 Trip。

微信端多候选时必须先列出候选，例如：

```text
1. 上海商务出行｜5月1日-5月3日
2. 上海展会行程｜5月2日-5月5日
```

用户回复“合并到第一个”后，才把第一个候选映射为 `trip_id` 并调用
`trip_aggregator.py add --trip-id <id>`。多候选未确认前，不得自动选择最近更新 Trip，
也不得新建重复 Trip。

## 字段约定

placeholder 和真实订单会标记：

- `source_type`: `travel_intent`、`hotel_order`、`train_order`、`flight_plan`、`manual`
- `confirmation_status`: `planned`、`confirmed`、`linked_readonly`、`date_conflict`
- `replaced_placeholder_id`: 被替换的占位 ID，未替换时为 `null`

Trip 增加 `merge_history`，每次替换记录：

```json
{
  "at": "ISO时间",
  "action": "replace_placeholder",
  "placeholder_type": "hotel_placeholder",
  "new_source_type": "hotel_order",
  "summary": "酒店订单替换住宿占位：上海外滩悦榕庄"
}
```

## 日期冲突

酒店真实入住/离店日期如果与 Trip 起止日期不一致，系统不得直接覆盖 `hotel_placeholder`。
此时订单标记为 `confirmation_status=date_conflict`，`trip_flow.py draft` 展示为
“日期冲突待确认”，等待用户确认是否属于同一次出行。

存在 `date_conflict` 时，`trip_flow.py confirm` 不应继续写入 Calendar；必须先处理
冲突，避免把错误的计划占位或真实订单写进日历。

微信端追问建议：

```text
这家酒店日期和原出行计划不完全一致，要按酒店订单日期调整 Trip，还是保持原计划？
```

高铁真实路线如果无法判断是去程或返程，也不得替换去程/返程占位；应返回 warning，
让用户确认。

## Draft 展示

`trip_flow.py draft` 应区分：

- ✅ 已确认订单
- ⏳ 计划占位
- 🔗 飞行计划只读关联
- ⚠️ 日期冲突待确认

示例：

```text
高先生，我已经把酒店订单替换进这次上海出行了 🏨

✅ 酒店：上海外滩悦榕庄
🛏️ 入住：5月1日 15:00
🚪 离店：5月3日 12:00

原来的“住宿计划｜上海”已被替换，不会重复写入。
```

## 安全边界

- 不写 `飞行计划`
- 不创建航班事件
- 不删除旧日程
- 不覆盖真实确认事件
- 不跳过确认
- 不请求外部网络
- 不写 Apple Reminders
