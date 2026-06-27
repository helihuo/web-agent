# BOSS直聘 — 职位搜索与提取

于 2026-05-01 针对 zhipin.com 实测验证。
访问 API 需要登录；浏览职位无需登录。
最近浏览器验证：2026-05-01（所有功能已针对线上网站重新测试）。

---

## 反爬虫 / API 结论

BOSS直聘是 Vue SPA。没有 SSR JSON 数据块（`__NEXT_DATA__`、`__INITIAL_STATE__` 等）— 所有数据通过 XHR/fetch 加载到内部 `/wapi/` 接口。

**`http_get` 无法使用** — `/wapi/` 接口需要浏览器会话 Cookie（不仅仅是 CSRF Token）。所有 API 调用必须通过浏览器会话内的 `js()` + `fetch()` 进行。

**但是，API 返回真实薪资数字**（`"salaryDesc": "18-22K"`），而 DOM 通过自定义 `@font-face` 使用私有区 Unicode 字符（U+E000–U+F8FF）来渲染薪资数字。**始终优先使用 API 而非 DOM 提取。**

---

## 快速开始

```python
import json

goto_url("https://www.zhipin.com/web/geek/jobs?ka=open_joblist")
wait_for_load()
wait(3)

jobs = json.loads(js("""
(async function() {
    var r = await fetch('/wapi/zpgeek/pc/recommend/job/list.json?page=1&pageSize=15&city=101020100');
    var d = await r.json();
    if (d.code !== 0 || !d.zpData) { return JSON.stringify([]); }
    return JSON.stringify(d.zpData.jobList || []);
})()
"""))

for j in jobs:
    print(j["salaryDesc"], j["jobName"], "|", j["brandName"])
```

---

## URL 模式

| 资源 | URL |
|------|-----|
| 职位搜索页 | `https://www.zhipin.com/web/geek/jobs` |
| 职位搜索（含偏好） | `https://www.zhipin.com/web/geek/jobs?ka=open_joblist` |
| 职位详情页 | `https://www.zhipin.com/job_detail/{JOB_ID}.html` |
| 公司页面 | `https://www.zhipin.com/gongsi/{COMPANY_ID}~.html` |

---

## API：职位列表

```
GET /wapi/zpgeek/pc/recommend/job/list.json
```

### 查询参数

| 参数 | 说明 | 取值 |
|------|------|------|
| `page` | 页码 | 1-N |
| `pageSize` | 每页结果数 | 15（默认） |
| `city` | 城市代码 | `101020100` = 上海, `101010100` = 北京, `101280100` = 广州 |
| `experience` | 经验筛选代码 | `0`=不限, `104`=1-3年, `105`=3-5年, `106`=5-10年 |
| `degree` | 学历筛选代码 | `0`=不限 |
| `salary` | 薪资筛选代码 | `0`=不限, `405`=10-20K, `406`=20-50K |
| `industry` | 行业筛选代码 | （数字） |
| `scale` | 公司规模筛选代码 | `0`=不限, `303`=100-499人, `305`=1000-9999人 |
| `jobType` | 职位类型 | `0`=不限, `1`=全职, `2`=兼职 |
| `encryptExpectId` | 已保存的偏好 ID | 来自用户已保存的偏好（空字符串 = 默认） |
| `mixExpectType` | 混合期望类型 | （空字符串为默认） |
| `expectInfo` | 期望信息 | （空字符串为默认） |

筛选代码来自 `/wapi/zpgeek/pc/all/filter/conditions.json`。
在没有有效 `encryptExpectId` 的情况下将 `experience`、`salary` 或 `degree` 设为非零值可能返回空结果。页面在 API 调用中始终发送所有筛选参数（即使为空）。

### 响应（`zpData.jobList[]`）

```python
{
    "securityId": "nbyXZvE4kfp6Y...",     # 用于详情 API 的不透明 ID
    "encryptJobId": "cbcbfca3...",          # 职位详情页 ID
    "encryptBossId": "37a64419...",         # 招聘者 ID
    "jobName": "Aone/GitHub开发工程师",
    "salaryDesc": "18-22K",                 # 真实薪资 — 非字体编码
    "jobLabels": ["3-5年", "本科", "Java", "Golang"],
    "skills": ["Java", "Golang", "Aone", "GitLab"],
    "jobExperience": "3-5年",
    "jobDegree": "本科",
    "cityName": "上海",
    "areaDistrict": "浦东新区",
    "businessDistrict": "张江",
    "brandName": "软通动力",
    "brandIndustry": "计算机软件",
    "brandScaleName": "10000人以上",
    "brandStageName": "未融资",
    "bossName": "杨女士",
    "bossTitle": "人事",
    "bossOnline": false,
    "bossAvatar": "https://img.bosszhipin.com/...",
    "brandLogo": "https://img.bosszhipin.com/...",
    "welfareList": [],
    "gps": {"longitude": 121.609707, "latitude": 31.185578}
}
```

