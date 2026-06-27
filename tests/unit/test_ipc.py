from web_agent import _ipc as ipc


def test_runtime_stem_uses_name_in_shared_runtime_dir(monkeypatch):
    monkeypatch.setattr(ipc, "WA_RUNTIME_DIR", "/tmp/web-agent")
    monkeypatch.setattr(ipc, "WA_RUNTIME_DIR_SHARED", True)

    assert ipc._runtime_stem("work") == "wa-work"


def test_runtime_stem_uses_bare_name_in_isolated_runtime_dir(monkeypatch):
    monkeypatch.setattr(ipc, "WA_RUNTIME_DIR", "/tmp/web-agent-work")
    monkeypatch.setattr(ipc, "WA_RUNTIME_DIR_SHARED", False)

    assert ipc._runtime_stem("work") == "wa"


def test_tmp_stem_uses_name_in_shared_tmp_dir(monkeypatch):
    monkeypatch.setattr(ipc, "WA_TMP_DIR", "/tmp/web-agent")
    monkeypatch.setattr(ipc, "WA_TMP_DIR_SHARED", True)

    assert ipc._tmp_stem("work") == "wa-work"


# --- identify()：ping 负载清理 ---

class _FakeConn:
    def close(self): pass


def _patch_identify_response(monkeypatch, response):
    """桩化 connect() 和 request()，使 identify() 看到的 `response` 与
    从守护进程回复中解析的 JSON 完全一致，就像从网络接收到的一样。"""
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_identify_returns_pid_for_well_formed_ping_reply(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": True, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) == 4242


def test_identify_rejects_boolean_pid(monkeypatch):
    """isinstance(True, int) 在 Python 中为 True；恶意或有缺陷的守护进程
    回复 {"pid": True} 时会得到 PID 1（POSIX 上的 init 进程），
    os.kill(1, SIGTERM) 会命中它。必须显式拒绝。"""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_boolean_false_pid(monkeypatch):
    """False 也是 int 的子类，会得到 PID 0。"""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": False})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_returns_none_when_pid_field_missing(monkeypatch):
    """升级前的守护进程只回复 {pong: True} —— 没有 pid。identify 必须
    返回 None，让调用者知道没有已验证的 PID 可以发送信号，同时仍允许
    通过 ipc.ping() 进行存活检查。"""
    _patch_identify_response(monkeypatch, {"pong": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_handles_non_dict_ping_payload(monkeypatch):
    """request() 可以反序列化任何有效的 JSON 值。残留或恶意的端点
    回复列表/标量/null 会导致朴素的 resp.get() 抛出 AttributeError；
    identify 必须吸收这种情况并返回 None。"""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_identify_response(monkeypatch, payload)
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() should reject non-dict ping payload: {payload!r}"
        )


def test_identify_returns_none_when_pong_is_not_true(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": False, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_zero_and_negative_pids(monkeypatch):
    """os.kill 在 POSIX 上的语义：pid=0 向调用进程组中的所有进程发送信号；
    pid=-1 向调用者有权限的所有进程发送信号；pid<-1 向对应的进程组发送信号。
    这些都不是有效的守护进程 PID，将任何值转发给 os.kill 都会造成灾难性后果。"""
    for bad_pid in (0, -1, -42, -99999):
        _patch_identify_response(monkeypatch, {"pong": True, "pid": bad_pid})
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() must reject non-positive pid {bad_pid!r}"
        )


# --- ping()：相同的负载清理 ---

def _patch_ping_response(monkeypatch, response):
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_ping_returns_true_for_well_formed_pong(monkeypatch):
    _patch_ping_response(monkeypatch, {"pong": True})

    assert ipc.ping("default", timeout=0.0) is True


def test_ping_handles_non_dict_payload(monkeypatch):
    """与 identify() 相同的回归类别：如果残留或恶意的端点
    回复列表/标量/null，ping() 必须返回 False 而不是在 resp.get() 上
    抛出 AttributeError。restart_daemon() 现在在回退路径上调用 ping()，
    因此此处未处理的异常会中止清理操作。"""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_ping_response(monkeypatch, payload)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should reject non-dict payload: {payload!r}"
        )


def test_ping_returns_false_when_pong_field_is_missing_or_not_true(monkeypatch):
    for resp in ({}, {"pong": False}, {"pong": "yes"}, {"pong": 1}):
        _patch_ping_response(monkeypatch, resp)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should require pong is exactly True; got: {resp!r}"
        )
