# 微信端一句话查询行程

Status: Phase 54.

本阶段新增即时秘书模式：用户在微信里自然语言询问日程、会议、行程或出差安排时，
Hermes 应优先调用 `schedule_query_router.py`，返回秘书式摘要，而不是直接闲聊回答。

## 支持话术

今天：

- 我今天什么安排
- 今天还有什么会
- 今天几点出门

明天：

- 我明天什么安排
- 明天出差安排
- 明天几点第一场会

未来：

- 下周上海出差怎么样
- 我什么时候去广州
- 这个月还有哪些出差
- 本周行程总结

## 手动查询

```bash
python3 scripts/schedule_query_router.py query --text "我明天什么安排"
python3 scripts/schedule_query_router.py query --text "下周上海出差怎么样"
python3 scripts/schedule_query_router.py query --text "今天还有几个会"
```

输出统一 JSON：

```json
{
  "ok": true,
  "data": {
    "query_type": "tomorrow_schedule",
    "summary": "...",
    "items": []
  },
  "error": null
}
```

## 路由规则

- 普通单日日程：查询 Calendar.app 的 `read_calendars`。
- 时间范围查询：按本周、下周、本月查询 Calendar.app。
- Trip 查询：读取 `data/trip_drafts.json`。
- 城市出行查询：按 `destination_city` 匹配 Trip，并结合 Calendar 查询结果。

如果 Calendar 某个日历读取失败，结果中会保留 `errors`，摘要会说明“有部分日历暂时没读成功”，
不得把失败误报成“没有安排”。

## 微信端行为

当用户消息包含：

- 安排
- 行程
- 出差
- 会议
- 什么时候去
- 还有几个会

Hermes 应优先调用：

```bash
python3 scripts/schedule_query_router.py query --text "<用户原文>"
```

返回给用户时使用 `data.summary`。

## 安全边界

- 只读查询。
- 不创建 Calendar。
- 不修改 Calendar。
- 不删除 Calendar。
- 不请求外网。
- 不读取微信 token。
- 不写 Apple Reminders。