### 获取职位列表（浏览器 API）

```python
import json

def fetch_job_list(page=1, page_size=15, city="101020100", **filters):
    """从 BOSS直聘 API 获取职位。必须先在 zhipin.com 页面上。"""
    # 默认参数（与真实页面发送的一致）
    defaults = {
        "encryptExpectId": "",
        "mixExpectType": "",
        "expectInfo": "",
        "jobType": "",
        "salary": "",
        "experience": "",
        "degree": "",
        "industry": "",
        "scale": ""
    }
    defaults.update(filters)
    params = f"page={page}&pageSize={page_size}&city={city}"
    for k, v in defaults.items():
        params += f"&{k}={v}"

    raw = js(f"""
    (async function() {{
        var r = await fetch('/wapi/zpgeek/pc/recommend/job/list.json?{params}');
        var d = await r.json();
        if (d.code !== 0 || !d.zpData) {{
            return JSON.stringify({{code: d.code, hasMore: false, jobs: [], error: d.msg || 'API error'}});
        }}
        return JSON.stringify({{code: d.code, hasMore: d.zpData.hasMore, jobs: d.zpData.jobList || []}});
    }})()
    """)
    return json.loads(raw)

# 用法
result = fetch_job_list(page=1, experience=105)  # 3-5年
print(f"Total: {len(result['jobs'])} jobs, hasMore: {result['hasMore']}")
for j in result["jobs"]:
    print(f"  {j['salaryDesc']:12s} {j['jobName']:30s} {j['brandName']}")
```

### 分页

API 使用 `hasMore`（布尔值），而非总数。**基于页码的分页不可靠** — 即使 `page=1` 返回 `hasMore: true`，`page=2` 也经常返回 0 条结果。建议使用首页结果并考虑放宽筛选条件（如更小的 `pageSize`、不同城市），而不是深度翻页。

实际的职位搜索页在 `page=1` 加载一次推荐，然后通过滚动懒加载更多，这触发不同的 API 路径。对于批量提取，可以变换筛选条件（城市、经验、薪资）来获取不同的结果集：

```python
def fetch_all_jobs(city="101020100", max_pages=10):
    all_jobs = []
    for page in range(1, max_pages + 1):
        result = fetch_job_list(page=page, city=city)
        all_jobs.extend(result["jobs"])
        if not result["hasMore"] or len(result["jobs"]) == 0:
            break
        wait(0.5)  # 礼貌延迟
    return all_jobs
```

---

## API：职位详情

```
GET /wapi/zpgeek/job/detail.json?securityId={securityId}
```

使用职位列表响应中的 `securityId`（不是 `encryptJobId`）。

```python
def fetch_job_detail(security_id):
    raw = js(f"""
    (async function() {{
        var r = await fetch('/wapi/zpgeek/job/detail.json?securityId={security_id}');
        var d = await r.json();
        if (d.code !== 0 || !d.zpData) {{
            return JSON.stringify({{code: d.code, error: d.msg || 'API error'}});
        }}
        var zp = d.zpData;
        var job = zp.jobInfo;
        var boss = zp.bossInfo;
        var brand = zp.brandComInfo;
        return JSON.stringify({{
            code: d.code,
            title: job.jobName,
            salary: job.salaryDesc,
            experience: job.experienceName,
            degree: job.degreeName,
            location: job.locationName,
            address: job.address,
            gps: {{lng: job.longitude, lat: job.latitude}},
            description: job.postDescription,
            skills: job.showSkills,
            boss_name: boss.name,
            boss_title: boss.title,
            boss_avatar: boss.large,
            boss_online: boss.online,
            company_name: brand.brandName,
            company_logo: brand.logo,
            company_industry: brand.industryName,
            company_scale: brand.scaleName,
            company_stage: brand.stageName
        }});
    }})()
    """)
    return json.loads(raw)
```

---

## API：筛选条件

```
GET /wapi/zpgeek/pc/all/filter/conditions.json
```

返回所有可用的筛选选项及其数字代码：

```python
def get_filter_conditions():
    raw = js("""
    (async function() {
        var r = await fetch('/wapi/zpgeek/pc/all/filter/conditions.json');
        var d = await r.json();
        if (d.code !== 0 || !d.zpData) { return JSON.stringify({}); }
        return JSON.stringify(d.zpData);
    })()
    """)
    return json.loads(raw)

# 返回: {
#   experienceList: [{code: 105, name: "3-5年"}, ...],
#   salaryList:     [{code: 406, name: "20-50K", lowSalary: 20, highSalary: 50}, ...],
#   degreeList:     [{code: 203, name: "本科"}, ...],
#   scaleList:      [{code: 305, name: "1000-9999人"}, ...],
#   stageList:      [{code: 807, name: "已上市"}, ...],
#   industryList:   [...],
#   payTypeList:    [...],
#   partTimeList:   [...]
# }
```

