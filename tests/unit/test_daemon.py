import asyncio

from web_agent import daemon


class _FakeCDP:
    """记录 send_raw 调用，以便测试可以断言触发了哪些 CDP 方法。"""

    def __init__(self):
        self.calls = []  # (方法, 参数, 会话ID) 列表

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        # set-session/初始附加路径只需要一个良性响应。
        return {}


def _fresh_daemon():
    d = daemon.Daemon()
    d.cdp = _FakeCDP()
    return d


def test_set_session_enables_all_four_default_domains_on_new_session():
    """回归测试：helpers.py 中的 switch_tab() / new_tab() 通过
    `set_session` IPC 路由，之前只在新的会话上启用 Page。
    在 Network 被禁用的情况下，wait_for_network_idle() 在标签页切换后
    静默地停止接收事件。初始附加启用所有四个域（Page、DOM、Runtime、Network）；
    set_session 必须启用相同的域集合。"""
    d = _fresh_daemon()
    new_session = "session-AFTER-switch"

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": new_session,
        "target_id": "target-2",
    }))

    enabled_on_new = [
        method for (method, _params, sid) in d.cdp.calls
        if sid == new_session and method.endswith(".enable")
    ]
    assert set(enabled_on_new) == {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}, (
        f"set_session must enable Page/DOM/Runtime/Network on the new session "
        f"(parity with initial attach). Got: {enabled_on_new}"
    )
    assert d.session == new_session
    assert d.target_id == "target-2"


def test_set_session_falls_back_to_existing_target_id_when_not_provided():
    """如果调用者遗漏了 target_id（传入 None），守护进程应该保留其
    现有的 target_id 而不是用 None 覆盖 —— 否则依赖 self.target_id 的
    后续调用将会出错。"""
    d = _fresh_daemon()
    d.target_id = "original-target"

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-AFTER",
        "target_id": None,
    }))

    assert d.target_id == "original-target"
    assert d.session == "session-AFTER"


def test_enable_default_domains_swallows_errors_per_domain():
    """单个域启用失败不能阻止其他域的启用尝试 —— 否则守护进程将
    处于部分配置状态。每个 Domain.enable 调用在辅助函数内部都有
    独立的 try/except。"""
    class _PartialFailureCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method == "DOM.enable":
                raise RuntimeError("simulated DOM failure")
            return {}

    d = daemon.Daemon()
    d.cdp = _PartialFailureCDP()

    asyncio.run(d._enable_default_domains("session-X"))

    attempted = [m for (m, _p, _s) in d.cdp.calls]
    assert "Page.enable" in attempted
    assert "DOM.enable" in attempted  # 已尝试，但抛出了异常
    assert "Runtime.enable" in attempted
    assert "Network.enable" in attempted


def test_set_session_disables_network_on_old_session_before_enabling_new():
    """切换标签页时，必须禁用前一个会话的 Network 域，以便后台标签页
    （轮询、SSE 等）停止向 wait_for_network_idle 读取的全局缓冲区
    发送事件。初始附加没有 `old_session`，因此那时不会触发此禁用操作。"""
    d = _fresh_daemon()
    d.session = "session-OLD"
    d.target_id = "target-OLD"

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-NEW",
        "target_id": "target-NEW",
    }))

    disabled = [
        (method, sid) for (method, _params, sid) in d.cdp.calls
        if method == "Network.disable"
    ]
    assert disabled == [("Network.disable", "session-OLD")], (
        f"Network.disable must fire on the old session before re-enabling on "
        f"the new one. Got: {disabled}"
    )

    # 合理性检查：新会话仍然获得了 Network.enable。
    enabled_on_new = {
        method for (method, _p, sid) in d.cdp.calls
        if sid == "session-NEW" and method.endswith(".enable")
    }
    assert "Network.enable" in enabled_on_new


def test_set_session_does_not_disable_network_when_no_previous_session():
    """第一次 set_session 调用（例如在启动早期、任何附加之前）
    没有 old_session —— Network.disable 路径必须被跳过。"""
    d = _fresh_daemon()
    d.session = None  # 没有先前的附加

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-FIRST",
        "target_id": "target-FIRST",
    }))

    disables = [m for (m, _p, _s) in d.cdp.calls if m == "Network.disable"]
    assert disables == [], (
        f"Network.disable must not fire when there's no previous session "
        f"to disable. Got: {disables}"
    )


