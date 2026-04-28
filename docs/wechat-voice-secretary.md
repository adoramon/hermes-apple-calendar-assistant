# 微信语音秘书模式

Phase 55 目标是让微信语音消息进入现有秘书事务链路：Hermes gateway 负责语音转文字
和可选 TTS，本仓库只处理转写后的文本意图，不重复实现 ASR/TTS。

## 用户体验

用户在微信发送语音后，预期链路是：

```text
微信语音
-> Hermes gateway ASR 转文字
-> Apple Calendar Skill 判断秘书事务意图
-> 调用现有 calendar / trip / reminder 脚本
-> 返回文字
-> Hermes gateway 按 voice_mode 决定是否附带女声 TTS
```

典型回复应短、自然、可直接听懂：

```text
高先生，明天第一项安排是 9:30 产品会议。
建议您 8:40 出门，我已经帮您看过时间。
```

## voice_mode

- `off`：仅文字回复，当前封板默认模式。
- `smart`：仅当用户明确要求“语音回复”“读给我听”“用语音说”时附带 TTS 音频附件。
- `always`：当前 Weixin iLink 通道不建议启用，避免无意义音频附件。

切换话术：

- `以后只文字回复`：切换到 `off`。
- `安静模式`：切换到 `off`。
- `打开语音回复`：可切换到 `smart`，但仍只在明确语音请求时发送音频附件。
- `开车模式`：按文字回复处理，不追加语音附件。

voice_mode 建议由 Hermes profile / gateway 层保存，本仓库不读取微信 token，也不直接
调用微信发送接口。

当前 Weixin iLink bot 出站原生 voice 气泡会被客户端静默丢弃：HTTP/iLink 返回成功，
但微信端不显示语音气泡。封板策略是使用可见音频附件作为语音回复载体；附件不带
`voice message as attachment` 英文提示，文件名应为中文，例如 `Hermes语音回复.ogg`。

## 示例语音指令

查询类：

- `我明天什么安排`
- `今天几点出门`
- `下周上海出差怎么样`
- `我什么时候去广州`

操作类：

- `帮我把下午会议推迟半小时`
- `明天三点加一个会议`
- `取消今晚晚餐`

提醒类：

- `提醒我两点给王总打电话`
- `明早八点叫我出门`

## 微信端实测收口

Phase 56 的标准验证文档见：

[wechat-voice-validation.md](wechat-voice-validation.md)

核心测试包括：

- 语音 `我明天什么安排`：应进入 `schedule_query_router.py query`。
- 语音 `帮我把下午会议推迟半小时`：应生成修改/提醒后续操作草稿，不直接改 Calendar。
- 语音 `下周上海出差怎么样`：应返回 Trip 摘要。

排查时优先搜索日志关键字：

- `voice`
- `ASR`
- `TTS`
- `schedule_query_router.py`
- `reminder_action_flow.py`
- `trip_flow.py`

## 路由规则

转写文本包含以下关键词时，应优先进入 Apple Calendar Skill：

- `安排`
- `会议`
- `日程`
- `出门`
- `出差`
- `提醒`
- `取消`
- `推迟`
- `增加`
- `添加`

推荐调用：

```bash
python3 scripts/schedule_query_router.py query --text "我明天什么安排"
python3 scripts/reminder_action_flow.py draft --text "帮我把下午会议推迟半小时"
python3 scripts/nlp_event_parser.py parse "明天三点加一个会议"
python3 scripts/interactive_create.py create-draft --session-key "<session_key>" --calendar "商务计划" --title "<title>" --start "<start>" --end "<end>" --check-conflict
```

Trip 查询可以复用：

```bash
python3 scripts/schedule_query_router.py query --text "下周上海出差怎么样"
python3 scripts/trip_flow.py draft --trip-id "<trip_id>"
```

## 安全边界

- 不读取微信 token。
- 不绕过 Hermes gateway。
- 不重新实现 ASR/TTS。
- 不请求外部网络。
- 不修改 `飞行计划` 规则。
- 删除、修改、创建、Trip 写入仍必须先生成草稿并等待确认。
- 语音输入不等于确认，除非用户明确说“确认写入”“确认删除”等清晰确认语。

## 常见故障排查

- 语音被当闲聊：检查转写文本是否包含秘书事务关键词，检查 `SKILL.md` 是否加载了
  WeChat Voice Secretary Rules。
- 没有语音回复：先确认用户是否明确要求语音回复；默认文字回复是预期行为。
  如明确要求仍无音频附件，再检查 profile 的 voice/TTS 设置和 `voice_mode`。
- 直接修改或删除日程：严重错误，应回到确认式 draft -> confirm 流程。
- 查询没结果：先确认 ASR 转写是否准确，再看 `schedule_query_router.py query` 输出。
- TTS 声音不对：在 Hermes gateway/profile 层调整 voice provider 或 voice id。

## 关闭语音回复

用户可直接说：

```text
以后只文字回复
```

或：

```text
安静模式
```

系统应切换或建议切换为 `voice_mode=off`。当前封板默认即为文字优先；安静模式、
开车模式、只文字回复都不应追加语音附件。