---

## 城市代码

城市通过数字代码标识，而非名称：

| 城市 | 代码 |
|------|------|
| 上海 | `101020100` |
| 北京 | `101010100` |
| 深圳 | `101280200` |
| 广州 | `101280100` |
| 杭州 | `101210100` |
| 成都 | `101270100` |

要查找城市代码，可查看职位列表 API 调用中的 `city` 参数，或使用城市数据 API：

```
GET /wapi/zpgeek/common/data/city/site.json
```

---

## DOM 提取（备选方案）

如果 API 路径被阻止，可退而使用 DOM 提取。注意薪资文本使用字体编码的私有区 Unicode 字符（U+E000–U+F8FF）— DOM `textContent` 返回不可读的 PUA 码点，如 `"-K"`，而非渲染后的数字。

### 职位卡片 DOM

```
li.job-card-box
  div.job-info
    div.job-title.clearfix
      a.job-name[href="/job_detail/{ID}.html"]   — 职位名称
      span.job-salary                              — 字体编码（见上文）
    ul.tag-list
      li  — 经验 / 学历 / 技能标签
  div.job-card-footer
    a.boss-info[href="/gongsi/{ID}~.html"]
      span.boss-name                               — 公司名称
    span.company-location                          — 如 "上海·徐汇区·龙华"
```

```python
def extract_job_cards_dom():
    raw = js("""
    (function() {
        var cards = document.querySelectorAll('.job-card-box');
        var results = [];
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i];
            function getText(sel) {
                var el = card.querySelector(sel);
                return el ? el.textContent.trim() : '';
            }
            function getHref(sel) {
                var el = card.querySelector(sel);
                return el ? el.href : '';
            }
            var tags = [];
            var tagEls = card.querySelectorAll('.tag-list li');
            for (var t = 0; t < tagEls.length; t++) {
                tags.push(tagEls[t].textContent.trim());
            }
            results.push({
                title: getText('.job-name'),
                salary_raw: getText('.job-salary'),
                tags: tags,
                company: getText('.boss-name'),
                location: getText('.company-location'),
                job_url: getHref('.job-name'),
                company_url: getHref('.boss-info')
            });
        }
        return JSON.stringify(results);
    })()
    """)
    return json.loads(raw)
```

每页 15 张卡片。滚动可懒加载更多。

---

## 注意事项

- **始终优先使用 API** — `salaryDesc` 返回人类可读的薪资。DOM 薪资使用字体编码的 PUA 字符，需要 OCR 或字体文件逆向才能解码。
- **API 需要浏览器会话** — `/wapi/` 接口需要真实浏览器页面加载产生的 Cookie。使用浏览器内的 `js()` + `fetch()`，而非 Python 的 `http_get`。
- **securityId 与 encryptJobId** — 职位详情 API 使用 `securityId`（长不透明字符串），而非 `encryptJobId`。两者均来自职位列表响应。
- **`brandComInfo` 而非 `brandInfo`** — 职位详情响应使用 `zpData.brandComInfo`（不是 `brandInfo`）。公司名称是 `brandName`（不是 `companyName`），Logo 是 `logo`（不是 `brandLogo`）。行业/规模/阶段是数字代码 — 使用 `industryName`/`scaleName`/`stageName` 获取显示字符串。
- **SPA 路由** — 通过 DOM 应用筛选时 URL 不会变化。使用 API 时，筛选条件是明确的查询参数。
- **基于页码的分页不可靠** — 即使 `hasMore` 在第 1 页为 true，`page=2` 也经常返回 0 条结果。建议变换筛选条件而非深度翻页。
- **筛选参数需要上下文** — 在没有有效 `encryptExpectId` 的情况下将 `experience`、`salary` 或 `degree` 设为非零值可能返回 `code: 200404`。使用空字符串进行默认/无偏好浏览。
- **城市代码是数字** — 不是城市名称。使用筛选条件 API 或 city/site.json 查找代码。
- **`goto_url` 后需要 `wait(2-3)`** — SPA 需要时间建立会话后 API 调用才能生效。
- **反爬虫检测** — zhipin.com 可能在页面加载约 1-2 秒后重定向到 about:blank。在同一执行上下文中导航后立即运行 API 调用。
- **城市代码 101280100 = 广州，不是深圳** — 之前文档中记录为深圳的代码实际上是广州。
