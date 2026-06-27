# 携程（`ctrip.com`） — 酒店数据抓取

于 2026-04-29 针对 `hotels.ctrip.com` PC 网页端实测验证。国内酒店。

---

## 概要

**无需登录即可看到价格** — 但前提是你通过"自然"导航流程到达列表页，产生完整的 URL 参数结构。直接 GET 简化 URL 会被重定向到登录页。

- 需要浏览器会话（页面外壳 144 KB，酒店数据在水合后通过 XHR 加载）。`http_get` 无法获取酒店数据。
- 在有效的列表页上，价格渲染为 `¥<原价> ¥<现价> 起` 的配对。没有 `¥?` 占位符，也没有"请登录"中间页。
- 详情页 URL `https://hotels.ctrip.com/hotel/<hotelId>.html?checkin=...` 在登录前即可使用，并显示完整的房费明细。
- 相比同程旅行（每个价格都藏在登录墙后面），只要遵守 URL 参数结构，携程对抓取要友好得多。

---

## URL 模式

```
列表页（规范格式，支持匿名访问）:
  https://hotels.ctrip.com/hotels/list
    ?flexType=1
    &cityId=<n>          # 2 = 上海, 1 = 北京 等
    &provinceId=0
    &districtId=0
    &countryId=1         # 1 = 中国国内
    &checkin=YYYY-MM-DD
    &checkout=YYYY-MM-DD

酒店详情页（规范格式）:
  https://hotels.ctrip.com/hotel/<hotelId>.html?checkin=...&checkout=...
  → 服务端重写为 /hotels/detail/?... — 两者均可，数据相同

登录页（意外到达时）:
  https://passport.ctrip.com/user/login?backurl=<url编码的目标地址>
```

**关键提示**：简化形式 `https://hotels.ctrip.com/hotels/list?city=2&checkin=...&checkout=...`
（注意：`city` 而非 `cityId`，且缺少 `provinceId/districtId/countryId/flexType`）
**会被重定向到登录页。** 这是携程的标志性反爬门槛 — 它区分"真实"客户端（通过首页表单构建 URL）和脚本客户端（手动拼凑 URL）。

---

## 如何可靠地到达列表页

### 方式 A — 构建规范 URL（已知 cityId 时优先使用）

```python
from web_agent.helpers import new_tab, wait_for_load
import time
url = (
    "https://hotels.ctrip.com/hotels/list"
    "?flexType=1&cityId=2&provinceId=0&districtId=0&countryId=1"
    "&checkin=2026-04-29&checkout=2026-04-30"
)
new_tab(url)
wait_for_load(timeout=20)
time.sleep(6)            # XHR 酒店列表获取
```

### 方式 B — 模拟首页流程（仅有城市名称时）

如果只有城市名称，驱动首页表单。搜索按钮是 `<div>`，不是 `<button>`（与同程旅行相同 — 见下方"搜索按钮陷阱"）：

```python
from web_agent.helpers import new_tab, wait_for_load, js, click_at_xy, type_text, press_key
import time

new_tab("https://hotels.ctrip.com/")
wait_for_load(timeout=20)
time.sleep(2)

# 通过占位符查找目的地输入框
inp = js("""
  const i = Array.from(document.querySelectorAll("input"))
    .find(i => i.placeholder && /目的地|城市|酒店/.test(i.placeholder));
  if (!i) return null;
  const r = i.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
""")
if not inp:
    raise RuntimeError("携程首页：未找到目的地输入框 — 页面 DOM 可能已变更")
click_at_xy(inp["x"], inp["y"])
time.sleep(0.4)
type_text("上海")
time.sleep(1.5)
press_key("Enter")        # 选择第一个自动补全建议

btn = js("""
  const b = Array.from(document.querySelectorAll("button, div"))
    .find(el => (el.innerText||"").trim() === "搜索"
                && el.getBoundingClientRect().width > 60);
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
""")
if not btn:
    raise RuntimeError("携程首页：未找到搜索按钮 — 页面 DOM 可能已变更")
click_at_xy(btn["x"], btn["y"])
time.sleep(7)
# 现在在 /hotels/list?... 拥有完整规范参数结构
```

这是人类用户的操作方式，也是让参数结构匹配的方法。此流程中设置的 Cookie 也有助于后续直接 URL 请求。

---

## 列表页 — 提取酒店

卡片是 `<div class="list-item">`。**没有 `data-id`，没有 `<a href=...>`。**
酒店 ID 仅存在于 React 组件闭包中 — 要导航到详情页，你需要点击卡片（坐标点击）或抓取酒店名称后通过其他方式解析 ID（例如逐步建立的映射）。

```js
// 列表提取 — 通过 js(...) 在浏览器中运行
return Array.from(document.querySelectorAll(".list-item")).slice(0, 30).map(card => {
  const text = (card.innerText || "").replace(/\s+/g, " ");
  const name = text.match(/^([^\s]{2,40}?(?:酒店|宾馆|公寓|民宿)(?:\([^)]*\))?)/)?.[1];
  const score = text.match(/[1-5]\.\d/)?.[0];
  // 在提取价格前先去除 "1,234条点评"，否则 ¥1 会从 "1,234" 中泄漏
  const priced = text.replace(/\d{1,3}(?:,\d{3})+/g, "").replace(/\d+条点评/g, "");
  const prices = (priced.match(/¥\s*(\d{2,})/g) || []).map(s => parseInt(s.replace(/[^\d]/g, "")));
  const [original, current] = prices;
  return {name, score, price_original: original ?? null, price_current: current ?? null};
});
```

