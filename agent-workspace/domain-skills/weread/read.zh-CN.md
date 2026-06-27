# 微信读书 — 自动阅读

于 2026-05-06 针对 weread.qq.com 实测验证。
阅读功能需要微信登录。

---

## 核心流程

```
步骤1：检查登录状态
    ├── 未登录 → 提示用户扫码 → 等待登录完成
    └── 已登录 → 进入步骤2

步骤2：检查阅读进度
    ├── 无进度或已读完 → 从新书榜选第一本书 → 记录状态 → 进入步骤3
    └── 有未读完的书 → 继续阅读 → 进入步骤3

步骤3：自动阅读（每次1分钟）
    ├── 每3-5秒向下滚动100px
    ├── 看到"下一章" → 点击，继续阅读
    ├── 看到"全书完" + "标记读完" → 点击标记读完 → 记录状态为已读完
    └── 时间到 → 保存进度，等待下次阅读
```

---

## URL 模式

| 页面 | URL |
|------|-----|
| 首页 | `https://weread.qq.com/` |
| 飙升榜 | `https://weread.qq.com/web/category/rising` |
| 热搜 | `https://weread.qq.com/web/category/hot_search` |
| 新书榜 | `https://weread.qq.com/web/category/newbook` |
| 图书详情 | `https://weread.qq.com/web/bookDetail/{BOOK_ID}` |
| 阅读器 | `https://weread.qq.com/web/reader/{BOOK_ID}k{CHAPTER_HASH}` |

### 阅读器 URL 模式

```
https://weread.qq.com/web/reader/{BOOK_ID}k{CHAPTER_HASH}
```

- `BOOK_ID` — 唯一图书标识（如 `ee0320b053b925ee0519857`）
- `CHAPTER_HASH` — 章节哈希值（如 `08432c902c4084b6fbb18c9`）
- 直接访问 URL 可跳转到指定章节

---

## 步骤1：登录流程

### 登录检测

```python
# 检查是否需要登录
login_needed = js("""
    const loginBtn = document.querySelector('[class*=login], [class*=Login]');
    const qrCode = document.querySelector('[class*=qrcode], [class*=QRCode]');
    return !!(loginBtn || qrCode);
""")
```

### 登录过程

1. 导航到 `https://weread.qq.com/`
2. 页面显示二维码登录提示
3. 用户使用微信手机 App 扫描二维码
4. 扫码成功后页面自动跳转到首页
5. 登录状态持久化 — 无需重新登录

### 等待登录完成

```python
# 等待登录完成
import time

def wait_for_login(timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        # 检查是否仍在登录页
        on_login = js("""
            const loginBtn = document.querySelector('[class*=login], [class*=Login]');
            return !!loginBtn;
        """)
        if not on_login:
            return True
        time.sleep(2)
    return False
```

---

## 步骤2：阅读进度管理

### progress.json 结构

```json
{
  "book": {
    "title": "书名",
    "author": "作者",
    "url": "当前章节 URL"
  },
  "progress": {
    "status": "reading | finished",
    "currentChapter": "章节名称",
    "completedChapters": ["章节列表"],
    "lastReadTime": "2026-05-06"
  }
}
```

### 加载进度

```python
import json
import os

PROGRESS_FILE = "progress.json"

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return None
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
```

### 保存进度

```python
def save_progress(book_title, author, url, chapter, completed_chapters, status="reading"):
    progress = {
        "book": {
            "title": book_title,
            "author": author,
            "url": url
        },
        "progress": {
            "status": status,
            "currentChapter": chapter,
            "completedChapters": completed_chapters,
            "lastReadTime": time.strftime("%Y-%m-%d")
        }
    }
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
```

### 检查阅读状态

```python
def should_pick_new_book():
    progress = load_progress()
    if progress is None:
        return True  # 从未阅读过
    if progress["progress"]["status"] == "finished":
        return True  # 已读完
    return False  # 有未读完的书
```

### 从新书榜选书

