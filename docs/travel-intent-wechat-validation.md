# 一句话出差模式微信端实测收口

Status: Phase 48.

本文档只固化微信端实测流程、日志关键字和失败排查，不新增核心功能。

## 标准测试话术

- `下周去上海见客户，两天`
- `周五广州出差，当天回`
- `和太太下月去东京玩五天`

## Hermes 预期行为

1. 调用：

```bash
python3 scripts/travel_intent_parser.py parse "<用户原文>"
```

2. 调用：

```bash
python3 scripts/trip_planner.py draft --text "<用户原文>"
```

3. 展示计划草稿。
4. 明确说明这是“计划草稿”，不是实际订单。
5. 询问是否写入：
- 商务计划
- 个人计划
- 夫妻计划

6. 用户选择日历后，必要时调用：

```bash
python3 scripts/trip_planner.py set-field --trip-id <trip_id> --field calendar --value "商务计划"
```

7. 用户确认后调用：

```bash
python3 scripts/trip_planner.py confirm --trip-id <trip_id>
```

8. 写入 Apple Calendar。

## 预期日志关键字

- `travel_intent_parser.py parse`
- `trip_planner.py draft`
- `trip_planner.py set-field`
- `trip_planner.py confirm`

排查时优先检查：

```text
~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log
```

## 成功判断标准

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

## 失败排查

### A. 没进入 trip_planner

- 检查 `SKILL.md` 是否要求 `travel_intent_parser.py` 优先。
- 检查 `gateway.log` 是否出现 parser 调用。

### B. 缺少日期

- `trip_planner.py` 应追问具体日期或时间范围。
- 不要自行猜测完整时间后直接写入。

### C. 直接写入

- 属于严重错误，应修正 `SKILL.md`。
- 所有一句话出差模式写入前必须先展示草稿，并等待用户确认。

### D. 去查外网航班/酒店

- 属于错误，本阶段不允许请求外网。
- 不查实时航班。
- 不查酒店库存。
- 不查价格。

## 微信端三轮测试流程

第一轮：

```text
用户：下周去上海见客户，两天
助手：展示计划草稿。
```

第二轮：

```text
用户：放到商务计划
助手：更新草稿，继续等待确认。
```

第三轮：

```text
用户：确认写入
助手：调用 confirm，写入 Apple Calendar。
```

## 清理测试数据

查看 `trip_drafts.json`：

```bash
cat data/trip_drafts.json
```

取消 trip draft：

```bash
python3 scripts/trip_planner.py cancel --trip-id <trip_id>
```

清理测试日程：

- 使用 Apple Calendar 手动删除。
- 或使用现有安全删除流程清理测试日程。
