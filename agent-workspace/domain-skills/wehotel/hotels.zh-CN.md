# 锦江 WeHotel（`bestwehotel.com`） — 酒店数据抓取

于 2026-04-29 针对 `www.bestwehotel.com` PC 网页端实测验证。锦江集团官方直订门户，覆盖约 50 个子品牌
（锦江/J酒店/昆仑/丽笙/丽筠/丽柏/维也纳/锦江都城/白玉兰/麗枫/喆啡/希岸/IU/7天/锦江之星 等）。

---

## 概要

**三个中文酒店门户中最抓取友好的**：

- 列表页和详情页均支持匿名访问 — 无登录墙，无参数结构门槛，无 `¥?` 占位符。
- `http_get` 不工作（仅 SPA 外壳）。需要浏览器会话。
- 也不需要浏览器 Cookie — 通过 `web-agent` 打开的新标签页即可立即渲染 200+ 家酒店及价格。
- 详情页匿名显示完整的房价计划明细（多种房型 × 早餐/取消政策矩阵）。
- 对比：同程旅行强制登录才能看到任何价格；携程仅通过规范的六参数 URL 或首页驱动的流程才能工作；WeHotel 直接就能用。

---

## URL 模式

```
列表页:
  https://www.bestwehotel.com/HotelSearch/
    ?checkinDate=YYYY-MM-DD            # 注意：小写 i / d
    &checkoutDate=YYYY-MM-DD            # 注意：小写 o / d
    &cityCode=AR04567                   # WeHotel 内部字母数字代码
    &cityName=<url编码的中文>
    &queryWords=                        # 可选关键词筛选
    &extend=1,2,0,0,0,0                 # 房间,成人,儿童,...

酒店详情页:
  https://www.bestwehotel.com/HotelDetail/
    ?hotelId=JJ1888                     # JJ<数字>; "JJ" 前缀 = 锦江系列
    &checkInDate=YYYY-MM-DD             # 注意：大写 I 和 D
    &checkOutDate=YYYY-MM-DD             # 注意：大写 O 和 D
    &extend=1,2,0,0,0,0
```

**参数名大小写在列表页和详情页之间不一致。**
列表页使用 `checkinDate/checkoutDate`；详情页使用 `checkInDate/checkOutDate`。
搞错了会静默回退到默认日期。

---

## 如何到达列表页

首页表单默认目的地为上海，且有合理的默认日期，因此两种等效方式均可：

### 方式 A — 驱动首页表单

```python
from web_agent.helpers import new_tab, wait_for_load, click_at_xy, js, type_text
import time

new_tab("https://www.bestwehotel.com/")
wait_for_load(timeout=20)
time.sleep(2)

# 搜索按钮是 <div>（以及一个同坐标的兄弟 <a>）— 坐标点击有效
btn = js("""
  const b = Array.from(document.querySelectorAll('button, div, a'))
    .find(el => (el.innerText||'').trim() === '搜索' && el.offsetParent !== null);
  const r = b.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
""")
click_at_xy(btn["x"], btn["y"])
time.sleep(8)            # XHR 列表获取
```

### 方式 B — 构建规范 URL（已知 `cityCode` 时优先使用）

```python
url = (
    "https://www.bestwehotel.com/HotelSearch/"
    "?checkinDate=2026-04-30&checkoutDate=2026-05-01"
    "&cityCode=AR04567&cityName=%E4%B8%8A%E6%B5%B7"
    "&queryWords=&extend=1,2,0,0,0,0"
)
new_tab(url)
wait_for_load(timeout=20)
time.sleep(8)
```

WeHotel 在你省略 `provinceId/districtId/countryId` 样式参数时**不会**重定向到登录页（与携程不同）。`cityCode` 单独就足够了。

---

## 列表页 — 提取酒店

可靠路径：从 `查看详情` `<a>` 标签向上回溯。每张卡片会产出**三个**具有相同 `hotelId` href 但不同 innerText 的 `<a>`：空的、酒店名称、和 `查看详情`。向上遍历到包含所有三个的最小祖先。

