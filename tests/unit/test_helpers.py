import os
import tempfile
import time
from unittest.mock import patch

import pytest
from PIL import Image

from web_agent import helpers


def _run(fake_png, width, height, **kwargs):
    fake = lambda method, **_: {"data": fake_png(width, height)}
    with patch("web_agent.helpers.cdp", side_effect=fake), tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "shot.png")
        helpers.capture_screenshot(path, **kwargs)
        return Image.open(path).size


def test_max_dim_downsizes_oversized_image(fake_png):
    assert max(_run(fake_png, 4592, 2286, max_dim=1800)) == 1800


def test_max_dim_skips_when_image_already_small(fake_png):
    assert _run(fake_png, 800, 400, max_dim=1800) == (800, 400)


def test_max_dim_default_is_no_resize(fake_png):
    assert _run(fake_png, 4592, 2286) == (4592, 2286)


def _seed_skill(tmp_path):
    site = tmp_path / "domain-skills" / "example"
    site.mkdir(parents=True)
    (site / "scraping.md").write_text("hi")


def test_goto_url_omits_domain_skills_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("WA_DOMAIN_SKILLS", raising=False)
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", tmp_path)
    _seed_skill(tmp_path)
    with patch("web_agent.helpers.cdp", return_value={"frameId": "f"}):
        result = helpers.goto_url("https://www.example.com/")
    assert result == {"frameId": "f"}


def test_goto_url_includes_domain_skills_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("WA_DOMAIN_SKILLS", "1")
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", tmp_path)
    _seed_skill(tmp_path)
    with patch("web_agent.helpers.cdp", return_value={"frameId": "f"}):
        result = helpers.goto_url("https://www.example.com/")
    assert result == {"frameId": "f", "domain_skills": ["scraping.md"]}


