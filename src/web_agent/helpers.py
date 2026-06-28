"""通过 CDP 进行浏览器控制。

核心辅助函数在此处。Agent 可编辑的辅助函数位于
WA_AGENT_WORKSPACE/agent_helpers.py。
"""
import base64, importlib.util, json, math, os, sys, time, urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import _ipc as ipc
from . import paths
from .oplog import get_session, oplog_step
from .paths import _load_env, _load_env_file


CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent.parent
AGENT_WORKSPACE = paths.workspace_dir()

_load_env()

NAME = os.environ.get("BU_NAME", "default")
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")


def truncate_text(text, limit):
    """通用文本截断：超长时截断并添加省略号。"""
    text = str(text)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _send(req):
    c, token = ipc.connect(NAME, timeout=5.0)
    try:
        r = ipc.request(c, token, req)
    finally:
        c.close()
    if "error" in r: raise RuntimeError(r["error"])
    return r


def cdp(method, session_id=None, **params):
    """原始 CDP 调用。cdp('Page.navigate', url='...'), cdp('DOM.getDocument', depth=-1)。"""
    return _send({"method": method, "params": params, "session_id": session_id}).get("result", {})


def drain_events():  return _send({"meta": "drain_events"})["events"]


def _js_snippet(expression, limit=160):
    snippet = expression.strip().replace("\n", "\\n")
    return truncate_text(snippet, limit)


def _js_exception_description(result, details):
    desc = result.get("description")
    exc = details.get("exception") if details else None
    if not desc and isinstance(exc, dict):
        desc = exc.get("description")
        if desc is None and "value" in exc:
            desc = str(exc["value"])
        if desc is None:
            desc = exc.get("className")
    if not desc and details:
        desc = details.get("text")
    return desc or "JavaScript evaluation failed"


def _decode_unserializable_js_value(value):
    if value == "NaN":
        return math.nan
    if value == "Infinity":
        return math.inf
    if value == "-Infinity":
        return -math.inf
    if value == "-0":
        return -0.0
    if value.endswith("n"):
        return int(value[:-1])
    return value


def _runtime_value(response, expression):
    result = response.get("result", {})
    details = response.get("exceptionDetails")
    if details or result.get("subtype") == "error":
        desc = _js_exception_description(result, details)
        if details:
            line = details.get("lineNumber")
            col = details.get("columnNumber")
            loc = f" at line {line}, column {col}" if line is not None and col is not None else ""
        else:
            loc = ""
        raise RuntimeError(f"JavaScript evaluation failed{loc}: {desc}; expression: {_js_snippet(expression)}")
    if "value" in result:
        return result["value"]
    if "unserializableValue" in result:
        return _decode_unserializable_js_value(result["unserializableValue"])
    return None


def _runtime_evaluate(expression, session_id=None, await_promise=False):
    try:
        r = cdp("Runtime.evaluate", session_id=session_id, expression=expression, returnByValue=True, awaitPromise=await_promise)
    except TimeoutError as e:
        raise RuntimeError(f"Runtime.evaluate timed out; expression: {_js_snippet(expression)}") from e
    return _runtime_value(r, expression)


def _wrap_js_function(expression):
    return f"(function(){{{expression}}})()"


def _is_illegal_return_error(exc):
    return "Illegal return statement" in str(exc)


# --- 导航 / 页面 ---
@oplog_step
def goto_url(url):
    r = cdp("Page.navigate", url=url)
    if os.environ.get("WA_DOMAIN_SKILLS") != "1":
        return r
    d = (AGENT_WORKSPACE / "domain-skills" / (urlparse(url).hostname or "").removeprefix("www.").split(".")[0])
    return {**r, "domain_skills": sorted(p.name for p in d.rglob("*.md"))[:10]} if d.is_dir() else r

@oplog_step
def page_info():
    """{url, title, w, h, sx, sy, pw, ph} — 视口 + 滚动 + 页面尺寸。

    如果打开了原生对话框（alert/confirm/prompt/beforeunload），则返回
    {dialog: {type, message, ...}} — 页面的 JS 线程会被冻结，
    直到对话框被处理（参见 interaction-skills/dialogs.md）。"""
    dialog = _send({"meta": "pending_dialog"}).get("dialog")
    if dialog:
        return {"dialog": dialog}
    expression = "JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,pw:document.documentElement.scrollWidth,ph:document.documentElement.scrollHeight})"
    return json.loads(_runtime_evaluate(expression))