```js
return Array.from(document.querySelectorAll("a[href*=HotelDetail]"))
  .filter(a => (a.innerText || "").trim() === "查看详情")
  .slice(0, 30)
  .map(detailA => {
    const id = (detailA.href.match(/hotelId=([A-Z]+\d+)/i) || [])[1];

    // 向上遍历到包含酒店名 <a> 的最小容器
    //（与 hotelId href 共享但文本不是 "查看详情" 的锚点 — 文本在链接体上，
    // 不在 href 中，所以按锚点身份/innerText 筛选，而非属性选择器）
    let card = detailA.parentElement;
    const hasNameAnchor = (el) =>
      Array.from(el.querySelectorAll("a[href*='" + id + "']"))
        .some(a => a !== detailA && (a.innerText || "").trim() && (a.innerText || "").trim() !== "查看详情");
    while (card && !hasNameAnchor(card)) {
      card = card.parentElement;
    }
    if (!card) return null;

    const text = (card.innerText || "").replace(/\s+/g, " ");
    const name = text.match(/(?:\d+\s+)?([^\s]{2,40}?(?:酒店|宾馆|大酒店|饭店))/)?.[1] || null;
    const score = text.match(/(\d\.\d)\s*\/\s*5/)?.[1] || null;
    const grade = (text.match(/(豪华型|高档型|舒适型|经济型)/) || [])[1] || null;
    const distance = (text.match(/距离市中心\s*([\d.]+)\s*km/) || [])[1] || null;
    const fromPrice = (text.match(/(?:¥|￥)\s*(\d+)\s*起/) || [])[1] || null;
    const address = (text.match(/地址：([^|]+?)距离/) || [])[1]?.trim() || null;
    const amenities = (text.match(/(停车场|餐厅|新店|游泳池|健身房|wifi)/g) || []).slice(0, 5);

    return {
      hotelId: id,
      name, score, grade, distance, address,
      price_from: fromPrice ? parseInt(fromPrice) : null,
      amenities,
    };
  })
  .filter(x => x && x.hotelId);
```

页面通过 `查询到 N 家酒店` 显示总数。

### 卡片字段结构（已观测）

```
<序号>
<酒店名称>
地址：<完整地址>
距离市中心 X.X km
<评分>/5分
<等级>            # 豪华型/高档型/舒适型/经济型
<设施标签>         # 停车场/餐厅/新店/...
￥<价格>起
查看详情
```

---

## 详情页 — 提取房型价格

详情页显示扁平表格：`房型 | 早餐 | 取消政策 | 人数上限 | 房价 | <预订按钮>`。
每行包含房价计划和单个 `¥<价格>`（没有原价/折扣三元组 — 列表价格已经是"起步价"）。

```js
const rows = Array.from(document.querySelectorAll("[class*=room], [class*=Room]"))
  .filter(el => (el.innerText || "").includes("立即预订") || (el.innerText || "").includes("￥"))
  .slice(0, 30);

return rows.map(row => {
  const text = (row.innerText || "").replace(/\s+/g, " ");
  return {
    room_type: text.match(/^(\S+(?:大床房|双床房|套房|标间|双人房)\S*)/)?.[1] || null,
    breakfast: text.match(/(无早餐|含早餐|含\d份早餐|\d份早餐)/)?.[1] || null,
    cancel: text.match(/(限时取消|免费取消|不可取消|订单确认后\d+分钟内可免费取消)/)?.[1] || null,
    price: parseInt((text.match(/(?:¥|￥)\s*(\d+)/) || [])[1] || "0"),
    full: text.slice(0, 200),
  };
}).filter(r => r.price > 0);
```

标题模式：保持为 `🟢 锦江酒店WeHotel官网`（测试框架的 🟢 前缀）。酒店名称在页面正文中，不在标题中 — 通过页面头部提取，使用通用 `[class*=name]` 或 `[class*=title]` 选择器。

---

## 品牌矩阵（WeHotel 旗下）

