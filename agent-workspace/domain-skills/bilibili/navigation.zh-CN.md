# 哔哩哔哩 — 站点导航与结构

于 2026-05-01 针对 bilibili.com 实测验证。
个人空间功能需要登录；公共页面无需登录即可访问。

---

## URL 模式

### 核心页面

| 页面 | URL |
|------|-----|
| 首页（推荐流） | `https://www.bilibili.com/` |
| 动态（关注流） | `https://t.bilibili.com/` |
| 个人空间 | `https://space.bilibili.com/{UID}` |
| 观看历史 | `https://www.bilibili.com/account/history` |
| 稍后再看 | `https://www.bilibili.com/watchlater/#/list` |
| 消息 | `https://message.bilibili.com/` |
| 搜索 | `https://search.bilibili.com/all?keyword={QUERY}` |

### 个人空间子页面

| 页面 | URL |
|------|-----|
| 主页（视频 + 收藏） | `https://space.bilibili.com/{UID}` |
| 动态（用户活动） | `https://space.bilibili.com/{UID}/dynamic` |
| 投稿 | `https://space.bilibili.com/{UID}/upload` |
| 合集和系列 | `https://space.bilibili.com/{UID}/lists` |
| 收藏 | `https://space.bilibili.com/{UID}/favlist` |
| 追番追剧 | `https://space.bilibili.com/{UID}/bangumi` |
| 设置 | `https://space.bilibili.com/{UID}/settings` |

### 发现

| 页面 | URL |
|------|-----|
| 热门 | `https://www.bilibili.com/v/popular/all` |
| 每周必看 | `https://www.bilibili.com/v/popular/weekly?num={ISSUE}` |
| 入站必刷 | `https://www.bilibili.com/v/popular/all`（入站必刷标签） |
| 排行榜（全部） | `https://www.bilibili.com/v/popular/rank/all` |
| 话题 | `https://www.bilibili.com/v/topic/` |

### 视频页面

| 方面 | 模式 |
|------|------|
| 观看 URL | `https://www.bilibili.com/video/{BV_ID}` |
| BV 格式 | `BV` 前缀 + 10 位字母数字，如 `BV1HeRKBdEoX` |
| AV 格式（旧版） | `av` + 数字，如 `av170001`（仍可解析） |

### 内容平台

| 页面 | URL |
|------|-----|
| 番剧 | `https://www.bilibili.com/anime/` |
| 电影 | `https://www.bilibili.com/movie/` |
| 电视剧 | `https://www.bilibili.com/tv/` |
| 纪录片 | `https://www.bilibili.com/documentary/` |
| 综艺 | `https://www.bilibili.com/variety/` |
| 国创 | `https://www.bilibili.com/guochuang/` |
| 专栏（文章/博客） | `https://www.bilibili.com/read/home` |
| 音频 / 音乐 | `https://www.bilibili.com/audio/home` |
| 课堂 | `https://www.bilibili.com/cheese/` |
| 直播 | `https://live.bilibili.com/` |
| 游戏中心 | `https://game.bilibili.com/platform` |
| 漫画 | `https://manga.bilibili.com/` |
| 会员购 | `https://show.bilibili.com/platform/home.html` |
| 赛事 | `https://www.bilibili.com/match/home/` |

### 创作者

| 页面 | URL |
|------|-----|
| 创作中心 | `https://member.bilibili.com/platform/home` |
| 投稿视频 | `https://member.bilibili.com/platform/upload/video/frame` |

### 其他

| 页面 | URL |
|------|-----|
| 大会员 | `https://account.bilibili.com/big` |
| 小黑屋（封禁） | `https://www.bilibili.com/blackroom/ban` |

---

## 顶部导航栏

`bilibili.com` 顶部的水平导航：

```
首页 | 番剧 | 直播 | 游戏中心 | 会员购 | 漫画 | 赛事
```

无论登录状态如何均始终可见。

### 左侧边栏分区

首页左侧边栏列出 30 个内容分区。每个分区映射到 `bilibili.com/c/{SLUG}` 或顶级路径：

```
动态  热门  番剧  电影  国创  电视剧  综艺  纪录片
动画  游戏  鬼畜  音乐  舞蹈  影视  娱乐  知识
科技数码  资讯  美食  小剧场  汽车  时尚美妆
体育运动  动物  vlog  绘画  人工智能  家装房产
户外潮流  健身
```