# --- 输入 ---
_debug_click_counter = 0

@oplog_step
def click_at_xy(x, y, button="left", clicks=1):
    if os.environ.get("WA_DEBUG_CLICKS"):
        global _debug_click_counter
        try:
            from PIL import Image, ImageDraw
            dpr = js("window.devicePixelRatio") or 1
            # 优先保存到 oplog 截图目录，否则保存到临时目录
            session = get_session()
            screenshot_dir = session.get_screenshot_dir()
            if screenshot_dir is not None:
                save_path = str(screenshot_dir / f"debug_click_{_debug_click_counter}.png")
            else:
                save_path = str(ipc._TMP / f"debug_click_{_debug_click_counter}.png")
            path = capture_screenshot(save_path)
            img = Image.open(path)
            draw = ImageDraw.Draw(img)
            px, py = int(x * dpr), int(y * dpr)
            r = int(15 * dpr)
            draw.ellipse([px - r, py - r, px + r, py + r], outline="red", width=int(3 * dpr))
            draw.line([px - r - int(5 * dpr), py, px + r + int(5 * dpr), py], fill="red", width=int(2 * dpr))
            draw.line([px, py - r - int(5 * dpr), px, py + r + int(5 * dpr)], fill="red", width=int(2 * dpr))
            img.save(path)
            print(f"[debug_click] saved {path} (x={x}, y={y}, dpr={dpr})")
            # 将调试截图关联到 oplog 日志（screenshot 开关控制是否记录）
            session.attach_screenshot(path)
        except Exception as e:
            print(f"[debug_click] overlay failed: {e}")
        _debug_click_counter += 1
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=clicks)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)

@oplog_step
def type_text(text):
    cdp("Input.insertText", text=text)

@oplog_step
def fill_input(selector, text, clear_first=True, timeout=0.0):
    """填充由框架管理的输入框（React 受控组件、Vue v-model、Ember 追踪属性）。

    type_text() 使用 Input.insertText，这会绕过框架的事件监听器，导致提交按钮保持禁用状态。
    此辅助函数会聚焦元素、清空内容、通过真实按键事件输入文本，然后触发合成的 input+change 事件，
    使框架能够感知到更新。

    如果未找到元素，则抛出 RuntimeError。传入 timeout>0 可在输入前等待延迟渲染的元素
    （例如路由切换后）。
    """
    if timeout > 0:
        if not wait_for_element(selector, timeout=timeout):
            raise RuntimeError(f"fill_input: element not found: {selector!r}")
    focused = js(
        f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
        f"if(!e)return false;e.focus();return true;}})()"
    )
    if not focused:
        raise RuntimeError(f"fill_input: element not found: {selector!r}")
    if clear_first:
        # 直接触发全选操作 — 不使用 press_key，因为 press_key 对单字符按键
        # 总是会发出 `char` 事件。在按住 Ctrl/Cmd 时，该 `char` 事件
        # 会让 Chrome 将输入视为可打印的 "a"，而不是触发全选快捷键，
        # 导致输入框未被清空。
        mods = 4 if sys.platform == "darwin" else 2  # macOS 上使用 Cmd，其他系统使用 Ctrl
        select_all = {"key": "a", "code": "KeyA", "modifiers": mods,
                      "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65}
        cdp("Input.dispatchKeyEvent", type="rawKeyDown", **select_all)
        cdp("Input.dispatchKeyEvent", type="keyUp", **select_all)
        press_key("Backspace")
    for ch in text:
        press_key(ch)
    js(
        f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
        f"if(!e)return;"
        f"e.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"e.dispatchEvent(new Event('change',{{bubbles:true}}));}})();"
    )

