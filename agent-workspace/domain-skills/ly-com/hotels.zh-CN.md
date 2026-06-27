# 同程旅行（ly.com / 同程旅行） — 酒店数据抓取

于 2026-04-29 针对 PC 网页端（`www.ly.com`）实测验证。移动端 H5 路径尚未映射。以下所有内容均为 PC 端，除非另有说明。

---

## 概要

**价格需要登录才能查看。酒店元数据无需登录。**

- 列表页在结果 URL 中返回 `prc=null&cury=null`，并在用户登录前将每个价格渲染为字面字符串 `￥？`。
- 登录后（Cookie 保存在用户的 Chrome 中），相同的 DOM 节点渲染真实数字（`¥259 ¥200 ¥59` 三元组 — 见*价格三元组结构*）。
- 酒店名称/地址/地铁/星级/英文名/开业+装修日期可在登录前从 `window.__NUXT__` SSR 状态中获取。

**实际影响**：`http_get` 对价格无效。你需要浏览器会话和已登录的用户。`web-agent` 连接到用户的日常 Chrome 是最省事的方式 — 一旦他们通过 `passport.ly.com` 登录一次，Cookie 就会在各次运行间保持。

---

## URL 模式

```
列表页:
  https://www.ly.com/hotel/hotellist?city=<cityId>&inDate=YYYY-MM-DD&outDate=YYYY-MM-DD

酒店详情页:
  https://www.ly.com/hotel/hoteldetail?hotelId=<hotelId>&inDate=YYYY-MM-DD&outDate=YYYY-MM-DD

登录页（含返回 URL）:
  https://passport.ly.com/?pageurl=<url编码的目标地址>
```

`cityId` 是同程旅行的内部 ID，不是国标编码。上海 = `321`。通过首页运行搜索即可获取 — 重定向 URL 中包含它。

`hotelId` 是每个酒店的稳定标识。观测范围：8 位数字（如 `92963586`、`50201258`、`93067902`）。

列表页也接受 `&keyword=`、`&star=` 等，但 `/hotel/` 上的表单字段是规范入口 — 填写它们或点击搜索 div 让 SPA 构建 URL。

### 移动端 H5 — 请勿使用（测试中返回 404）

- `https://m.ly.com/scenery/hotel/<hotelId>` — 404
- `https://hotelh5.ly.com/...` — 尚未映射

如需移动端路径，请从 `m.ly.com/` 搜索而非猜测。

---

## 搜索按钮不是 `<button>`

在 `https://www.ly.com/hotel/` 上，绿色的"搜索"按钮是 `<div>`，不是 `<button>` 或 `<a>`。通过 `element.click()` 的 JS 点击**不会**可靠触发 SPA 处理程序。两种可行方案：

1. **坐标点击**（首选 — 与其余测试框架形式一致）：
   ```python
   from web_agent.helpers import js, click_at_xy
   btns = js("""
     return Array.from(document.querySelectorAll("div"))
       .filter(el => (el.innerText||"").trim() === "搜索")
       .map(el => { const r = el.getBoundingClientRect();
                    return {x: r.x+r.width/2, y: r.y+r.height/2}; });
   """)
   click_at_xy(btns[0]["x"], btns[0]["y"])
   ```

2. **直接 URL 导航**（完全跳过表单）：自行构建 `/hotel/hotellist?city=<id>&inDate=...&outDate=...` URL。

点击后，列表通过 XHR 渲染。页面显示加载文字"正在搜寻更多住宿……" — 提取卡片前等待约 5-7 秒。

---

## 列表页 — 提取酒店

酒店卡片是 `<a>` 元素，类名为 `listBox`（Tailwind 混淆后的类名，完整类名字符串可能是 `mb-[20px] flow-root listBox` 或类似 — 使用 `a[class*=listBox]` 匹配）。

