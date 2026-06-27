# BOSS直聘 — 聊天与消息

于 2026-05-01 针对 zhipin.com 实测验证。
需要登录。消息通过 WebSocket + REST API 加载。

**重要提示**：未经用户明确许可，切勿发送消息。本技能仅记录读取/检索机制。

---

## 架构

BOSS直聘采用混合消息架构：

- **会话列表** — 页面加载时通过 WebSocket（`ws6.zhipin.com`）加载，而非 REST 接口
- **消息历史** — REST API `/wapi/zpchat/geek/historyMsg`
- **实时消息** — 通过 `ws6.zhipin.com` 的 WebSocket 推送

---

## 聊天页面（`/web/geek/chat`）

### 页面结构

```
左侧面板:
  .chat-user.v2                  — 筛选栏 + 搜索输入框
    .label-list > ul
      li.selected                — 当前选中的筛选标签
      li                         — "未读(N)" 在 <i> 中显示数量角标
      li > .ui-dropmenu          — "更多" 下拉菜单（仅沟通/有交换/有面试/不感兴趣）
      li.filter-item             — "AI筛选" 下拉菜单，含自然语言输入框
    .boss-search-input           — 联系人搜索（占位符："搜索30天内的联系人"）
  .user-list
    .user-list-content
      .friend-content-warp
        .friend-content           — 会话条目（点击打开）
          .friend-content.friend-top  — 置顶会话

右侧面板（点击会话后显示）:
  .chat-record                   — 消息历史容器
    .message-item.item-myself    — 用户发送的消息
      .item-time > .time         — 时间戳
      .message-content > .text   — 消息正文
      .message-status.status-read — 已读回执（"已读"）
    .message-item.item-friend    — 招聘者发送的消息
      .item-time > .time
      .message-content > .text
```

### 筛选标签

顶部标签（`.chat-user.v2 .label-list li`）：

| 标签 | 说明 | 类名 |
|-----|------|------|
| 全部 | 所有会话（默认） | 选中时为 `li.selected` |
| 未读(N) | 未读会话，角标显示数量 | 标签内 `<i>` 显示数量 |
| 新招呼 | 招聘者发来的新招呼 | 通过 `<i class="badge">` 显示角标 |
| 更多 ▾ | 包含额外筛选的下拉菜单 | `.ui-dropmenu` |

"更多" 下拉菜单（`.more-label li`）：

| 选项 | 说明 |
|------|------|
| 仅沟通 | 有消息往来的会话 |
| 有交换 | 有文件/联系方式交换的会话 |
| 有面试 | 有面试邀请的会话 |
| 不感兴趣 | 标记为"不感兴趣"的会话 |

"AI筛选"（`.filter-item > .ui-dropmenu`）：打开一个面板，包含 `<textarea>` 用于自然语言筛选输入（例如 "后端开发 上海 高薪"）。

#### 点击筛选标签

```python
def click_filter(label_text):
    """根据文本标签点击筛选标签。"""
    js(f"""
    (function() {{
        var labels = document.querySelectorAll('.chat-user .label-list li .label-name');
        for (var i = 0; i < labels.length; i++) {{
            if (labels[i].textContent.trim().indexOf('{label_text}') === 0) {{
                labels[i].closest('li').click();
                return true;
            }}
        }}
        return false;
    }})()
    """)
    wait(1)

def click_more_filter(label_text):
    """点击"更多"下拉菜单中的选项。"""
    # 先打开下拉菜单
    click_filter("更多")
    wait(0.5)
    js(f"""
    (function() {{
        var items = document.querySelectorAll('.more-label li span');
        for (var i = 0; i < items.length; i++) {{
            if (items[i].textContent.trim() === '{label_text}') {{
                items[i].closest('li').click();
                return true;
            }}
        }}
        return false;
    }})()
    """)
    wait(1)
```

### 会话条目（DOM）

每个 `.friend-content` 包含：
- 时间戳（如 "04月13日"、"昨天"）
- 招聘者姓名（如 "刘女士"）
- 公司名称（如 "Soul App"）
- 招聘者头衔（如 "招聘专家"）
- 最近消息预览
- 未读数量角标（数字）

### 读取会话列表（DOM）