```python
def pick_book_from_new_ranking():
    # 导航到新书榜
    new_tab("https://weread.qq.com/web/category/newbook")
    wait_for_load()
    time.sleep(2)

    # 滚动到顶部
    js("window.scrollTo(0, 0)")
    time.sleep(1)

    # 点击第一本书
    first_book = js("""
        const allElements = document.querySelectorAll("[class*=title]");
        for (const el of allElements) {
            const text = el.textContent.trim();
            if (text.length > 3 && text.length < 50 && !text.includes("榜")) {
                const rect = el.getBoundingClientRect();
                return {
                    title: text,
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2
                };
            }
        }
        return null;
    """)

    if first_book:
        click_at_xy(first_book["x"], first_book["y"])
        wait_for_load()
        time.sleep(1)

    return first_book["title"] if first_book else None
```

---

## 步骤3：自动阅读

### 滚动阅读

```python
import random

def scroll_reading(duration=360):
    start_time = time.time()
    chapters_read = []

    while time.time() - start_time < duration:
        # 向下滚动100px
        js("window.scrollBy(0, 100)")

        # 随机等待3-5秒
        wait_time = random.uniform(3, 5)
        time.sleep(wait_time)

        # 检查"下一章"按钮是否可见
        next_chapter = find_next_chapter_button()
        if next_chapter and next_chapter["visible"]:
            # 记录当前章节
            current = get_current_chapter()
            chapters_read.append(current)
            # 点击下一章
            click_at_xy(next_chapter["x"], next_chapter["y"])
            wait_for_load()
            time.sleep(1)
            continue

        # 检查是否"全书完"并有"标记读完"
        finished = check_book_finished()
        if finished:
            click_mark_finished()
            return chapters_read, True  # True = 书已读完

    return chapters_read, False  # False = 时间到，书未读完
```

### 查找下一章按钮

```python
def find_next_chapter_button():
    buttons = js("""
        const items = [];
        const elements = document.querySelectorAll("button, a, [role=button], [class*=next], [class*=Next]");
        elements.forEach(el => {
            const text = el.textContent.trim();
            if (text.includes("下一章")) {
                const rect = el.getBoundingClientRect();
                items.push({
                    text: text,
                    x: rect.x + rect.width/2,
                    y: rect.y + rect.height/2,
                    visible: rect.top < window.innerHeight && rect.bottom > 0
                });
            }
        });
        return items;
    """)
    return buttons[0] if buttons else None
```

### 获取当前章节

```python
def get_current_chapter():
    return js("""
        const title = document.title;
        const parts = title.split(" - ");
        return parts.length > 1 ? parts[1] : "未知章节";
    """)
```

### 检查书籍是否读完

```python
def check_book_finished():
    return js("""
        const elements = document.querySelectorAll("[class*=finish], [class*=complete], [class*=end]");
        for (const el of elements) {
            const text = el.textContent.trim();
            if (text.includes("全书完") || text.includes("已读完")) {
                return true;
            }
        }
        return false;
    """)
```

### 点击标记读完

```python
def click_mark_finished():
    button = js("""
        const elements = document.querySelectorAll("button, [role=button]");
        for (const el of elements) {
            const text = el.textContent.trim();
            if (text.includes("标记读完") || text.includes("标记已读")) {
                const rect = el.getBoundingClientRect();
                return {x: rect.x + rect.width/2, y: rect.y + rect.height/2};
            }
        }
        return null;
    """)
    if button:
        click_at_xy(button["x"], button["y"])
        wait_for_load()
        time.sleep(1)
```

---

## 注意事项

- **持久登录** — 首次扫码后无需重新登录，除非清除浏览器数据。
- **"下一章"按钮位置** — 按钮在页面底部；点击前需先滚动到可视区域。
- **滚动间隔** — 3-5秒随机间隔模拟真实阅读；滚动过快可能触发检测。
- **章节 URL 变化** — 每个章节有唯一的 URL 哈希；保存完整 URL 可精确恢复阅读位置。
- **书籍读完检测** — 部分书籍可能缺少"全书完"提示；需根据实际情况调整检测逻辑。
- **新书榜首本选择** — 排名顺序可能变化；始终实时获取第一本书。