**陷阱**：像 `1,234条点评` 和 `5,678条点评` 这样的评论数会在你不先去除的情况下匹配 `¥\s*\d+` — `¥1` 和 `¥5` 会作为虚幻价格出现。在应用价格正则之前，务必先去除千分位数字和评论数。

每张卡片的文本结构：
```
<名称> [4.8] [超棒][1,994条点评] <标语> 近<区域> · <地铁站>查看地图 <房型> 订单确认后30分钟内免费取消 ... ¥<原价> ¥<现价> 起 查看详情
```

"起" 后缀表示"起步价"；实际预订价格可能因房价计划/早餐/取消政策而更高。

---

## 详情页

```
https://hotels.ctrip.com/hotel/<hotelId>.html?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD
```

登录前即可使用。服务端规范化为 `/hotels/detail/?...` 但数据相同。标题格式：`🟢 <酒店名>预订价格,联系电话位置地址【携程酒店】`
（🟢 前缀来自 `web-agent`，非携程）。

详情页渲染多个房费行，与列表页相同的 `¥原价 ¥现价` 格式。查找文本恰好为 `预订` 的 `<button>` 或 `<a>`，然后向上遍历到费率卡片。

如果访问的酒店已不存在，URL 会静默存活但显示通用标题"预订价格,联系电话位置地址【携程酒店】"且无价格 — 通过 `bodyText.match(/¥\s*\d+/) === null` 检测。

---

## 登录重定向信号

当携程判定你的会话可疑时，会重定向到：

```
https://passport.ctrip.com/user/login?backurl=...
```

登录表单会预填用户 Chrome 表单自动填充的最后一个手机号。如果看到此 URL，**不要输入凭据** — 退出并（a）通过首页表单重新启动流程（上方方式 B），这会修复 URL 参数结构不匹配，或（b）请用户交互式登录。

检测方法：
```python
if "passport.ctrip.com" in page_info()["url"]:
    raise RuntimeError("携程要求登录 — 请从首页重新启动")
```

在我们的测试中，重定向由以下情况触发：
- 访问 `/hotels/list?city=2&...`（注意：`city` 而非 `cityId`）。
- 在会话中从未加载过 `hotels.ctrip.com/` 就直接 GET。

反之，以下情况**未**触发重定向：
- 直接访问 `/hotels/list?flexType=1&cityId=2&provinceId=0&districtId=0&countryId=1&...`（即使零携程 Cookie）。
- 直接访问 `/hotel/<id>.html?...`。

因此，此门槛是基于参数结构的，而非基于行为的。参数结构正确就不需要登录流程。

---

## 全局状态 — 无需关注

`window._objAllSearchResult` 存在但在实时会话中为空。
携程的酒店数据存在于 React 组件状态中，不在 `window` 上。
**使用 DOM 提取。** 没有 `__NEXT_DATA__`、`__APOLLO_STATE__`、`window.__INITIAL_STATE__`。

---

## 陷阱

- **简化 URL（`?city=`）会重定向到登录页。** 使用规范的六参数结构或驱动首页表单。
- **首页默认标签是海外酒店。** 展示的酒店显示"暂无价格"并预选新加坡/普吉岛日期。不要从首页读取价格 — 去 `/hotels/list?...` 页面。
- **虚幻的 `¥1`、`¥5` 价格** 来自评论数正则渗透。在应用 `¥\d+` 前先去除 `\d+,\d+` 和 `\d+条点评`。
- **卡片上没有详情 URL。** 没有 `data-id`，没有 `<a>`。坐标点击是唯一可靠的导航到详情的方式（没有外部 ID 来源时）。
- **不存在的 ID 访问 `/hotel/{id}.html` 返回 200** 但只有品牌外壳无错误 — 通过正文中无价格检测。
- **搜索按钮是 `<div>`。** 与同程旅行同样的陷阱 — 坐标点击有效，`el.click()` 不可靠。
- **`hotels.ctrip.com` 是国内站。** 首页标题说"海外酒店预订"，但 `/hotels/list?countryId=1&...` 是国内的。海外版本使用 `countryId` ≠ 1（尚未映射）。

---

## 常用 cityId 值（已观测）

| 城市 | cityId |
|------|--------|
| 上海 | 2 |
| 北京 | 1 |
| 广州 | 32 |
| 深圳 | 30 |

通过驱动首页流程一次并读取规范 URL 可获取更多城市 ID。

---

## 快速开始

```python
from web_agent.helpers import new_tab, wait_for_load, js, cdp
import time, json

url = (
    "https://hotels.ctrip.com/hotels/list"
    "?flexType=1&cityId=2&provinceId=0&districtId=0&countryId=1"
    "&checkin=2026-04-29&checkout=2026-04-30"
)
tid = new_tab(url)
wait_for_load(timeout=20)
time.sleep(6)

hotels = js("""
  return Array.from(document.querySelectorAll(".list-item")).slice(0, 20).map(card => {
    const raw = (card.innerText || "").replace(/\\s+/g, " ");
    const cleaned = raw.replace(/\\d{1,3}(?:,\\d{3})+/g, "").replace(/\\d+条点评/g, "");
    const name = raw.match(/^([^\\s]{2,40}?(?:酒店|宾馆|公寓|民宿)(?:\\([^)]*\\))?)/)?.[1] || null;
    const prices = (cleaned.match(/¥\\s*\\d{2,}/g) || [])
                     .map(s => parseInt(s.replace(/[^\\d]/g, "")));
    const score = raw.match(/[1-5]\\.\\d/)?.[0] || null;
    return {name, score, price_original: prices[0] ?? null, price_current: prices[1] ?? null};
  });
""")
print(json.dumps(hotels, indent=2, ensure_ascii=False))
cdp("Target.closeTarget", targetId=tid)
```