```python
def get_conversations():
    raw = js("""
    (function() {
        var items = document.querySelectorAll('.friend-content');
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            var text = el.textContent;
            var badge = el.querySelector('[class*="badge"], [class*="unread"], [class*="count"]');
            var unread = badge ? parseInt(badge.textContent) || 0 : 0;
            results.push({
                text: text.trim().substring(0, 150),
                is_top: el.classList.contains('friend-top'),
                unread: unread
            });
        }
        return JSON.stringify(results);
    })()
    """)
    return json.loads(raw)
```

### 打开会话

点击 `.friend-content` 元素：

```python
def open_conversation(index=0):
    js(f"document.querySelectorAll('.friend-content')[{index}].click()")
    wait(2)
```

---

## API：消息历史

```
GET /wapi/zpchat/geek/historyMsg?bossId={bossId}&maxMsgId=0&c=20&page=1&src=0
```

### 参数

| 参数 | 说明 |
|------|------|
| `bossId` | 会话中的招聘者 ID（格式：`9c833990a839f1251Hx92du5GA~~`） |
| `maxMsgId` | 分页游标。首页为 `0`，之后使用上一页最小的 `mid` |
| `c` | 每页数量（默认 20） |
| `page` | 页码 |
| `src` | 来源（0 表示网页端） |

`bossId` 可在点击会话后的 performance 条目中找到，或从页面加载时的 WebSocket 连接数据中提取。

### 响应（`zpData.messages[]`）

每条消息包含：

```python
{
    "mid": 337069469603329,              # 消息 ID（数字，用于分页）
    "type": 3,                           # 3=普通消息, 4=系统消息
    "received": true,                    # 是否为接收到的消息
    "body": {
        "type": 1,                       # 1=文本, 8=职位卡片
        "text": "message text here...",  # body.type=1 时存在
        "jobDesc": { ... }               # body.type=8 时存在
    },
    "from": {
        "uid": 502838021,                # 发送者用户 ID
        "name": "张女士",
        "avatar": "https://img.bosszhipin.com/..."
    },
    "to": {
        "uid": 680839465                 # 接收者用户 ID
    }
}
```

### 消息体类型

| `body.type` | 含义 | 字段 |
|-------------|------|------|
| `1` | 纯文本 | `body.text` |
| `8` | 职位描述卡片 | `body.jobDesc`（title、salary、company、boss、city、experience、education），`body.headTitle` |
| `16` | 系统通知 | （文件已接收等） |

### 职位卡片消息（`body.type=8`）

```python
{
    "body": {
        "type": 8,
        "headTitle": "您正在与Boss刘女士直接沟通如下职位",
        "jobDesc": {
            "title": "AI Agent工程师",
            "salary": "35-60K·16薪",         # 真实薪资 — 非字体编码
            "company": "Soul App",
            "city": "上海 浦东新区 金桥",
            "experience": "经验不限",
            "education": "硕士",
            "stage": "D轮及以上",
            "positionCategory": "算法工程师",
            "boss": {
                "uid": 3872648,
                "name": "刘女士",
                "avatar": "https://img.bosszhipin.com/..."
            },
            "bossTitle": "招聘专家",
            "jobId": 509933581
        }
    }
}
```

### 获取消息历史

```python
def fetch_messages(boss_id, page=1, count=20):
    raw = js(f"""
    (async function() {{
        var url = '/wapi/zpchat/geek/historyMsg?bossId={boss_id}&maxMsgId=0&c={count}&page={page}&src=0';
        var r = await fetch(url);
        var d = await r.json();
        if (d.code !== 0 || !d.zpData) {{
            return JSON.stringify({{code: d.code, hasMore: false, count: 0, messages: [], error: d.msg || 'API error'}});
        }}
        var msgs = d.zpData.messages || [];
        return JSON.stringify({{
            code: d.code,
            hasMore: d.zpData.hasMore,
            count: msgs.length,
            messages: msgs.map(function(m) {{
                var b = m.body || {{}};
                return {{
                    mid: m.mid,
                    type: m.type,
                    body_type: b.type,
                    text: b.text || null,
                    job: b.jobDesc ? {{
                        title: b.jobDesc.title,
                        salary: b.jobDesc.salary,
                        company: b.jobDesc.company,
                        city: b.jobDesc.city,
                        boss_name: (b.jobDesc.boss || {{}}).name,
                        job_id: b.jobDesc.jobId
                    }} : null,
                    from_name: (m.from || {{}}).name,
                    from_uid: (m.from || {{}}).uid,
                    received: m.received
                }};
            }})
        }});
    }})()
    """)
    return json.loads(raw)
```