分区 URL：
- `bilibili.com/c/{slug}` — 如 `/c/douga`（动画）、`/c/game`、`/c/music`、`/c/ai`
- 部分使用完整单词：`/c/knowledge`、`/c/information`、`/c/food`、`/c/fashion`、`/c/sports`、`/c/animal`、`/c/painting`、`/c/home`、`/c/outdoors`、`/c/gym`
- 其他使用缩写：`/c/kichiku`（鬼畜）、`/c/ent`（娱乐）、`/c/tech`（科技）
- 短剧：`/c/shortplay`
- 汽车：`/c/car`

---

## 用户菜单（顶部栏右侧，需要登录）

右上角头像访问的下拉菜单：

| 项目 | URL | 备注 |
|------|-----|------|
| 大会员 | `account.bilibili.com/big` | 会员状态 |
| 消息 | `message.bilibili.com` | 子项：回复我的、@我的、收到的赞、系统消息、我的消息 |
| 动态 | `t.bilibili.com` | 关注流 — 日常使用最重要 |
| 收藏 | `space.bilibili.com/{UID}/favlist` | 收藏夹 |
| 历史 | `https://www.bilibili.com/account/history` | 观看历史 |
| 创作中心 | `member.bilibili.com/platform/home` | 创作者仪表板 |
| 投稿 | `member.bilibili.com/platform/upload/video/frame` | 上传 |

---

## 个人空间标签页（`space.bilibili.com/{UID}`）

个人空间内的子导航：

```
主页 | 动态 | 投稿 | 合集和系列 | 收藏 | 追番追剧 | 设置
```

- **主页** — 视频网格 + 收藏夹 + 数据统计
- **动态** — 该用户的活动流（与 `t.bilibili.com` 的关注流不同）
- **投稿** — 已发布视频，可按：最新发布 / 最多播放 / 最多收藏排序
- **合集和系列** — 精选视频合集
- **收藏** — 收藏夹（公开或私密）
- **追番追剧** — 追踪的番剧/剧集
- **设置** — 空间配置

### 用户数据（个人空间可见）

选择器：`.nav-statistics` 包含 `.nav-statistics__item` 子元素。

| 数据项 | 类名 |
|--------|------|
| 关注数 | `.nav-statistics__item.jumpable`（第一个） |
| 粉丝数 | `.nav-statistics__item.jumpable`（第二个） |
| 获赞数 | `.nav-statistics__item`（第三个） |
| 播放数 | `.nav-statistics__item`（第四个） |

数值在 `.nav-statistics__item-num` 中。

---

## 视频页面 — 互动功能

在观看页面（`bilibili.com/video/{BV_ID}`）时，播放器下方的工具栏提供：

| 操作 | 选择器 / 类名 | 备注 |
|------|---------------|------|
| 点赞 | `.video-like` | 计数在 `.video-like-info` |
| 投币 | `.video-coin` | 每位用户每个视频最多投 2 枚硬币 |
| 收藏 | `.video-collect` | 添加到收藏夹 |
| 分享 | `.video-share-wrap` | 打开分享面板，含链接/复制/二维码 |
| 三连 | 长按点赞按钮 | 一次性触发点赞 + 投币 + 收藏 |

**三连**是哔哩哔哩的标志性互动 — 长按点赞按钮会同时发送点赞、投 1 枚硬币和添加收藏。

### 硬币

- 用户每日登录可获得硬币
- 通过"投币"花费硬币（每个视频 1 或 2 枚）
- 硬币数量显示在头部用户区域
- 与 B币 不同 — B币是用真钱购买的

### 弹幕

实时评论在视频上滚动显示。通过播放器控件中的弹幕按钮切换。弹幕数据在视频播放器初始化后通过 XHR 加载。

### 充电

月度订阅/打赏以支持创作者。可从创作者空间页面或视频播放器下方访问。

---

## 收藏（`/favlist`）

每个收藏夹显示：名称、视频数量、可见性（公开/仅自己可见）。

页面上分两个区域：
- **我创建的收藏夹** — 用户自己的收藏夹
- **我追的合集/收藏夹** — 关注的其他用户的合集