def test_page_info_raises_clear_error_on_js_exception():
    def fake_send(req):
        return {}

    def fake_cdp(method, **kwargs):
        return {
            "result": {
                "type": "object",
                "subtype": "error",
                "description": "ReferenceError: location is not defined",
            },
            "exceptionDetails": {
                "text": "Uncaught",
                "lineNumber": 0,
                "columnNumber": 16,
            },
        }

    with patch("web_agent.helpers._send", side_effect=fake_send), \
         patch("web_agent.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="ReferenceError"):
            helpers.page_info()


# --- fill_input 部分 ---

def test_fill_input_focuses_types_and_fires_events():
    cdp_calls = []
    js_calls = []

    def fake_cdp(method, **kwargs):
        cdp_calls.append((method, kwargs))
        return {}

    def fake_js(expr, **kwargs):
        js_calls.append(expr)
        return True  # focus 调用必须返回 True（元素已找到）

    with patch("web_agent.helpers.cdp", side_effect=fake_cdp), \
         patch("web_agent.helpers.js", side_effect=fake_js):
        helpers.fill_input("#my-input", "hello")

    assert any("#my-input" in e for e in js_calls)
    key_downs = [m for m, _ in cdp_calls if m == "Input.dispatchKeyEvent"]
    assert len(key_downs) > 0
    assert any("input" in e and "change" in e for e in js_calls)


def test_fill_input_raises_when_element_not_found():
    def fake_js(expr, **kwargs):
        return False  # 元素未找到

    with patch("web_agent.helpers.js", side_effect=fake_js):
        with pytest.raises(RuntimeError, match="element not found"):
            helpers.fill_input("#missing", "hello")


def test_fill_input_clear_first_sends_select_all_then_backspace():
    import sys

    key_events = []

    def fake_cdp(method, **kwargs):
        if method == "Input.dispatchKeyEvent":
            key_events.append(kwargs)
        return {}

    def fake_js(expr, **kwargs):
        return True  # 元素已找到

    with patch("web_agent.helpers.cdp", side_effect=fake_cdp), \
         patch("web_agent.helpers.js", side_effect=fake_js):
        helpers.fill_input("#inp", "x", clear_first=True)

    # "a" 必须使用平台正确的修饰符派发（macOS 上 Meta=4，
    # 其他平台 Ctrl=2）。没有修饰符，字段永远不会被选中 ——
    # 它只会接收到一个字面的 "a"。
    expected_mod = 4 if sys.platform == "darwin" else 2
    a_events = [e for e in key_events if e.get("key") == "a"]
    assert a_events, "expected an 'a' key event for select-all"
    assert all(e.get("modifiers") == expected_mod for e in a_events), \
        f"select-all 'a' must carry modifiers={expected_mod}; got {[e.get('modifiers') for e in a_events]}"

    # 关键：不应对 "a" 发出 `char` 事件 —— 发出后 Chrome 会将
    # Cmd/Ctrl+A 视为可打印字符而不是快捷键。
    assert not any(e.get("type") == "char" and e.get("text") == "a" for e in key_events), \
        "select-all must not emit a 'char' event with text='a' (would cancel the shortcut)"

    # Backspace 仍然会触发（通过 press_key，使用 keyDown）。
    keys_down = [e.get("key") for e in key_events if e.get("type") in ("keyDown", "rawKeyDown")]
    assert "Backspace" in keys_down


def test_fill_input_no_clear_skips_ctrl_a():
    key_events = []

    def fake_cdp(method, **kwargs):
        if method == "Input.dispatchKeyEvent":
            key_events.append(kwargs)
        return {}

    def fake_js(expr, **kwargs):
        return True  # 元素已找到

    with patch("web_agent.helpers.cdp", side_effect=fake_cdp), \
         patch("web_agent.helpers.js", side_effect=fake_js):
        helpers.fill_input("#inp", "x", clear_first=False)

    keys_seen = [e.get("key") for e in key_events if e.get("type") == "keyDown"]
    assert "Backspace" not in keys_seen


# --- wait_for_element 部分 ---

def test_wait_for_element_returns_true_when_found_immediately():
    def fake_js(expr, **kwargs):
        return True

    with patch("web_agent.helpers.js", side_effect=fake_js):
        assert helpers.wait_for_element("#target", timeout=2.0) is True


def test_wait_for_element_returns_false_on_timeout():
    def fake_js(expr, **kwargs):
        return False

    with patch("web_agent.helpers.js", side_effect=fake_js), \
         patch("web_agent.helpers.time") as mock_time:
        # 模拟时间立即超过截止时间
        start = time.time()
        mock_time.time.side_effect = [start, start + 5.0]
        mock_time.sleep = lambda _: None
        assert helpers.wait_for_element("#missing", timeout=1.0) is False


def test_wait_for_element_visible_uses_check_visibility():
    js_exprs = []

    def fake_js(expr, **kwargs):
        js_exprs.append(expr)
        return True

    with patch("web_agent.helpers.js", side_effect=fake_js):
        helpers.wait_for_element("#btn", visible=True)

    # 优先使用 checkVisibility（遍历祖先链），对旧版 Chrome 回退到
    # getComputedStyle。
    assert any("checkVisibility" in e for e in js_exprs)
    assert any("getComputedStyle" in e for e in js_exprs)
    # 绝不能使用 offsetParent（对 position:fixed 元素会失败）
    assert not any("offsetParent" in e for e in js_exprs)


def test_wait_for_element_non_visible_uses_simple_check():
    js_exprs = []

    def fake_js(expr, **kwargs):
        js_exprs.append(expr)
        return True

    with patch("web_agent.helpers.js", side_effect=fake_js):
        helpers.wait_for_element("#btn", visible=False)

    assert any("querySelector" in e and "offsetParent" not in e for e in js_exprs)


# --- wait_for_network_idle 部分 ---

def test_wait_for_network_idle_returns_true_when_no_events():
    call_count = 0

    def fake_send(req):
        nonlocal call_count
        call_count += 1
        return {"events": []}

    with patch("web_agent.helpers._send", side_effect=fake_send), \
         patch("web_agent.helpers.time") as mock_time:
        start = 1000.0
        # 第一次调用：尚未空闲；第二次调用：空闲窗口已过
        mock_time.time.side_effect = [start, start, start, start + 0.6, start + 0.6]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=5.0, idle_ms=500)

    assert result is True


