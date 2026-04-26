# Calendar Event Query Bugfix

当前状态：`v2.0-rc Calendar event query bugfix documented`。

本记录收口一次提醒链路实测中发现的 Calendar 读取问题：用户在 Calendar.app 的
`个人计划` 中手工创建了 `再次测试`，开始时间为 `2026-04-26 13:00`，但微信没有
收到提醒。

## 现象

- Hermes Cron bridge 正常运行。
- `outbox` 中没有新的 `pending` 提醒。
- `reminder_worker.py scan` 没有生成提醒候选。
- 直接按标题查询 Calendar.app 可以看到事件：
  `再次测试 / 2026年4月26日 星期日 13:00:00 / 2026年4月26日 星期日 14:00:00`。
- 使用项目的时间窗口查询时，事件没有进入 `calendar_ops.py events` 结果。

## 根因

本次问题由三个 Calendar AppleScript 兼容性和解析问题叠加造成：

- Calendar.app 的 AppleScript `whose` 时间过滤对 date 属性需要使用 `its`，
  例如 `whose its end date is greater than windowStart`。
- 旧变量名如 `startDate`、`endDate`、`eventStartText`、`eventEndText` 容易与
  Calendar AppleScript 术语冲突，导致语法错误或查询异常。
- `再次测试` 的地点字段是多行地址。旧解析使用换行分隔事件记录，且会对 stdout
  做 `.strip()`，导致带多行地点、空备注或空地点的事件行被拆坏或丢弃。

## 修复

已在 `scripts/calendar_ops.py` 中修复：

- 时间窗口过滤改为：
  `every event of targetCalendar whose its end date is greater than windowStart and its start date is less than windowEnd`
- AppleScript 日期变量改为更安全的命名：
  `windowStart`、`windowEnd`、`eventStartValue`、`eventEndValue`、
  `updatedStartValue`、`updatedEndValue`。
- 事件输出增加 `cleanField`：
  将字段中的 tab、linefeed、return 清洗为空格，并将 `missing value` 归一为空字符串。
- `_run_osascript()` 不再对 stdout 做通用 `.strip()`，改为只去掉行尾换行，
  保留 tab 分隔和空字段。

## 验证命令

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache-hermes-calendar python3 -m py_compile scripts/*.py

python3 scripts/calendar_ops.py events 个人计划 \
  --start 2026-04-26T12:00:00 \
  --end 2026-04-26T14:00:00

python3 scripts/reminder_worker.py scan \
  --format outbound \
  --channel hermes \
  --recipient default \
  --write-outbox

python3 scripts/outbox.py list --limit 5
```

验证结果：

- `calendar_ops.py events` 能返回 `再次测试`。
- 多行地点被清洗为单行：
  `望京北路9号叶青大厦D座7层 朝阳区 北京市 100102 中国`。
- `reminder_worker.py` 能生成 `60分钟后` 提醒并写入 `pending` outbox。

## 影响范围

该修复影响所有依赖 `calendar_ops.list_events()` 的读取路径，包括：

- 日程查询
- 冲突检测
- reminder worker 提醒扫描
- flight watcher / flight auto enhancer 中的事件读取

该修复不读取微信 token，不调用微信 API，不请求外部网络，不改变 Hermes Cron
Delivery 的投递边界。

## 后续建议

- 增加一个专门的 Calendar 查询回归测试夹具，覆盖空地点、空备注、多行地点、多行备注。
- 为 `reminder_worker` 增加 `doctor --title "<title>"` 诊断命令，直接显示事件是否被
  Calendar 查询读到、是否命中提醒窗口、是否被 `reminder_seen.json` 去重。
