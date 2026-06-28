"""oplog 模块单元测试。"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from web_agent.oplog import (
    OplogSession,
    _config_file_path,
    _load_config_file,
    _project_root,
    _safe_args,
    _truncate_value,
    close_session,
    get_session,
    is_enabled,
    is_screenshot_enabled,
    oplog_dir,
    oplog_step,
    reset_session,
)


# --- 工具函数测试 ---

def test_truncate_value_short():
    """短字符串不截断。"""
    assert _truncate_value("hello") == "hello"


def test_truncate_value_long():
    """长字符串截断并添加省略号。"""
    long_str = "a" * 200
    result = _truncate_value(long_str)
    assert len(result) == 120
    assert result.endswith("...")


def test_safe_args_positional():
    """位置参数用 arg0, arg1 表示。"""
    result = _safe_args(("foo", 42), {})
    assert result["arg0"] == "foo"
    assert result["arg1"] == "42"


def test_safe_args_sensitive_keywords():
    """敏感关键字参数被替换为 [redacted]。"""
    result = _safe_args((), {"password": "secret123", "token": "abc"})
    assert result["password"] == "[redacted]"
    assert result["token"] == "[redacted]"


def test_safe_args_normal_keywords():
    """非敏感关键字参数正常记录。"""
    result = _safe_args((), {"button": "left", "clicks": 2})
    assert result["button"] == "left"
    assert result["clicks"] == "2"


# --- 项目根目录和配置文件路径测试 ---

def test_project_root_is_src_parent():
    """项目根目录是 src/web_agent 的上两级目录。"""
    root = _project_root()
    assert (root / "src" / "web_agent" / "oplog.py").exists()


def test_config_file_path_under_project_root():
    """配置文件路径在项目根目录下。"""
    path = _config_file_path()
    assert path.name == "oplog.jsonc"
    assert path.parent == _project_root()


def test_load_config_file_returns_dict_when_exists(tmp_path, monkeypatch):
    """配置文件存在时返回其内容。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"enabled": true, "screenshot": false}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    config = _load_config_file()
    assert config["enabled"] is True
    assert config["screenshot"] is False


def test_load_config_file_returns_empty_when_missing(tmp_path, monkeypatch):
    """配置文件不存在时返回空字典。"""
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: tmp_path / "nonexistent.jsonc")
    config = _load_config_file()
    assert config == {}


def test_load_config_file_returns_empty_on_invalid_json(tmp_path, monkeypatch):
    """配置文件 JSON 无效时返回空字典。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text("not valid json")
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    config = _load_config_file()
    assert config == {}


def test_load_config_file_strips_jsonc_comments(tmp_path, monkeypatch):
    """配置文件中的 JSONC 注释被正确剥离。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{\n  // 这是注释\n  "enabled": true\n}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    config = _load_config_file()
    assert config["enabled"] is True


# --- 配置优先级测试 ---

def test_is_enabled_config_file_true(tmp_path, monkeypatch):
    """配置文件 enabled=true 时启用。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"enabled": true}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.delenv("WA_OPLOG", raising=False)
    assert is_enabled() is True


def test_is_enabled_config_file_false(tmp_path, monkeypatch):
    """配置文件 enabled=false 时禁用。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"enabled": false}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.delenv("WA_OPLOG", raising=False)
    assert is_enabled() is False


def test_is_enabled_no_config_file(monkeypatch):
    """无配置文件且无环境变量时默认禁用。"""
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    assert is_enabled() is False


def test_is_enabled_env_overrides_config(tmp_path, monkeypatch):
    """环境变量 WA_OPLOG 覆盖配置文件。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"enabled": true}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.setenv("WA_OPLOG", "0")
    assert is_enabled() is False


def test_is_enabled_env_enables_when_config_disabled(tmp_path, monkeypatch):
    """环境变量启用可覆盖配置文件的禁用状态。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"enabled": false}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.setenv("WA_OPLOG", "1")
    assert is_enabled() is True


