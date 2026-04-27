# 安全删除日程流程

Status: delete false-positive bugfix.

本流程修复微信端“删除游泳计划”这类请求可能被直接回复“已删除”但实际没有删除的问题。
根因是旧规则允许在确认后调用 `calendar_ops.py delete <calendar> <title> --yes`，而底层只按
精确标题删除第一条；当用户说“游泳计划”但真实标题是“游泳”时，如果没有先查询候选，就容易
出现误判或误报。

## 标准流程

用户要求删除日程时，先生成删除草稿：

```bash
python3 scripts/delete_event_flow.py draft --text "删除游泳计划"
```

脚本会：

- 从用户原文提取目标标题，去掉“删除/取消/计划/安排/日程”等口语尾词。
- 默认查找今天起未来 30 天内的可写日历。
- 如果用户说“今天/明天/后天”，只查对应日期。
- 在 `商务计划`、`家庭计划`、`个人计划`、`夫妻计划` 中查候选，不查也不写 `飞行计划`。
- 唯一匹配时写入 `data/pending_confirmations.json`，返回 `session_key` 和删除草稿。
- 多个候选时返回 `delete_event_ambiguous`，等待用户选择。
- 没有候选时返回 `delete_event_not_found`，不得回复已删除。

用户明确回复“确认删除”后：

```bash
python3 scripts/delete_event_flow.py confirm --session-key <session_key>
```

确认时不再按裸标题删除，而是调用 `calendar_ops.delete_event_exact_identity()`，按
`calendar + title + start + end` 精确身份删除。只有 confirm 返回 `ok=true` 后，才允许回复
删除成功。

## 微信端话术

第一轮：

```text
用户：删除游泳计划
助手：我先找到这条日程，删除前请您再确认一次……
```

第二轮：

```text
用户：确认删除
助手：好的，这个安排我已经替您取消了。
```

## 失败处理

- 没找到：说明没有找到匹配日程，建议用户补充日期或先查询今天行程。
- 多候选：列出候选标题、时间、日历，让用户选择一条。
- confirm 失败：只展示失败原因，不得说已删除。
- AppleScript 失败：返回底层错误，提示稍后重试或打开 Calendar 检查权限。

## 安全边界

- 删除前必须有草稿。
- 删除前必须有明确确认。
- 不删除 `飞行计划`。
- 不写 Apple Reminders。
- 不凭用户原话直接宣布成功。