_KEYS = {  # 按键 → (windowsVirtualKeyCode, code, text)
    "Enter": (13, "Enter", "\r"), "Tab": (9, "Tab", "\t"), "Backspace": (8, "Backspace", ""),
    "Escape": (27, "Escape", ""), "Delete": (46, "Delete", ""), " ": (32, "Space", " "),
    "ArrowLeft": (37, "ArrowLeft", ""), "ArrowUp": (38, "ArrowUp", ""),
    "ArrowRight": (39, "ArrowRight", ""), "ArrowDown": (40, "ArrowDown", ""),
    "Home": (36, "Home", ""), "End": (35, "End", ""),
    "PageUp": (33, "PageUp", ""), "PageDown": (34, "PageDown", ""),
}
@oplog_step
def press_key(key, modifiers=0):
    """修饰键位域：1=Alt，2=Ctrl，4=Meta(Cmd)，8=Shift。
    特殊按键（Enter、Tab、方向键、Backspace 等）携带其虚拟键码，
    以便检查 e.keyCode / e.key 的监听器都能被触发。"""
    vk, code, text = _KEYS.get(key, (ord(key[0]) if len(key) == 1 else 0, key, key if len(key) == 1 else ""))
    base = {"key": key, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    shortcut_modifiers = modifiers & (1 | 2 | 4)  # Alt/Ctrl/Meta 会将单个按键转换为快捷键。
    printable_char = len(key) == 1 and bool(text) and not shortcut_modifiers
    cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({} if printable_char or not text else {"text": text}))
    if printable_char:
        cdp("Input.dispatchKeyEvent", type="char", text=text, **{k: v for k, v in base.items() if k != "text"})
    cdp("Input.dispatchKeyEvent", type="keyUp", **base)

@oplog_step
def scroll(x, y, dy=-300, dx=0):
    cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)


# --- 视觉 ---
@oplog_step
def capture_screenshot(path=None, full=False, max_dim=None):
    """保存当前视口的 PNG 截图。在 2× 显示器上设置 max_dim=1800，
    可使文件保持在某些图像感知 LLM 所要求的每边不超过 2000 像素的限制内。"""
    path = path or str(ipc._TMP / "shot.png")
    r = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=full)
    open(path, "wb").write(base64.b64decode(r["data"]))
    if max_dim:
        from PIL import Image
        img = Image.open(path)
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
            img.save(path)
    return path


# --- 标签页 ---
def _is_agent_startup_placeholder(title, url):
    url = str(url or "")
    return str(title or "").startswith("Starting agent ") and (
        url in ("", "about:blank") or url.startswith("about:blank#")
    )


@oplog_step
def list_tabs(include_chrome=True):
    out = []
    for t in cdp("Target.getTargets")["targetInfos"]:
        if t["type"] != "page": continue
        url = t.get("url", "")
        if _is_agent_startup_placeholder(t.get("title", ""), url): continue
        if not include_chrome and url.startswith(INTERNAL): continue
        out.append({
            "targetId": t["targetId"],
            "target_id": t["targetId"],
            "title": t.get("title", ""),
            "url": url,
        })
    return out

@oplog_step
def current_tab():
    r = _send({"meta": "current_tab"})
    return {
        "targetId": r["targetId"],
        "target_id": r["targetId"],
        "url": r["url"],
        "title": r["title"],
    }

def _mark_tab():
    """在标签页标题前添加马表情符号，以便用户查看 Agent 正在控制哪个标签页。"""
    try: cdp("Runtime.evaluate", expression="if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title")
    except Exception: pass

@oplog_step
def switch_tab(target):
    # 接受原始 targetId 字符串或 current_tab() / list_tabs() 返回的字典，
    # 这样 `switch_tab(current_tab())` 无需手动取 ["targetId"] 即可工作。
    target_id = (target.get("targetId") or target.get("target_id")) if isinstance(target, dict) else target
    # 移除旧标签页的标记。马表情符号在 JS UTF-16 字符串中是代理对（2 个代码单元），
    # 加上尾部空格共 3 个代码单元，因此 slice(3) 可以干净地移除前缀。
    try: cdp("Runtime.evaluate", expression="if(document.title.startsWith('\U0001F434 '))document.title=document.title.slice(3)")
    except Exception: pass
    cdp("Target.activateTarget", targetId=target_id)
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    _send({"meta": "set_session", "session_id": sid, "target_id": target_id})
    _mark_tab()
    return sid