WeHotel 覆盖所有锦江集团品牌。在筛选或猜测 hotelId 前缀时有用：

```
LUXURY（奢华尊选）:    J酒店, 昆仑
PREMIUM（高端甄选）:   锦江, 丽笙精选, 丽笙, 丽筠, 丽芮, 暻阁, 郁锦香, 丽柏, Park Plaza
QUALITY（精品优选）:   维也纳国际/酒店/智好/3好, 非繁云居, Park Inn, Renjoy, 锦江都城, 凯里亚德, Lavande
ESSENTIALS（舒适智选）: 锦江之星(品尚/风尚), 7天酒店, 7天优品, IU酒店, 派酒店, 白玉兰, 康铂, 麗枫, 喆啡, 希岸, 潮漫
```

所有这些品牌均可通过相同的 `/HotelDetail/?hotelId=JJ<n>` URL 预订。

---

## 全局状态 — 无可用

`window.__INITIAL_STATE__`、`__NUXT__`、`__NEXT_DATA__`、`__APOLLO_STATE__` 均不存在。酒店数据通过 XHR 加载到 Vue/React 组件状态中，未暴露在 `window` 上。**使用 DOM 提取。**

---

## 陷阱

- **列表页是 `checkinDate`（小写 i），详情页是 `checkInDate`（大写 I）。**
  混淆会导致静默回退到默认日期。始终从本文档复制而非手动输入。
- **`cityCode` 是字母数字，不是纯数字。** 上海 = `AR04567`。没有明显的映射 — 通过首页表单获取一次并缓存。
- **卡片有 3 个相同 href 的 `<a>`。** 第一个是空的（图片链接），第二个是名称，第三个是 `查看详情`。按 innerText 筛选去重。
- **首页默认日期每日变化。** 不要信任表单预填日期 — 通过 URL 显式设置或在点击搜索前填写表单。
- **"价格区间-"筛选** 在正文文本中是 UI 元素，不是数据 — 不要意外从中提取 `¥?`。

---

## 快速开始

```python
import time, json
from web_agent.helpers import new_tab, wait_for_load, js, cdp

url = (
    "https://www.bestwehotel.com/HotelSearch/"
    "?checkinDate=2026-04-30&checkoutDate=2026-05-01"
    "&cityCode=AR04567&cityName=%E4%B8%8A%E6%B5%B7"
    "&queryWords=&extend=1,2,0,0,0,0"
)
tid = new_tab(url)
wait_for_load(timeout=20)
time.sleep(8)

hotels = js(r"""
  return Array.from(document.querySelectorAll("a[href*=HotelDetail]"))
    .filter(a => (a.innerText||"").trim() === "查看详情")
    .slice(0, 30)
    .map(detailA => {
      const id = (detailA.href.match(/hotelId=([A-Z]+\d+)/i) || [])[1];
      let card = detailA.parentElement;
      while (card && !card.querySelector(`a[href*='${id}']:not(:where([href*='%E6%9F%A5%E7%9C%8B%E8%AF%A6%E6%83%85']))`)) {
        card = card.parentElement;
        if (!card) break;
      }
      if (!card) return null;
      const text = (card.innerText || "").replace(/\s+/g, " ");
      return {
        hotelId: id,
        name:  text.match(/(?:\d+\s+)?([^\s]{2,40}?(?:酒店|宾馆|大酒店|饭店))/)?.[1] || null,
        score: text.match(/(\d\.\d)\s*\/\s*5/)?.[1] || null,
        grade: (text.match(/(豪华型|高档型|舒适型|经济型)/) || [])[1] || null,
        distance_km: parseFloat((text.match(/距离市中心\s*([\d.]+)/) || [])[1] || "0"),
        price_from: parseInt((text.match(/(?:¥|￥)\s*(\d+)\s*起/) || [])[1] || "0") || null,
      };
    })
    .filter(x => x && x.hotelId && x.name);
""")
print(json.dumps(hotels, indent=2, ensure_ascii=False))
cdp("Target.closeTarget", targetId=tid)
```