操作：
- 创建新收藏夹：点击"新建收藏夹"
- 设置可见性：每个收藏夹独立设置（公开 / 仅自己可见）
- 默认收藏夹自动创建，保存所有快速收藏的视频

---

## 观看历史（`/account/history`）

功能：
- **暂停/恢复** 记录 — "暂停记录历史" / "继续记录历史"
- **清空全部** — "清空历史"
- **日期筛选** — 今天 / 昨天 / 近1周 / 1周前 / 1个月前
- 每条记录显示：标题、进度（看到 XX:XX）、UP主名称、分区标签

历史条目在 `.history-record` 元素中。

### 稍后再看

位于 `bilibili.com/watchlater/#/list`。也作为个人空间主页收藏区域中的默认收藏夹出现。

---

## 搜索（`search.bilibili.com`）

搜索结果按标签页分类：

```
综合 | 视频 | 番剧 | 影视 | 直播 | 专栏 | 用户
```

每个标签页显示数量角标（如 "视频99+"）。查询参数：`?keyword={QUERY}`。

在搜索输入框中输入时会出现自动补全建议。

---

## 热门页面（`/v/popular/all`）

标签栏：

```
综合热门 | 每周必看 | 入站必刷 | 排行榜 | 全站音乐榜
```

- **综合热门** — 当前热门趋势
- **每周必看** — 每周精选，URL：`/v/popular/weekly?num={ISSUE}`
- **入站必刷** — 经典必看视频
- **排行榜** — 重定向到 `/v/popular/rank/all`
- **全站音乐榜** — 音乐专属榜单

### 排行榜（`/v/popular/rank/all`）

24 个分类标签：全部, 番剧, 国创, 纪录片, 电影, 电视剧, 综艺, 动画, 游戏, 鬼畜, 音乐, 舞蹈, 影视, 娱乐, 知识, 科技, 数码, 美食, 汽车, 时尚, 美妆, 体育, 运动, 动物

每条记录显示：排名、标题、创作者、播放量、互动量。

---

## 检测登录状态

```python
# 已登录：头像元素存在
avatar = js("document.querySelector('.header-entry-avatar')?.src || 'not logged in'")

# 未登录：登录按钮可见
login_btn = js("document.querySelector('.header-login-entry')?.textContent?.trim() || 'no login btn'")
```

提取当前用户的 UID：

```python
uid = js("document.querySelector('.header-entry-avatar')?.closest('a')?.href?.match(/space\\.bilibili\\.com\\/(\\d+)/)?.[1]")
```

---

## 注意事项

- **"动态"有两个含义** — `t.bilibili.com` 是关注流（你关注的人的内容），而 `space.bilibili.com/{UID}/dynamic` 是特定用户的活动流。它们是不同的页面。
- **收藏 URL 会重定向** — 导航到 `/favlist` 可能重定向到 `/favlist?fid={DEFAULT_FOLDER_ID}&ftype=create`，自动打开第一个收藏夹。
- **历史记录可以暂停** — 如果历史页面显示"历史功能暂停中"，说明用户暂停了记录。点击"继续记录历史"恢复。
- **UID 是数字** — 哔哩哔哩用户 ID 全部为数字，与 YouTube 的用户名不同。UID 出现在空间 URL 中且保持不变。
- **BV 与 AV ID** — 现代视频 ID 使用 BV 格式（如 `BV1HeRKBdEoX`）。旧版 AV 格式（如 `av170001`）仍可解析，但所有新内容使用 BV。
- **视频 URL 会被追加 `?vd_source=`** — 从已登录会话导航时，哔哩哔哩会追加 `vd_source` 追踪参数。可以去除。
- **稍后再看与历史是独立的** — `/watchlater/#/list` 是单页应用路径，不是 `/account/history` 的子页面。
- **硬币不是 B币** — 硬币是每日免费获取的。B币是用真钱购买的，用于打赏/充电/会员。
- **部分分区 URL 使用缩写** — 鬼畜是 `/c/kichiku`，娱乐是 `/c/ent`，科技是 `/c/tech`。并非所有都是拼音或翻译。
- **视频页面上 `wait_for_load()` 不够** — 与 YouTube 类似，视频播放器及其工具栏组件在 load 事件之后才水合完成。在查询视频工具栏选择器前添加 `wait(3)`。
