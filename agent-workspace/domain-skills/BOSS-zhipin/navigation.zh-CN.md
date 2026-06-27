# BOSS直聘 — 站点导航与结构

于 2026-05-01 针对 zhipin.com 实测验证。

---

## URL 模式

| 页面 | URL |
|------|-----|
| 首页（重定向到城市页） | `https://www.zhipin.com/` → `https://www.zhipin.com/{city}/` |
| 职位搜索 | `https://www.zhipin.com/web/geek/jobs` |
| 公司搜索 | `https://www.zhipin.com/gongsi/` |
| 消息 / 聊天 | `https://www.zhipin.com/web/geek/chat` |
| 个人中心 | `https://www.zhipin.com/web/geek/recommend` |

### 特色频道

| 页面 | URL |
|------|-----|
| 校园招聘 | `https://www.zhipin.com/school/` |
| 海归 | `https://www.zhipin.com/returnee_jobs/` |
| 海外职位 | `https://www.zhipin.com/overseas/` |
| 无障碍专区 | `https://www.zhipin.com/accessible_job/` |
| 有了（职业社区） | `https://youle.zhipin.com/recommend/selected/` |

---

## 顶部导航栏

```
BOSS直聘 | 首页 | 职位 | 公司 | 校园 | 海归 | APP | 有了 | 海外 | 无障碍专区
```

始终可见。第一项（BOSS直聘 Logo）链接到根域名。

---

## 用户菜单（需要登录）

顶部栏右侧的下拉菜单。登录后显示用户真实姓名。菜单项包括：

- 消息 — 与招聘者聊天
- 简历 — 简历管理
- 升级VIP — 付费会员
- 规则中心 — 平台规则
- 切换为招聘者/切换为求职者 — 求职者与招聘者之间的**双模式切换**

---

## 首页

根 URL 根据 IP 重定向到城市页面（如 `/shanghai/`）。显示行业分类选择器和推荐职位。

### 行业分类（一级）

互联网/AI, 电子/电气/通信, 产品, 客服/运营, 销售, 人力/行政/法务, 财务/审计/税务, 生产制造 等。

每个分类可展开到子专业（如 互联网/AI → Java, Python, 前端, AI工程师...）。

### 搜索栏

```python
"input[placeholder='搜索职位、公司']"
```

---

## 注意事项

- **根 URL 重定向到城市页** — `zhipin.com` → `zhipin.com/{city}/` 基于 IP 定位。导航后务必检查最终 URL。
- **双模式账户** — 同一账户可在求职者和招聘者之间切换。UI 完全不同。
- **搜索基于 SPA** — `/web/geek/jobs` 使用客户端路由。URL 参数不反映当前筛选状态。
- **城市标识为拼音** — `/shanghai/`、`/beijing/`、`/shenzhen/`、`/hangzhou/` 等（英文音译，非中文字符）。注意：职位搜索 API 使用数字城市代码（如 `city=101020100`），而非拼音标识 — 详见 job-search.md 中的城市代码表。
- **`wait_for_load()` 可能不够** — 重型 SPA，请额外添加 `wait(2)` 等待水合完成。
