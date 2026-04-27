# 计划 Trip 与飞行计划自动合并

Status: Phase 50.

本阶段把一句话计划 Trip、酒店/高铁订单和 Apple Calendar 的「飞行计划」只读航班
合并在一起。航班仍由航旅纵横统一管理，本项目只读取和关联，不创建航班日程。

## 业务规则

- 用户机票不由本 Skill 创建。
- 航班最终由航旅纵横自动写入 Apple Calendar 的「飞行计划」日历。
- 本项目不得把机票订单重复写入 `商务计划`、`个人计划` 或 `夫妻计划`。
- 本项目不得创建航班日程。
- 本项目不得修改「飞行计划」中的航班事件，除了已有 `flight_auto_enhancer.py` 的 location 增强能力。
- Trip 聚合时，航班信息优先从「飞行计划」读取。
- 用户发送机票截图时，只能用于辅助匹配 Trip，不得创建航班日程。
- 酒店、高铁、客户拜访等仍可写入 `商务计划`、`个人计划` 或 `夫妻计划`。

## 读取飞行计划

只读读取未来航班：

```bash
python3 scripts/flight_plan_reader.py list --days 30
```

输出中的航班来自 `飞行计划`，字段包括：

- `flight_no`
- `departure_city`
- `arrival_city`
- `departure_airport`
- `arrival_airport`
- `departure_terminal`
- `arrival_terminal`
- `source`

本命令不写 Calendar、不创建事件、不修改「飞行计划」。

诊断读取链路：

```bash
python3 scripts/flight_plan_reader.py diagnose --days 30
```

诊断输出区分：

- `calendar_found`
- `permission_ok`
- `apple_script_ok`
- `event_count`
- `parse_success_count`
- `parse_failed_count`
- `errors`

如果 AppleScript 查询失败，`diagnose` 会把错误放入 `errors` 和顶层 `error`，不会静默
吞掉；`list` 仍可在运行环境受限时 fallback 到 `data/flight_seen.json` 做只读辅助。

## 匹配 Trip

把「飞行计划」航班关联到已有 Trip：

```bash
python3 scripts/trip_flight_matcher.py match --trip-id <trip_id> --days 30
```

去程匹配规则：

- `flight.arrival_city == trip.destination_city`
- `flight.departure_city == trip.origin_city`
- 航班日期接近 `trip.start_date`，允许前后 1 天

返程匹配规则：

- `flight.departure_city == trip.destination_city`
- `flight.arrival_city == trip.origin_city`
- 航班日期接近 `trip.end_date`，允许前后 1 天

无法唯一确定时，返回候选航班列表，不自动合并。

## Trip 字段

匹配成功后，Trip 草稿增加：

```json
{
  "linked_flights": {
    "outbound": {
      "source_calendar": "飞行计划",
      "title": "...",
      "start": "...",
      "end": "...",
      "location": "...",
      "flight_no": "...",
      "readonly": true
    },
    "return": {}
  }
}
```

状态字段：

- `flight_link_status`: `no_flight_needed`、`flight_pending_sync`、`outbound_linked`、`return_linked`、`fully_linked`
- `planning_status`: `planned_only`、`partially_confirmed`、`fully_confirmed`

## 机票截图规则

如果用户发送机票截图或机票订单文字：

1. `travel_order_parser.py` 可以识别为 `flight`。
2. `trip_aggregator.py add` 只把它作为 `flight_order_hints`。
3. 系统尝试从「飞行计划」匹配对应航班。
4. 匹配成功则写入 `linked_flights`。
5. 匹配失败则提示：

```text
我没有在飞行计划中找到这趟航班。等航旅纵横同步后，我再帮您合并。
```

机票截图不得产生待创建航班事件。

## 与真实订单替换的关系

Phase 50 起，酒店和高铁真实订单会优先替换一句话计划 Trip 中的 placeholder：

- 酒店订单替换 `hotel_placeholder`。
- 高铁去程替换 `outbound_placeholder`。
- 高铁返程替换 `return_placeholder`。
- 机票订单仍只用于匹配 `飞行计划`，不替换为待创建事件。

如需指定候选 Trip：

```bash
python3 scripts/trip_aggregator.py add --trip-id <trip_id> --text "<订单文字>"
```

详见 `docs/trip-plan-order-merge.md`。

## Draft 展示

`trip_flow.py draft` 会把 `linked_flights` 展示为“已从飞行计划读取”，并把它们排除在
待写入事件之外。

待写入 Apple Calendar 的只包括：

- 酒店订单
- 高铁订单
- 客户拜访计划
- 其他非航班计划

## Confirm 写入

`trip_flow.py confirm`：

- 不创建 `linked_flights`
- 不创建机票订单对应事件
- 不创建去程/返程航班占位
- 只创建酒店、高铁、客户拜访等非航班事件
- notes 中引用只读航班信息
- `trip_seen.json` 只记录实际创建的非航班事件
- 不写 `飞行计划`

## 安全边界

- 不创建航班日程
- 不写飞行计划
- 不修改飞行计划
- 不删除飞行计划
- 不重复写航班
- 不读微信 token
- 不请求外部网络
- 不自动订票
- 不跳过确认
