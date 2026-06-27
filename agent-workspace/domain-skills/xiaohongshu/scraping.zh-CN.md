# 小红书 — 搜索与排序

URL 模式：
- 首页 / 发现页：`https://www.xiaohongshu.com/explore`
- 搜索结果：`https://www.xiaohongshu.com/search_result?keyword=...`

## 搜索流程

- 优先通过直接导航到桌面端搜索结果页，而非自动化首页搜索框。
- 可靠的主要路径：`https://www.xiaohongshu.com/search_result?keyword=<url编码的关键词>&source=web_explore_feed`
- 此路径加载正常的桌面端结果页，避免首页输入框的不稳定性。
- 搜索结果页也可能在应用内导航后出现 `type=51` 或其他 `source` 值的变体；如果渲染结果正确，不要将这些视为异常。
- `explore` 顶部的搜索框也可以使用，从首页搜索在某些会话中已经可以跳转到 `search_result` 而无需登录墙。
- 页面在 DOM 中暴露了重复的搜索输入框，占位符同为 `搜索小红书`。
- 首页搜索输入框可能表现为严格受控的应用字段：直接 DOM 赋值可能被立即清除，即使输入框已获焦，测试框架的 `type_text()` 也可能无法填充。
- 将首页输入框视为尽力而为。当类人交互流程很重要时使用它，但自动化默认应直接构建 `search_result` URL。

## 排序行为

- 在当前桌面端结果布局中，`最新` **不是** `综合` 旁边的顶级标签。
- 打开结果头部右上角的 `筛选` 控件来访问排序选项。
- 在 `筛选` 中，`排序依据` 包含：
  - `综合`
  - `最新`
  - `最多点赞`
  - `最多评论`
  - `最多收藏`
- `排序依据` 行可以为相同的标签文本渲染重复的 DOM 节点，包括不可交互的克隆。
- 对 `最新` 进行全局文本搜索可能先命中错误的节点。限定在 `排序依据` 区域内，然后选择可见的可交互 `.tags` 节点。
- 优先使用语义筛选，如 `aria-hidden != "true"` 或区域限定的可见 `.tags` 选择，而非样式特定检查。
- 当 `最新` 被激活时，`筛选` 触发器变为 `已筛选`。
- 渲染的信息流和 `已筛选` / 激活标签的 UI 比 `window.__INITIAL_STATE__.search.searchContext.sort` 更可靠地确认最新排序。

## 稳定标识

- 顶部附近的搜索频道标签：`全部`、`图文`、`视频`、`用户`
- 排序面板标签：`筛选`、`排序依据`、`最新`
- 面板中还可见的筛选区域：`笔记类型`、`发布时间`、`搜索范围`、`位置距离`

## 交互说明

- DOM `.click()` 可靠地打开了 `筛选` 面板。
- DOM `.click()` 在打开的 `排序依据` 区域内对可见的 `最新` 标签可可靠地激活最新排序。
- 可靠的 DOM 模式是：
  - 找到 `排序依据` 区域 / `.filters` 块
  - 在该块内搜索 `.tags`
  - 选择文本为 `最新` 且为可见可交互节点的那个
  - 对该可见节点调用 `.click()`
- 示例选择器策略：
  - 找到第一个标签为 `排序依据` 的 `.filters`
  - 在其中选择 `textContent.trim() === "最新"` 且 `el.getAttribute("aria-hidden") !== "true"` 的 `.tags`
- 仅用 `getClientRects().length > 0` 可能不足以区分有效节点和重复节点。
- 对 `document.querySelectorAll("*")` 进行文本匹配搜索 `最新` 在此页面上不可靠，因为可能点击隐藏的重复节点而非可见控件。
- 对可见的 `最新` 标签进行坐标点击也有效，如果 DOM 定位因未来 UI 变更而混乱，仍可作为有效的备选方案。
- 选择 `最新` 后，网格短暂显示骨架占位符，然后出现刷新后的结果。
- 搜索页将当前渲染的笔记卡片存储在 `window.__INITIAL_STATE__.search.feeds._value` 中，作为信息流条目数组。对于普通笔记卡片，有用的字段有：
  - `id`
  - `xsecToken`
  - `noteCard.displayTitle`
  - `noteCard.user.nickname`
- 信息流数组可能包含非笔记插入项，如热门查询模块。在将条目视为笔记结果之前，需筛选包含 `noteCard` 的条目。

## 笔记打开

- **不要**假设原始结果链接如 `https://www.xiaohongshu.com/explore/<id>` 可以直接打开。
- 在新标签页中打开原始的 `/explore/<id>` URL 可能重定向到网页 404 / 仅限应用的门槛页，即使同一篇笔记可从搜索结果打开。
- 要从搜索结果打开笔记，先点击可见的卡片图片/卡片进行页内导航。
- 该点击导航可以到达带 Token 的 URL，如 `https://www.xiaohongshu.com/explore/<id>?xsec_token=...&xsec_source=pc_search`，这比原始 `/explore/<id>` 形式更可靠。
- 一旦通过点击流程获得带 Token 的 URL，可在会话内重新访问以提取内容。
- 如果搜索结果状态已加载，可以直接从信息流条目重建带 Token 的笔记 URL，无需重新点击：
  - `https://www.xiaohongshu.com/explore/<id>?xsec_token=<xsecToken>&xsec_source=pc_search`

## 笔记提取

- 在通过 `pc_search` 打开的带 Token 笔记页面上，`document.body.innerText` 可以作为有用的初遍提取来源，因为它通常包含渲染的笔记文本、话题标签、时间戳、互动数和可见评论。
- 在信任 `document.body.innerText` 之前，请验证笔记内容确实已渲染，因为页面也可能包含大量导航、底部和评论噪声。
- 优先将 `document.body.innerText` 作为备选或初步探测，而非为笔记内容编写脆弱的逐元素选择器。

## 注意事项

- 不要假设按 `Enter` 就完成了搜索流程，除非你验证 URL 已变为 `search_result` 或结果网格已出现。
- 不要假设可见的 `综合` 标签控制所有排序；在此布局中，时间排序隐藏在 `筛选` 内。
- 不要假设第一个文本为 `最新` 的 DOM 节点就是可点击的；此面板会复制标签，隐藏的克隆可能吸收朴素文本定位而不改变状态。
- 不要假设成功打开的笔记可以通过去除查询参数来复现；重新打开来自搜索结果的笔记 URL 时保留 `xsec_token`。