def test_wait_for_network_idle_waits_for_inflight_request():
    # 验证进行中请求跟踪：必须等到 loadingFinished 才能返回 True，
    # 即使 requestWillBeSent 和 loadingFinished 之间已超过 idle_ms。
    # 仅基于事件静默的实现会在 iter2 返回 True（错误的）。
    events_seq = [
        [{"method": "Network.requestWillBeSent", "params": {"requestId": "req1"}}],
        [],   # 已超过 500ms —— 旧实现在此处返回 True；新实现绝不能
        [{"method": "Network.loadingFinished",   "params": {"requestId": "req1"}}],
        [],   # loadingFinished 后的 idle_ms → 返回 True
    ]
    idx = 0

    def fake_send(req):
        nonlocal idx
        evs = events_seq[min(idx, len(events_seq) - 1)]
        idx += 1
        return {"events": evs}

    with patch("web_agent.helpers._send", side_effect=fake_send), \
         patch("web_agent.helpers.time") as mock_time:
        start = 1000.0
        # 进行中请求非空 → 空闲检查中的短路跳过了 iter1/iter2 的 time.time()
        mock_time.time.side_effect = [
            start, start,       # 截止时间 + last_activity 初始化
            start + 0.1,        # iter1 while 检查
            start + 0.1,        # iter1 rWS last_activity 更新
                                # iter1 空闲检查：进行中请求非空 → 短路
            start + 0.7,        # iter2 while 检查（距 rWS 已 >500ms 但请求仍在进行中）
                                # iter2 空闲检查：进行中请求非空 → 短路
            start + 0.8,        # iter3 while 检查
            start + 0.8,        # iter3 lF last_activity 更新
            start + 0.8,        # iter3 空闲检查：0ms < 500 → 非空闲
            start + 1.4,        # iter4 while 检查
            start + 1.4,        # iter4 空闲检查：600ms >= 500 → True
        ]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=5.0, idle_ms=500)

    assert result is True
    assert idx == 4  # 在 iter2 尽管静默超过 idle_ms 但没有短路返回


def test_wait_for_network_idle_returns_false_on_timeout():
    # 持续的 rWS 使进行中请求保持非空 → 空闲检查每次迭代都短路。
    # time.time() 只在 while 检查和 rWS last_activity 时被调用（不在空闲检查中）。
    def fake_send(req):
        return {"events": [{"method": "Network.requestWillBeSent", "params": {"requestId": "r"}}]}

    with patch("web_agent.helpers._send", side_effect=fake_send), \
         patch("web_agent.helpers.time") as mock_time:
        start = 1000.0
        mock_time.time.side_effect = [
            start, start,       # 截止时间 + last_activity 初始化
            start + 0.1,        # iter1 while 检查（在截止时间内）
            start + 0.1,        # iter1 rWS last_activity 更新
                                # iter1 空闲检查：进行中请求非空 → 短路
            start + 20.0,       # iter2 while 检查（超过截止时间 → 退出）
        ]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=10.0, idle_ms=500)

    assert result is False



def test_wait_for_network_idle_filters_events_to_active_session():
    """后台标签页（例如代理切换离开的轮询页面）持续向守护进程的
    全局缓冲区发送 Network 事件。等待必须按当前附加标签页的 session_id
    进行过滤 —— 否则它会看到后台标签页的流量，要么无法返回空闲状态，
    要么等待错误标签页的请求。"""
    active = "session-ACTIVE"
    background = "session-BACKGROUND"

    # 第一次 /drain_events/ 负载：必须忽略的 BACKGROUND 会话上的 rWS + lF，
    # 加上活跃会话上的零事件。通过过滤，活跃会话看不到流量，空闲窗口可以过去。
    events_seq = [
        [
            {"session_id": background, "method": "Network.requestWillBeSent", "params": {"requestId": "bg1"}},
            {"session_id": background, "method": "Network.loadingFinished",   "params": {"requestId": "bg1"}},
        ],
        [],  # 第二次 drain —— 两个会话都安静；空闲窗口应该在此处触发
    ]
    drain_idx = 0

    def fake_send(req):
        nonlocal drain_idx
        if req.get("meta") == "session":
            return {"session_id": active}
        if req.get("meta") == "drain_events":
            evs = events_seq[min(drain_idx, len(events_seq) - 1)]
            drain_idx += 1
            return {"events": evs}
        return {}

    with patch("web_agent.helpers._send", side_effect=fake_send), \
         patch("web_agent.helpers.time") as mock_time:
        start = 1000.0
        # 活跃会话上没有进行中请求 → 空闲检查使用 time.time()。
        mock_time.time.side_effect = [start, start, start, start + 0.6, start + 0.6]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=5.0, idle_ms=500)

    assert result is True, (
        "wait_for_network_idle must return True even when the BACKGROUND "
        "session is busy, as long as the ACTIVE session is idle. Without the "
        "session filter, the background rWS/lF pair would have updated "
        "last_activity and prevented the idle window from elapsing."
    )