@oplog_step
def new_tab(url="about:blank"):
    # 始终先创建空白页，再导航：将 url 传给 createTarget 会与 attach 产生竞争，
    # 导致短暂的 about:blank 在调用方轮询时就已经 "complete"，
    # wait_for_load() 在实际导航开始前就返回了。
    if url != "about:blank":
        try:
            cur = current_tab()
            cur_url = cur.get("url") or ""
            if cur_url in ("", "about:blank") or cur_url.startswith("about:blank#"):
                goto_url(url)
                return cur.get("targetId") or cur.get("target_id")
        except Exception:
            pass
    tid = cdp("Target.createTarget", url="about:blank")["targetId"]
    switch_tab(tid)
    if url != "about:blank":
        goto_url(url)
    return tid

@oplog_step
def close_tab(target=None):
    """关闭标签页。如果省略 `target`，则关闭当前已附加的标签页。
    接受原始 targetId 字符串或 list_tabs()/current_tab() 返回的字典。"""
    target_id = (target.get("targetId") or target.get("target_id")) if isinstance(target, dict) else target
    if target_id is None:
        target_id = current_tab()["targetId"]
    cdp("Target.closeTarget", targetId=target_id)


@oplog_step
def ensure_real_tab():
    """如果当前标签页是 chrome:// / 内部页面 / 已过时，则切换到真实的用户标签页。"""
    tabs = list_tabs(include_chrome=False)
    if not tabs:
        return None
    try:
        cur = current_tab()
        if cur["url"] and not cur["url"].startswith(INTERNAL):
            return cur
    except Exception:
        pass
    switch_tab(tabs[0]["targetId"])
    return tabs[0]

@oplog_step
def iframe_target(url_substr):
    """返回第一个 URL 包含 `url_substr` 的 iframe target。配合 js(..., target_id=...) 使用。"""
    for t in cdp("Target.getTargets")["targetInfos"]:
        if t["type"] == "iframe" and url_substr in t.get("url", ""):
            return t["targetId"]
    return None


# --- 工具函数 ---
@oplog_step
def wait(seconds=1.0):
    time.sleep(seconds)