```js
Array.from(document.querySelectorAll("a[class*=listBox]")).slice(0, 20).map(a => {
  const href = a.href;
  const m = href.match(/hotelId=(\d+)/);
  return {
    hotelId: m ? m[1] : null,
    href,
    text: (a.innerText || "").replace(/\s+/g, " ").slice(0, 200),
  };
});
```

卡片 `innerText` 以竖线分隔，包含：酒店名称、星级、评分（4.x）、评论数、设施标签、区域/地铁，然后未登录时为 `￥？ 查看详情`（或登录后从列表页为 `¥<n> 预订` — 但列表页通常仍然隐藏价格，只有详情页可靠显示）。

`href` 包含冗长的 `traceToken` 查询参数，重新导航时可以丢弃；只有 `hotelId`、`inDate`、`outDate` 有意义。

---

## 详情页 — Nuxt SSR 状态

网站基于 Nuxt.js 构建。登录前的数据位于：

```
window.__NUXT__.data["$<随机哈希>"]   // 每次页面加载不同，不稳定
```

数据对象每次页面加载恰好包含两个键。第一个（`$VKSoZS1qt0` 样式）保存页面外壳（头部/底部/CSS）；第二个保存实际的酒店负载。按结构查找，而非按键名：

```js
const dataMap = window.__NUXT__?.data || {};
const hotelEntry = Object.values(dataMap).find(v => v && v.hotelData);
// 优先使用公开的 Vue ref API（`.value`）；仅在未来的 Vue/Nuxt 构建改变解包结构时
// 回退到 `_rawValue`
const meta = hotelEntry?.hotelData?.value ?? hotelEntry?.hotelData?._rawValue;
// meta 现在包含: hotelid, hotelName, hotelNameEn, hotelAddress,
// nearestAreaPosition, hotelArea, starLevel, headPicUrl
```

`detailBaseInfo.value` 额外包含：`openDate`、`decorateDate`、`featureInfo`（散文段落）和完整地址。

**价格不在 `__NUXT__` 中。** 它们在水合后通过单独的 XHR 加载。这是服务端限制，不是客户端隐藏 — 在用户认证之前，价格字段在 SSR 负载中字面上不存在。

---

## 价格提取（已登录）

每个房型/费率卡片包含一个 `预订` 按钮（`<button>` 或 `<a>` — 可见性判断为 `offsetParent !== null`）。向上遍历到 `innerText.length > 80` 的最小祖先元素来获取卡片。

### 价格三元组结构

每个可见的价格块在 DOM 顺序中是一个三元组：

```
[¥<原价>] [¥<会员价>] [¥<节省金额>]
```

对于"至尊·大床房 (无餐食)"房型，我们观测到 `¥259 ¥200 ¥59`。折扣始终是 `原价 - 会员价`，因此可以在正则捕获到邻近元素杂散 `¥` 时用作合理性校验。

```js
const text = card.innerText.replace(/\s+/g, " ");
const nums = (text.match(/¥\s*\d+(?:\.\d+)?/g) || [])
              .map(s => parseFloat(s.replace(/[^\d.]/g, "")));
const [original, current, saved] = nums;
// 校验: Math.abs((original - current) - saved) < 1
```

卡片文本中其他有用字段：
- `无餐食` / `1份早餐` / `2份早餐` — 餐食方案
- `订单确认30分钟内可免费取消` — 取消政策
- `可开专票` — 增值税发票
- 房型名称通常在卡片头部，跟在 `套餐` 之后；面积写作 `<n>-<m>㎡`

"房间"标签是默认着陆标签。如果页面落在其他位置，滚动到约 `y=1400`（相对于 720 视口下 6900 高的文档）或点击 `房间` 标签 DOM 元素使房型进入视野。

---

## 登录流程

登录 URL 接受 `pageurl` 查询参数，使用户登录后返回原始页面：

```python
new_tab(f"https://passport.ly.com/?pageurl={urllib.parse.quote(target_url)}")
```

检测 — 当活跃 URL 离开 `passport.ly.com` 域名时登录完成。每 3 秒轮询 `page_info()`；在以下条件满足时退出：

