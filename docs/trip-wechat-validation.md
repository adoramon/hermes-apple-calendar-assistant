# 微信端 Trip 聚合实测收口

Status: Phase 46.

本文档只收口微信端实测流程、日志关键字和失败排查，不新增任何核心功能。

## 标准测试流程

用户连续发送：

- 机票订单截图
- 酒店订单截图
- 高铁/返程订单截图

Hermes 端预期行为：

1. 从每张截图提取文字。
2. 对每段订单文字调用：

```bash
python3 scripts/travel_order_parser.py parse --text "<订单文字>"
```

3. 对可识别的出行订单继续调用：

```bash
python3 scripts/trip_aggregator.py add --text "<订单文字>"
```

4. 聚合后调用：

```bash
python3 scripts/trip_flow.py draft --trip-id <trip_id>
```

5. 展示统一 Trip 草稿。
6. 询问写入哪个日历：
- 商务计划
- 个人计划
- 夫妻计划

7. 用户明确选择后调用：

```bash
python3 scripts/trip_flow.py set-calendar --trip-id <trip_id> --calendar "商务计划"
```

8. 用户明确确认后调用：

```bash
python3 scripts/trip_flow.py confirm --trip-id <trip_id>
```

9. 一次性写入 Apple Calendar。

## 预期日志关键字

- `travel_order_parser.py parse`
- `trip_aggregator.py add`
- `trip_flow.py draft`
- `trip_flow.py set-calendar`
- `trip_flow.py confirm`

排查时优先检查 `~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log`，确认以上关键字是否按顺序出现。

## 成功判断标准

- Trip 中包含去程交通、酒店入住、返程交通。
- 日历选择被明确确认。
- 写入前有草稿。
- 确认后 Apple Calendar 出现多条日程。
- 不写 `飞行计划`。
- 不写 Apple Reminders。
- 不直接跳过确认。

## 失败排查

### A. 截图未识别

- 检查 Hermes 是否提取出 OCR 文本。
- 如果没有提取到可用文字，让用户复制订单文字重试。

### B. 没进入 Trip 流程

- 检查 `SKILL.md` 是否要求优先 `travel_order_parser.py`。
- 检查 `gateway.log` 是否有 parser 调用。

### C. 三张订单没有聚合到同一 Trip

- 检查 `destination_city` 是否一致。
- 检查日期是否相差超过 3 天。
- 检查：

```bash
python3 scripts/trip_aggregator.py list
```

### D. 没追问日历

- 检查 `trip_flow.py draft` 的 `missing_fields` 是否包含 `calendar`。

### E. 直接写入

- 属于严重错误，必须修正 `SKILL.md`。
- 所有写入前必须 `confirm`。

## 微信端测试话术

- `我发你几张订单截图，帮我整理成一次出行`
- `放到商务计划`
- `确认写入`
- `取消这次出行草稿`

## 回滚与清理

查看 Trip 草稿文件：

```bash
cat data/trip_drafts.json
```

取消 Trip draft：

```bash
python3 scripts/trip_flow.py cancel --trip-id <trip_id>
```

或：

```bash
python3 scripts/trip_aggregator.py cancel --trip-id <trip_id>
```

查看去重记录：

```bash
cat data/trip_seen.json
```

删除测试日程：

- 必须通过 Apple Calendar 手动删除。
- 或通过现有安全删除流程处理。
- 不要通过直接改 `data/trip_seen.json` 代替删除真实日程。