@oplog_step
def wait_for_load(timeout=15.0):
    """轮询等待 document.readyState == 'complete'，超时则返回 False。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if js("document.readyState") == "complete": return True
        time.sleep(0.3)
    return False

@oplog_step
def wait_for_element(selector, timeout=10.0, visible=False):
    """轮询等待 querySelector(selector) 存在于 DOM 中，超时则返回 False。

    wait_for_load() 无法覆盖 SPA — 文档在框架渲染之前就已 'complete'。
    在触发异步渲染的操作（路由切换、数据请求）之后使用此函数。
    设置 visible=True 可额外要求元素非隐藏且处于布局中。
    找到返回 True，超时返回 False。
    """
    if visible:
        # checkVisibility 会遍历祖先链并检查父元素上的 display:none /
        # visibility:hidden / opacity:0，而单独对元素使用 getComputedStyle
        # 无法检测到这些（它只返回后代元素自身的样式，而非继承的
        # "是否被渲染"状态）。在不支持 checkVisibility 的旧版 Chrome 上
        # 回退为逐元素的 CSS 检查。
        check = (
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return false;"
            f"if(typeof e.checkVisibility==='function')"
            f"return e.checkVisibility({{checkOpacity:true,checkVisibilityCSS:true}});"
            f"const s=getComputedStyle(e);"
            f"return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'}})()"
        )
    else:
        check = f"!!document.querySelector({json.dumps(selector)})"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if js(check): return True
        time.sleep(0.3)
    return False

@oplog_step
def wait_for_network_idle(timeout=10.0, idle_ms=500):
    """等待所有进行中的请求完成，并且在 idle_ms 毫秒内没有新的 Network.* 事件到达。

    适用于表单提交、SPA 路由切换以及任何触发 XHR/fetch 但没有可见 DOM 变化的操作。
    基于 drain_events() 构建 — 无需修改 daemon。
    达到空闲时间窗口返回 True，超时返回 False。

    事件会过滤到当前活跃会话 — 之前附加的后台标签页（例如 Agent 已切换离开的
    轮询/SSE 页面）会持续向 daemon 的全局事件缓冲区发送 Network 事件；
    如果没有此过滤，这些事件会干扰当前标签页的空闲检测。
    """
    deadline = time.time() + timeout
    last_activity = time.time()
    inflight = set()
    active_session = _send({"meta": "session"}).get("session_id")
    while time.time() < deadline:
        for e in drain_events():
            if e.get("session_id") != active_session:
                continue
            method = e.get("method", "")
            params = e.get("params", {})
            if method == "Network.requestWillBeSent":
                inflight.add(params.get("requestId"))
                last_activity = time.time()
            elif method in ("Network.loadingFinished", "Network.loadingFailed"):
                inflight.discard(params.get("requestId"))
                last_activity = time.time()
            elif method.startswith("Network."):
                last_activity = time.time()
        if not inflight and (time.time() - last_activity) * 1000 >= idle_ms:
            return True
        time.sleep(0.1)
    return False

@oplog_step
def js(expression, target_id=None):
    """在已附加的标签页（默认）或 iframe target（通过 iframe_target()）中执行 JS。

    表达式首先按原样求值。如果 Chrome 报告非法的顶层 `return`，
    则将代码片段包装在函数中重试，这样 `document.title` 和
    `const x = 1; return x` 都能正常工作，而不会错误地包装包含自身 return 的嵌套函数。
    """
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"] if target_id else None
    try:
        return _runtime_evaluate(expression, session_id=sid, await_promise=True)
    except RuntimeError as e:
        if _is_illegal_return_error(e):
            return _runtime_evaluate(_wrap_js_function(expression), session_id=sid, await_promise=True)
        raise


# 从 _KEYS 派生的 keyCode 子集，用于 dispatch_key() 的 DOM KeyboardEvent
_KC = {k: v[0] for k, v in _KEYS.items()}


@oplog_step
def dispatch_key(selector, key="Enter", event="keypress"):
    """在匹配的元素上触发 DOM KeyboardEvent。

    当网站对元素上的合成 DOM 按键事件的响应比对原始 CDP 输入事件的响应更可靠时，使用此函数。
    """
    kc = _KC.get(key, ord(key) if len(key) == 1 else 0)
    js(
        f"(()=>{{const e=document.querySelector({json.dumps(selector)});if(e){{e.focus();e.dispatchEvent(new KeyboardEvent({json.dumps(event)},{{key:{json.dumps(key)},code:{json.dumps(key)},keyCode:{kc},which:{kc},bubbles:true}}));}}}})()"
    )

@oplog_step
def upload_file(selector, path):
    """通过 CDP DOM.setFileInputFiles 在文件输入框上设置文件。`path` 为绝对文件路径（需要时可使用 tempfile.mkstemp）。"""
    doc = cdp("DOM.getDocument", depth=-1)
    nid = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)["nodeId"]
    if not nid: raise RuntimeError(f"no element for {selector}")
    cdp("DOM.setFileInputFiles", files=[path] if isinstance(path, str) else list(path), nodeId=nid)

@oplog_step
def http_get(url, headers=None, timeout=20.0):
    """纯 HTTP 请求 — 不使用浏览器。适用于静态页面 / API。批量请求时可包装在 ThreadPoolExecutor 中。

    当设置了 BROWSER_USE_API_KEY 时，通过 fetch-use 代理路由（处理机器人检测、
    住宅代理、重试）。否则回退到本地 urllib。"""
    if os.environ.get("BROWSER_USE_API_KEY"):
        try:
            from fetch_use import fetch_sync
            return fetch_sync(url, headers=headers, timeout_ms=int(timeout * 1000)).text
        except ImportError:
            pass
    import gzip
    h = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    if headers: h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip": data = gzip.decompress(data)
        return data.decode()


def _load_agent_helpers():
    p = AGENT_WORKSPACE / "agent_helpers.py"
    if not p.exists():
        return
    spec = importlib.util.spec_from_file_location("web_agent_agent_helpers", p)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        globals()[name] = value


_load_agent_helpers()