```python
url = page_info()["url"]
done = "passport.ly.com" not in url and "login" not in url.lower()
```

> 陷阱：当用户在登录页上（尤其是切换标签页/滑动 QR 码步骤时），`page_info()` 可能暂时报错 "Cannot read properties of null (reading 'scrollWidth')" — 文档 body 尚未就绪。用 try/except 包裹每次轮询并继续。

`passport.ly.com` 设置的 Cookie 作用域为 `.ly.com`，保存在用户的 Chrome 配置中。它们在 `web-agent` 运行和 Chrome 重启后仍然有效。无需每次会话重新登录。

---

## 需关注的 XHR（尚未逆向工程）

我们观测到但未捕获：

- 一个价格获取 XHR 在详情页的 Nuxt 水合后触发；它似乎依赖于 `.ly.com` 认证 Cookie 进行门控。逆向工程此请求可以让你在拥有有效 Token 后完全跳过浏览器，但该请求几乎确定携带防重放签名。
- 一个列表页价格填充 XHR 在初始渲染后触发（卡片 URL 中的 `prc=null` 是占位符）。

在这些被映射之前，**优先使用 DOM 提取而非网络嗅探。**

---

## 陷阱

- **`￥？` 是真实的 DOM 内容，不是 CSS 占位符。** 不要浪费时间寻找隐藏元素或计算样式 — 服务端只是不给未认证请求发送价格。
- **`m.ly.com/scenery/hotel/<id>`** 返回 404。不要在未验证的情况下模式匹配移动端 URL。
- **`__NUXT__` 数据键在每次页面加载时随机化**（`$VKSoZS1qt0`、`$0GffEk0IYv` 等）。遍历值并按结构检测（存在 `hotelData`），不要硬编码键名。
- **`__NUXT__.data.X.hotelData` 是 Vue ref。** 读取 `_rawValue`（或 `_value`）；两者包含相同数据。不要尝试直接 `JSON.stringify` ref — 循环引用会导致爆炸。
- **"搜索"按钮是 `<div>`，不是 button。** `el.click()` 不会触发 SPA — 使用坐标点击或直接构建列表 URL。
- **"未来"日期**（如 `inDate=2099-01-01`）会静默强制为下一个可用夜晚 — 不要依赖回显输入值。

---

## 快速开始（已登录用户，测试框架已连接）

```python
from urllib.parse import quote
import time, json
from web_agent.helpers import new_tab, wait_for_load, js, page_info, cdp

HOTEL_ID = "92963586"   # 和颐至尊酒店(上海新国际博览中心世博园店)
url = f"https://www.ly.com/hotel/hoteldetail?hotelId={HOTEL_ID}&inDate=2026-04-29&outDate=2026-04-30"

tid = new_tab(url)
wait_for_load(timeout=20)
time.sleep(4)            # XHR 价格获取
js("window.scrollTo(0, 1400)")
time.sleep(2)

rooms = js("""
  const buttons = Array.from(document.querySelectorAll("button, a, div"))
    .filter(el => (el.innerText||"").trim() === "预订" && el.offsetParent !== null);
  const out = [], seen = new Set();
  for (const btn of buttons) {
    let card = btn.parentElement;
    while (card && card.innerText.length < 80) card = card.parentElement;
    if (!card) continue;
    const k = card.innerText.slice(0, 50);
    if (seen.has(k)) continue;
    seen.add(k);
    const text = card.innerText.replace(/\\s+/g, " ");
    const nums = (text.match(/¥\\s*\\d+(?:\\.\\d+)?/g) || [])
                   .map(s => parseFloat(s.replace(/[^\\d.]/g, "")));
    out.push({
      summary: text.slice(0, 120),
      price_original: nums[0] ?? null,
      price_current:  nums[1] ?? null,
      saved:          nums[2] ?? null,
    });
    if (out.length >= 10) break;
  }
  return out;
""")
print(json.dumps(rooms, indent=2, ensure_ascii=False))
cdp("Target.closeTarget", targetId=tid)
```