def test_is_screenshot_enabled_config_file(tmp_path, monkeypatch):
    """配置文件 screenshot=false 时禁用截图记录。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"screenshot": false}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.delenv("WA_OPLOG_SCREENSHOT", raising=False)
    assert is_screenshot_enabled() is False


def test_is_screenshot_enabled_default_true(monkeypatch):
    """无配置文件且无环境变量时截图记录默认启用。"""
    monkeypatch.delenv("WA_OPLOG_SCREENSHOT", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    assert is_screenshot_enabled() is True


def test_is_screenshot_enabled_env_overrides_config(tmp_path, monkeypatch):
    """环境变量覆盖配置文件的截图设置。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text('{"screenshot": true}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.setenv("WA_OPLOG_SCREENSHOT", "0")
    assert is_screenshot_enabled() is False


# --- oplog_dir 测试 ---

def test_oplog_dir_default_is_project_root_oplog(monkeypatch):
    """默认日志目录为项目根目录/oplog。"""
    monkeypatch.delenv("WA_OPLOG_DIR", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    result = oplog_dir()
    assert result == _project_root() / "oplog"


def test_oplog_dir_config_file_dir(tmp_path, monkeypatch):
    """配置文件中指定目录时使用该目录。"""
    config_path = tmp_path / "oplog.jsonc"
    custom_dir = str(tmp_path / "my_logs")
    config_path.write_text(f'{{"dir": "{custom_dir.replace(chr(92), "/")}"}}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.delenv("WA_OPLOG_DIR", raising=False)
    result = oplog_dir()
    assert result.name == "my_logs"


def test_oplog_dir_env_overrides_config(tmp_path, monkeypatch):
    """环境变量 WA_OPLOG_DIR 覆盖配置文件。"""
    config_path = tmp_path / "oplog.jsonc"
    config_path.write_text(f'{{"dir": "{str(tmp_path / "config_dir").replace(chr(92), "/")}"}}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    env_dir = str(tmp_path / "env_dir")
    monkeypatch.setenv("WA_OPLOG_DIR", env_dir)
    result = oplog_dir()
    assert result.name == "env_dir"


def test_oplog_dir_env_only(monkeypatch, tmp_path):
    """仅设置环境变量时使用环境变量路径。"""
    monkeypatch.delenv("WA_OPLOG_DIR", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    custom = str(tmp_path / "custom_oplog")
    monkeypatch.setenv("WA_OPLOG_DIR", custom)
    result = oplog_dir()
    assert result.name == "custom_oplog"


# --- OplogSession 测试 ---

def test_session_disabled_by_default(monkeypatch):
    """默认情况下会话禁用，不创建文件。"""
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    session = OplogSession()
    assert session.enabled is False
    step = session.begin_step("test_func", (), {})
    assert step == {}


def test_session_creates_files_when_enabled(monkeypatch, tmp_path):
    """启用时会话创建日志文件和 screenshots 子目录。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    step = session.begin_step("test_func", (), {})
    assert session._session_dir is not None
    assert session._json_path.exists()
    assert session._text_path.exists()
    # 创建 screenshots 子目录
    assert session._screenshot_dir is not None
    assert session._screenshot_dir.exists()
    session.close()


def test_session_records_steps(monkeypatch, tmp_path):
    """会话记录操作步骤到 JSON 和文本文件。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    step = session.begin_step("goto_url", ("https://example.com",), {})
    session.end_step(step, result={"frameId": "f"})
    session.close()
    # 验证 JSON 文件
    lines = session._json_path.read_text().strip().splitlines()
    records = [json.loads(l) for l in lines]
    types = [r["type"] for r in records]
    assert "session_start" in types
    assert "step" in types
    assert "session_end" in types
    step_record = next(r for r in records if r["type"] == "step")
    assert step_record["func"] == "goto_url"
    assert step_record["status"] == "ok"
    assert "elapsed_ms" in step_record
    text = session._text_path.read_text()
    assert "goto_url" in text
    assert "ok" in text


def test_session_records_error(monkeypatch, tmp_path):
    """会话记录操作错误信息。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    step = session.begin_step("click_at_xy", (100, 200), {})
    session.end_step(step, error=RuntimeError("element not found"))
    session.close()
    lines = session._json_path.read_text().strip().splitlines()
    step_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "step")
    assert step_record["status"] == "error"
    assert "RuntimeError" in step_record["error"]
    assert "element not found" in step_record["error"]


def test_session_records_events(monkeypatch, tmp_path):
    """会话记录非操作步骤事件。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    session.record_event("daemon_started", {"name": "default"})
    session.close()
    lines = session._json_path.read_text().strip().splitlines()
    event_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "event")
    assert event_record["event"] == "daemon_started"


def test_session_summary_on_close(monkeypatch, tmp_path):
    """关闭会话时写入汇总信息。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    step1 = session.begin_step("func1", (), {})
    session.end_step(step1, result="ok")
    step2 = session.begin_step("func2", (), {})
    session.end_step(step2, result="ok")
    session.close()
    lines = session._json_path.read_text().strip().splitlines()
    summary = next(json.loads(l) for l in lines if json.loads(l)["type"] == "session_end")
    assert summary["total_steps"] == 2
    assert "total_elapsed_ms" in summary
    text = session._text_path.read_text()
    assert "总步骤数: 2" in text


def test_session_sensitive_filter_in_event(monkeypatch, tmp_path):
    """事件中的敏感字段被过滤。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    session.record_event("ipc_request", {"method": "Runtime.evaluate", "token": "secret_value"})
    session.close()
    lines = session._json_path.read_text().strip().splitlines()
    event_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "event")
    assert event_record["details"]["token"] == "[redacted]"


# --- attach_screenshot 测试 ---

def test_attach_screenshot_records_when_enabled(monkeypatch, tmp_path):
    """screenshot 启用时，attach_screenshot 将截图复制到 oplog 目录并记录路径。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    session.screenshot_enabled = True
    # 创建一个模拟截图文件
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src_file = src_dir / "debug_click_0.png"
    src_file.write_bytes(b"fake_png_data")
    step = session.begin_step("click_at_xy", (100, 200), {})
    result_path = session.attach_screenshot(str(src_file))
    session.end_step(step, result="ok")
    session.close()
    # 截图应被复制到 oplog 的 screenshots 子目录
    assert result_path is not None
    assert "screenshots" in result_path
    assert Path(result_path).exists()
    # JSON 日志中记录的路径指向 oplog 目录
    lines = session._json_path.read_text().strip().splitlines()
    step_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "step")
    assert "screenshots" in step_record
    assert "screenshots" in step_record["screenshots"][0]


def test_attach_screenshot_skipped_when_disabled(monkeypatch, tmp_path):
    """screenshot 禁用时，attach_screenshot 不记录截图路径。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    session.screenshot_enabled = False
    # 创建一个模拟截图文件
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src_file = src_dir / "debug_click_0.png"
    src_file.write_bytes(b"fake_png_data")
    step = session.begin_step("click_at_xy", (100, 200), {})
    result = session.attach_screenshot(str(src_file))
    session.end_step(step, result="ok")
    session.close()
    lines = session._json_path.read_text().strip().splitlines()
    step_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "step")
    assert "screenshots" not in step_record
    assert result is None


def test_attach_screenshot_skipped_when_oplog_disabled(monkeypatch, tmp_path):
    """oplog 禁用时，attach_screenshot 返回 None。"""
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    session = OplogSession()
    session.screenshot_enabled = True
    # 创建一个模拟截图文件
    src_file = tmp_path / "debug_click_0.png"
    src_file.write_bytes(b"fake_png_data")
    result = session.attach_screenshot(str(src_file))
    assert result is None


def test_attach_screenshot_multiple(monkeypatch, tmp_path):
    """单步骤可附加多张截图，均复制到 screenshots 子目录。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    session.screenshot_enabled = True
    # 创建两个模拟截图文件
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src1 = src_dir / "click_before.png"
    src1.write_bytes(b"fake_png_1")
    src2 = src_dir / "click_after.png"
    src2.write_bytes(b"fake_png_2")
    step = session.begin_step("click_at_xy", (100, 200), {})
    path1 = session.attach_screenshot(str(src1))
    path2 = session.attach_screenshot(str(src2))
    session.end_step(step, result="ok")
    session.close()
    lines = session._json_path.read_text().strip().splitlines()
    step_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "step")
    assert len(step_record["screenshots"]) == 2
    # 两个截图都在 screenshots 子目录下
    assert "screenshots" in step_record["screenshots"][0]
    assert "screenshots" in step_record["screenshots"][1]
    # 文件确实存在
    assert Path(step_record["screenshots"][0]).exists()
    assert Path(step_record["screenshots"][1]).exists()


def test_attach_screenshot_text_log_includes_names(monkeypatch, tmp_path):
    """文本日志中包含截图文件名。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = OplogSession()
    session.screenshot_enabled = True
    # 创建一个模拟截图文件
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src_file = src_dir / "debug_click_0.png"
    src_file.write_bytes(b"fake_png_data")
    step = session.begin_step("click_at_xy", (100, 200), {})
    session.attach_screenshot(str(src_file))
    session.end_step(step, result="ok")
    session.close()
    text = session._text_path.read_text()
    # 截图被复制后文件名包含序号前缀
    assert "debug_click_0.png" in text


# --- 配置文件驱动的会话启用测试 ---

def test_session_enabled_via_config_file(tmp_path, monkeypatch):
    """通过配置文件启用日志时，会话正常工作。"""
    config_path = tmp_path / "oplog.jsonc"
    oplog_out = tmp_path / "oplog_output"
    config_path.write_text(f'{{"enabled": true, "dir": "{str(oplog_out).replace(chr(92), "/")}", "screenshot": false}}')
    monkeypatch.setattr("web_agent.oplog._config_file_path", lambda: config_path)
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.delenv("WA_OPLOG_DIR", raising=False)
    monkeypatch.delenv("WA_OPLOG_SCREENSHOT", raising=False)
    session = OplogSession()
    assert session.enabled is True
    step = session.begin_step("test_func", (), {})
    assert step != {}
    session.end_step(step, result="ok")
    session.close()
    assert session._json_path.exists()


# --- 装饰器测试 ---

def test_oplog_step_disabled_passthrough(monkeypatch):
    """日志禁用时装饰器直接透传，零开销。"""
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    @oplog_step
    def my_func(x, y):
        return x + y
    result = my_func(1, 2)
    assert result == 3


def test_oplog_step_enabled_records(monkeypatch, tmp_path):
    """日志启用时装饰器记录步骤。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = reset_session()
    @oplog_step
    def my_func(x, y):
        return x + y
    result = my_func(3, 4)
    assert result == 7
    close_session()
    json_files = list(tmp_path.rglob("session.json"))
    assert len(json_files) == 1
    lines = json_files[0].read_text().strip().splitlines()
    records = [json.loads(l) for l in lines]
    step_records = [r for r in records if r["type"] == "step"]
    assert len(step_records) == 1
    assert step_records[0]["func"] == "my_func"
    assert step_records[0]["status"] == "ok"


def test_oplog_step_error_propagation(monkeypatch, tmp_path):
    """装饰器在记录错误后重新抛出异常。"""
    monkeypatch.setenv("WA_OPLOG", "1")
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    monkeypatch.setenv("WA_OPLOG_DIR", str(tmp_path))
    session = reset_session()
    @oplog_step
    def failing_func():
        raise ValueError("test error")
    with pytest.raises(ValueError, match="test error"):
        failing_func()
    close_session()
    json_files = list(tmp_path.rglob("session.json"))
    lines = json_files[0].read_text().strip().splitlines()
    step_record = next(json.loads(l) for l in lines if json.loads(l)["type"] == "step")
    assert step_record["status"] == "error"
    assert "test error" in step_record["error"]


# --- 全局会话管理测试 ---

def test_reset_session_creates_new(monkeypatch):
    """reset_session 创建新会话并关闭旧会话。"""
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    session1 = get_session()
    session2 = reset_session()
    assert session2 is not session1


def test_close_session_clears_global(monkeypatch):
    """close_session 清除全局会话。"""
    monkeypatch.delenv("WA_OPLOG", raising=False)
    monkeypatch.setattr("web_agent.oplog._load_config_file", lambda: {})
    session = get_session()
    close_session()
    import web_agent.oplog as oplog_mod
    oplog_mod._session = None
    new_session = get_session()
    assert new_session is not session
    close_session()
