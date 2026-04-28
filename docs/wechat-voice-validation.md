# 微信语音秘书实测收口

本文档固化 Phase 56 微信语音秘书模式的实测流程、日志关键字和失败排查。

## 标准测试流程

### 语音测试 1：查询明天安排

用户在微信发送语音：

```text
我明天什么安排
```

预期行为：

- Hermes gateway 完成语音转文字。
- 转写文本命中“安排”查询意图。
- Hermes 调用：

```bash
python3 scripts/schedule_query_router.py query --text "我明天什么安排"
```

- 返回秘书式文字回复。
- 根据 `voice_mode` 决定是否附带女声 TTS 语音回复。

### 语音测试 2：推迟下午会议

用户在微信发送语音：

```text
帮我把下午会议推迟半小时
```

预期行为：

- Hermes gateway 完成语音转文字。
- 转写文本命中“会议 / 推迟”操作意图。
- Hermes 进入 `reminder_action_flow.py` 或日程修改草稿流程。
- 生成待确认草稿。
- 不直接修改 Calendar。
- 等待用户明确确认后才执行。

推荐优先调用：

```bash
python3 scripts/reminder_action_flow.py draft --text "帮我把下午会议推迟半小时"
```

如果没有最近提醒上下文，应进入普通日程修改候选选择流程，不得直接改日程。

### 语音测试 3：查询 Trip 摘要

用户在微信发送语音：

```text
下周上海出差怎么样
```

预期行为：

- Hermes gateway 完成语音转文字。
- 转写文本命中“出差”或城市 Trip 查询意图。
- Hermes 调用 `schedule_query_router.py` 或 `trip_flow.py`。
- 返回 Trip 摘要，包括去程、酒店、会议、返程、待确认事项等可用信息。

推荐调用：

```bash
python3 scripts/schedule_query_router.py query --text "下周上海出差怎么样"
```

必要时可继续调用：

```bash
python3 scripts/trip_flow.py draft --trip-id "<trip_id>"
```

## voice_mode

- `off`：仅文字回复，不附带 TTS；当前封板默认模式。
- `smart`：仅当用户明确要求“语音回复”“读给我听”“用语音说”时附带 TTS 音频附件。
- `always`：当前微信 iLink 通道不建议启用，避免无意义音频附件。

切换测试：

- `关闭语音回复`：应切换或建议切换到 `voice_mode=off`。
- `打开语音回复`：应切换或建议切换到 `voice_mode=smart`。
- `开车模式`：应按文字回复处理，不追加语音附件。

## 预期日志关键字

检查 Hermes profile 日志时，重点搜索：

- `voice`
- `ASR`
- `TTS`
- `schedule_query_router.py`
- `reminder_action_flow.py`
- `trip_flow.py`

常用日志位置：

```bash
~/.hermes/profiles/sunny-wechat-lite/logs/gateway.log
~/.hermes/profiles/sunny-wechat-lite/logs/gateway.error.log
~/.hermes/profiles/sunny-wechat-lite/logs/agent.log
```

## 测试话术

- `我明天什么安排`
- `今天几点出门`
- `帮我把下午会议推迟半小时`
- `取消今晚晚餐`
- `下周上海出差怎么样`
- `关闭语音回复`
- `打开语音回复`

## 成功判断标准

- 语音消息能被 Hermes 转写为文字。
- 秘书事务类语音不会被当作普通闲聊。
- 查询类语音进入 `schedule_query_router.py query`。
- 推迟/取消/修改类语音先生成草稿，不直接修改 Calendar。
- Trip 查询类语音返回 Trip 摘要。
- `voice_mode` 能控制是否附带 TTS。
- 创建、修改、删除仍需要确认。

## 失败排查

### A. 语音没有转文字

- 检查 Hermes gateway voice pipeline 是否启用。
- 检查 ASR 模型配置。
- 检查 `gateway.log` 中是否出现 `voice` / `ASR` 相关日志。
- 如果 Hermes 未产生转写文本，本仓库脚本不会被调用。

### B. 没进入 Calendar Skill

- 检查 `SKILL.md` 是否包含 WeChat Voice Secretary Rules。
- 检查转写文本是否包含“安排、会议、日程、出门、出差、提醒、取消、推迟、增加”等关键词。
- 检查 `gateway.log` 是否出现 `schedule_query_router.py`、`reminder_action_flow.py` 或 `trip_flow.py` 调用。

### C. 没有语音回复

- 检查 `voice_mode`：
  `off` 模式不会发语音。
- 检查用户是否明确要求语音回复；没有明确要求时只回文字是预期行为。
- 检查 Hermes profile 的 TTS 配置。
- 检查 `gateway.log` 中是否出现 `TTS` 相关日志。
- 当前 Weixin iLink bot 出站原生 voice 气泡会被客户端静默丢弃；封板策略是音频附件。

### D. 修改或删除直接执行

这是严重错误。

- 必须修正 `SKILL.md`。
- 所有修改、删除、推迟都必须先生成草稿。
- 只有用户明确确认后，才允许执行 confirm。

## 安全边界

- 不读取微信 token。
- 不绕过 Hermes gateway。
- 不请求外部网络，除非 Hermes 原有 ASR/TTS 配置本身需要。
- 不跳过确认。
- 不写 Apple Reminders。
- 不修改 `飞行计划`。
- 不新增本仓库 ASR/TTS 实现。
