# 微信端多 Trip 候选选择与合并实测

Status: Phase 51 WeChat validation closure.

本阶段不新增核心功能，只固化 Phase 50 后的微信端实测流程：当存在多个可合并 Trip
候选时，Hermes 必须先让用户选择目标 Trip，再使用 `trip_aggregator.py add --trip-id`
合并真实酒店/高铁订单。

## 标准微信测试流程

第一步，用户创建 Trip 草稿 A：

```text
用户：下周去上海见客户，两天
```

预期行为：

- 调用 `travel_intent_parser.py parse`。
- 调用 `trip_planner.py draft`。
- 生成 Trip 草稿 A。
- 展示“计划草稿”，说明不是实际订单。

第二步，用户创建 Trip 草稿 B：

```text
用户：下周去上海参加展会，三天
```

预期行为：

- 再次调用 `travel_intent_parser.py parse`。
- 调用 `trip_planner.py draft`。
- 生成 Trip 草稿 B。
- 不覆盖 Trip 草稿 A。

第三步，用户发送酒店订单截图或文字。

预期行为：

- Hermes 先从截图提取 OCR 文本。
- 调用 `travel_order_parser.py parse`，识别为 `hotel`。
- 检测到多个 Trip 候选。
- 不直接合并，不新建重复 Trip。
- 列出候选并询问用户合并到哪个 Trip。

候选展示示例：

```text
高先生，我找到两个可能相关的上海出行草稿：

1. 上海商务出行｜5月1日-5月3日
2. 上海展会行程｜5月2日-5月5日

这张酒店订单要合并到哪一个？
```

第四步，用户选择目标 Trip：

```text
用户：合并到第一个
```

预期行为：

- 根据用户选择取第一个候选的 `trip_id`。
- 调用：

```bash
python3 scripts/trip_aggregator.py add --trip-id <id> --text "<酒店订单文字>"
```

- 如果日期匹配，替换 `hotel_placeholder`。
- 写入 `merge_history`。
- 调用 `trip_flow.py draft --trip-id <id>` 展示合并后的 Trip 草稿。
- 写入 Calendar 前仍等待用户 confirm。

## 高铁订单替换流程

用户发送高铁订单后：

- 先调用 `travel_order_parser.py parse`，识别为 `train`。
- 如果存在多个候选 Trip，先让用户选择目标 Trip。
- 用户选择后调用 `trip_aggregator.py add --trip-id <id>`。

替换规则：

- `origin_city → destination_city`：替换 `outbound_placeholder`。
- `destination_city → origin_city`：替换 `return_placeholder`。
- 不替换 `meeting_placeholder`。

展示要求：

- 明确说明真实高铁订单已替换去程或返程计划占位。
- 不保留旧 placeholder 造成重复待写入事件。
- 仍需 `trip_flow.py draft` 展示草稿，用户确认后才写入 Apple Calendar。

## 航班订单处理规则

如果用户发送机票截图：

- 调用 `travel_order_parser.py parse`，识别航班信息。
- 不创建航班日程。
- 不写 `商务计划`、`个人计划` 或 `夫妻计划`。
- 尝试从 Apple Calendar 的「飞行计划」匹配。
- 匹配成功：关联到 Trip 的 `linked_flights`。
- 匹配失败：提示等待航旅纵横同步。

可使用：

```bash
python3 scripts/trip_flight_matcher.py match --trip-id <id> --days 30
```

必要时先诊断飞行计划读取链路：

```bash
python3 scripts/flight_plan_reader.py diagnose --days 30
```

## 日期冲突处理

如果酒店订单日期与 Trip 日期不一致：

- 标记 `confirmation_status=date_conflict`。
- 不自动替换 `hotel_placeholder`。
- 不直接写入 Calendar。
- 追问用户：

```text
这家酒店日期和原出行计划不完全一致，要按酒店订单日期调整 Trip，还是保持原计划？
```

存在 `date_conflict` 时，`trip_flow.py confirm` 不应继续写入；必须先处理冲突。

## 预期日志关键字

- `travel_order_parser.py parse`
- `trip_aggregator.py add`
- `trip_aggregator.py add --trip-id`
- `trip_flow.py draft`
- `flight_plan_reader.py diagnose`
- `trip_flight_matcher.py match`

## 成功判断标准

- 多候选时不乱合并。
- 用户选择后使用 `--trip-id`。
- 真实酒店订单替换 `hotel_placeholder`。
- 真实高铁订单替换去程或返程 placeholder。
- 航班不重复创建。
- 写入前仍需要 confirm。
- 不写 `飞行计划`。
- 不写 Apple Reminders。

## 失败排查

### A. 没列出候选 Trip

- 检查 `python3 scripts/trip_aggregator.py list`。
- 检查候选 Trip 的 `destination_city`。
- 检查候选 Trip 的 `start_date` / `end_date`。

### B. 合并到错误 Trip

- 检查是否使用 `trip_aggregator.py add --trip-id <id>`。
- 检查 `SKILL.md` 是否要求多候选时先让用户选择。
- 检查用户选择序号与实际 `trip_id` 映射。

### C. 酒店 placeholder 没被替换

- 检查订单 `source_type` 是否为 `hotel_order`。
- 检查 `confirmation_status` 是否为 `confirmed` 或 `date_conflict`。
- 检查 Trip 的 `merge_history` 是否记录 `replace_placeholder`。

### D. 机票被写入普通日历

- 严重错误，必须回滚。
- 重新执行 Phase 49 规则：航班只从「飞行计划」读取/关联。
- 检查 `trip_flow.py confirm` 是否排除了航班和 `linked_flights`。

## 安全边界

- 不写 `飞行计划`。
- 不创建航班事件。
- 不请求外部网络。
- 不自动订票。
- 不跳过确认。
- 不写 Apple Reminders。