def test_set_session_runs_disable_and_enables_in_parallel():
    """四个 Domain.enable 调用（加上旧会话上的 Network.disable）
    必须通过 asyncio.gather 并发运行，而不是顺序执行。使用旧的
    顺序代码时，helpers.switch_tab() 会在 _send() 中阻塞长达
    约 22 秒（在慢速/远程守护进程上），而辅助函数的 IPC 套接字
    有 5 秒的读取超时，会导致客户端套接字超时。验证所有五个 CDP 调用
    在任何一个返回之前都到达了 send_raw，即可证明并行化。"""
    class _ConcurrencyProbeCDP:
        def __init__(self):
            self.calls = []
            self.in_flight = 0
            self.max_concurrent = 0
            self.release = None  # asyncio.Event，在测试循环内设置

        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            self.in_flight += 1
            self.max_concurrent = max(self.max_concurrent, self.in_flight)
            try:
                await self.release.wait()
            finally:
                self.in_flight -= 1
            return {}

    async def run():
        d = daemon.Daemon()
        d.cdp = _ConcurrencyProbeCDP()
        d.session = "session-OLD"  # 确保旧会话上的 Network.disable 被触发
        d.cdp.release = asyncio.Event()

        handle_task = asyncio.create_task(d.handle({
            "meta": "set_session",
            "session_id": "session-NEW",
            "target_id": "target-NEW",
        }))
        # 反复让出控制权，直到所有将要进行中的调用都进行中。
        # 限制迭代次数以避免并行化失败时挂起。
        for _ in range(50):
            await asyncio.sleep(0)
            # 5 = 旧会话上的 Network.disable + 新会话上的 4 个 enable。
            if d.cdp.in_flight >= 5:
                break
        peak = d.cdp.max_concurrent
        d.cdp.release.set()
        await handle_task
        return peak, d.cdp.calls

    peak, calls = asyncio.run(run())
    assert peak == 5, (
        f"set_session must run disable + 4 enables concurrently via gather "
        f"(observed peak in-flight = {peak}; expected 5 = 1 disable on OLD + "
        f"4 enables on NEW). Sequential await would peak at 1."
    )
    # 合理性检查：正确的调用被执行了。
    methods = sorted({m for (m, _p, _s) in calls})
    assert "Network.disable" in methods
    assert {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}.issubset(methods)


def test_set_session_first_attach_runs_four_enables_in_parallel():
    """当没有之前的会话时，禁用路径被跳过 —— 只有四个 enable 运行，
    仍然是并行的。"""
    class _ConcurrencyProbeCDP:
        def __init__(self):
            self.calls = []
            self.in_flight = 0
            self.max_concurrent = 0
            self.release = None

        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            self.in_flight += 1
            self.max_concurrent = max(self.max_concurrent, self.in_flight)
            try:
                await self.release.wait()
            finally:
                self.in_flight -= 1
            return {}

    async def run():
        d = daemon.Daemon()
        d.cdp = _ConcurrencyProbeCDP()
        d.session = None  # 没有之前的会话
        d.cdp.release = asyncio.Event()

        handle_task = asyncio.create_task(d.handle({
            "meta": "set_session",
            "session_id": "session-FIRST",
            "target_id": "target-FIRST",
        }))
        for _ in range(50):
            await asyncio.sleep(0)
            if d.cdp.in_flight >= 4:
                break
        peak = d.cdp.max_concurrent
        d.cdp.release.set()
        await handle_task
        return peak

    peak = asyncio.run(run())
    assert peak == 4, (
        f"first set_session must run 4 enables concurrently "
        f"(observed peak = {peak}). No Network.disable should fire."
    )


def test_current_tab_meta_passes_attached_target_id():
    """issue #304 回归测试：helpers.current_tab() 之前发送 Target.getTargetInfo
    时没有 targetId。守护进程对 Target.* 方法去除 session_id，因此该调用
    以空参数命中浏览器级连接，Chrome 返回的是*浏览器*目标的信息（空的
    url/title）而不是附加的页面。守护进程现在使用其跟踪的 target_id
    在服务端解析此问题。"""
    class _TargetInfoCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method == "Target.getTargetInfo":
                return {"targetInfo": {
                    "targetId": params["targetId"],
                    "url": "https://example.com/",
                    "title": "Example Domain",
                    "type": "page",
                }}
            return {}

    d = daemon.Daemon()
    d.cdp = _TargetInfoCDP()
    d.target_id = "page-target-abc"

    result = asyncio.run(d.handle({"meta": "current_tab"}))

    assert result == {
        "targetId": "page-target-abc",
        "url": "https://example.com/",
        "title": "Example Domain",
    }
    # targetId 必须被传递 —— 这就是修复的核心要点。
    get_info_calls = [(p, s) for (m, p, s) in d.cdp.calls if m == "Target.getTargetInfo"]
    assert get_info_calls == [({"targetId": "page-target-abc"}, None)]


def test_current_tab_meta_returns_not_attached_when_no_target_id():
    """没有附加页面时，current_tab() 没有有意义的答案。
    返回 {error: not_attached} 会导致 helpers 中的 _send() 抛出异常，
    这对于像 ensure_real_tab() 这样将调用包装在 try/except 中的
    调用者来说是正确的信号。"""
    d = _fresh_daemon()
    d.target_id = None

    result = asyncio.run(d.handle({"meta": "current_tab"}))

    assert result == {"error": "not_attached"}
    # 不应发出任何 CDP 调用。
    assert d.cdp.calls == []