### 分页

使用 `maxMsgId`（而非 `page`）进行高效分页。将 `maxMsgId` 设置为上一批中最小的 `mid`：

```python
def fetch_all_messages(boss_id):
    all_msgs = []
    max_msg_id = 0
    while True:
        raw = js(f"""
        (async function() {{
            var r = await fetch('/wapi/zpchat/geek/historyMsg?bossId={boss_id}&maxMsgId={max_msg_id}&c=20&page=1&src=0');
            var d = await r.json();
            if (d.code !== 0 || !d.zpData) {{
                return JSON.stringify({{messages: [], hasMore: false}});
            }}
            return JSON.stringify(d.zpData);
        }})()
        """)
        data = json.loads(raw)
        msgs = data.get("messages", [])
        if not msgs:
            break
        all_msgs.extend(msgs)
        if not data.get("hasMore"):
            break
        max_msg_id = msgs[-1]["mid"]  # 最小的 mid
        wait(0.5)
    return all_msgs
```

---

## 从 DOM 读取消息（打开会话后）

```python
def read_messages_dom():
    raw = js("""
    (function() {
        var items = document.querySelectorAll('.message-item');
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            var timeEl = el.querySelector('.time');
            var textEl = el.querySelector('.text');
            var statusEl = el.querySelector('.message-status');
            results.push({
                from_me: el.classList.contains('item-myself'),
                time: timeEl ? timeEl.textContent.trim() : '',
                text: textEl ? textEl.textContent.trim().substring(0, 300) : '',
                status: statusEl ? statusEl.textContent.trim() : ''
            });
        }
        return JSON.stringify(results);
    })()
    """)
    return json.loads(raw)
```

---

## 从页面提取 bossId

`bossId` 嵌入在 WebSocket 负载和 API 调用中。点击会话后可通过以下方式发现：

```python
def get_current_boss_id():
    return js("""
    (function() {
        var entries = performance.getEntriesByType('resource');
        for (var i = entries.length - 1; i >= 0; i--) {
            var url = entries[i].name;
            if (url.indexOf('/wapi/zpchat/geek/historyMsg') === -1) continue;
            var match = url.match(/bossId=([^&]+)/);
            if (match) return match[1];
        }
        return null;
    })()
    """)
```

---

## 从职位详情导航到聊天

打开职位详情页并点击"立即沟通"即可发起与该职位招聘者的会话。所需 API：

1. 导航到 `/job_detail/{JOB_ID}.html`
2. 找到聊天按钮（`.btn-startchat`）元素
3. 按钮的 `href` 或点击处理程序包含 `bossId` 和 `securityId`

---

## 注意事项

- **会话列表通过 WebSocket 加载** — 没有用于列表的 REST API。使用 DOM 提取（`.friend-content`）或监控 WebSocket 帧来获取初始会话列表。
- **消息历史使用 `bossId`，而非 `encryptBossId`** — `bossId` 格式为 `"9c833990a839f1251Hx92du5GA~~"`（尾部带 `~~`），与职位列表中的 `encryptBossId` 不同。
- **`maxMsgId` 分页** — 使用当前批次中最小的 `mid` 作为下一页的游标，而非 `page` 参数。
- **消息中的职位卡片包含真实薪资** — `body.jobDesc.salary` 返回 `"35-60K·16薪"`，而 DOM 使用字体编码的数字。
- **系统消息（type=4）** — 包括已读回执、文件传输（"对方已同意，您的附件简历已发送给对方"）和竞品分析卡片。
- **点击会话后需要 `wait(2)`** — 消息历史需要时间渲染。
- **`item-myself` 与 `item-friend`** — 用户消息有 `item-myself` 类名，招聘者消息有 `item-friend` 类名。
- **联系人搜索输入框** — `.boss-search-input` 搜索 30 天内的联系人，不是通用消息编写框。
