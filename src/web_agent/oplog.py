"""web-agent 操作流转日志模块。

记录每一步操作的详细信息和耗时，支持可配置的日志开关。
日志以双格式输出：结构化 JSON（JSONL）+ 可读文本。

配置来源（优先级从高到低）：
  1. 环境变量（临时覆盖）
     WA_OPLOG           — 启用/禁用操作日志（1/true 启用，0/false 禁用）
     WA_OPLOG_DIR       — 自定义日志根目录
     WA_OPLOG_SCREENSHOT — 是否将项目原有截图记录到日志（1/true 启用，0/false 禁用）
  2. 配置文件 oplog.jsonc（项目根目录下）
     enabled            — 是否启用操作日志（默认 false）
     dir                — 自定义日志目录路径（默认项目根目录/oplog）
     screenshot         — 是否将项目原有截图记录到日志（默认 true）
  3. 默认值：enabled=false, dir={项目根目录}/oplog, screenshot=true
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths


# 禁止记录到日志中的敏感参数名（与 telemetry.py 一致）
_SENSITIVE_KEYS = frozenset({
    "api_key", "content", "cookie", "email", "href", "key",
    "message", "password", "prompt", "query", "secret",
    "selector", "text", "title", "token", "url", "uri",
})

# 参数值截断长度
_VALUE_TRUNCATE = 120

# 配置文件默认值
_CONFIG_DEFAULTS = {
    "enabled": False,  # 默认禁用操作日志
    "dir": None,  # 默认使用项目根目录/oplog
    "screenshot": True,  # 默认将项目原有截图记录到日志
}


def _project_root() -> Path:
    """获取项目根目录路径（src/web_agent 的上两级目录）。"""
    return Path(__file__).resolve().parents[2]


def _config_file_path() -> Path:
    """获取 oplog.jsonc 配置文件路径。"""
    return _project_root() / "oplog.jsonc"


def _load_config_file() -> dict:
    """读取 oplog.jsonc 配置文件，文件不存在或解析失败时返回空字典。"""
    return paths.read_json_config(_config_file_path())


def _env_enabled(env_var: str) -> bool | None:
    """检查环境变量是否为启用状态，未设置时返回 None。"""
    val = (os.environ.get(env_var) or "").strip().lower()
    if not val:
        return None  # 环境变量未设置，不覆盖
    return val in ("1", "true", "yes", "on")


def oplog_dir() -> Path:
    """获取操作日志根目录路径。

    优先级：环境变量 WA_OPLOG_DIR > 配置文件 dir > 默认项目根目录/oplog
    """
    # 1. 环境变量（最高优先级）
    raw = os.environ.get("WA_OPLOG_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    # 2. 配置文件
    config = _load_config_file()
    config_dir = config.get("dir")
    if config_dir:
        return Path(config_dir).expanduser().resolve()
    # 3. 默认值：项目根目录/oplog
    return _project_root() / "oplog"


def is_enabled() -> bool:
    """检查操作日志是否启用。

    优先级：环境变量 WA_OPLOG > 配置文件 enabled > 默认值 False
    """
    env_val = _env_enabled("WA_OPLOG")
    if env_val is not None:
        return env_val  # 环境变量覆盖
    config = _load_config_file()
    return bool(config.get("enabled", _CONFIG_DEFAULTS["enabled"]))


def is_screenshot_enabled() -> bool:
    """检查是否将项目原有截图记录到日志。

    优先级：环境变量 WA_OPLOG_SCREENSHOT > 配置文件 screenshot > 默认值 True
    """
    env_val = _env_enabled("WA_OPLOG_SCREENSHOT")
    if env_val is not None:
        return env_val  # 环境变量覆盖
    config = _load_config_file()
    return bool(config.get("screenshot", _CONFIG_DEFAULTS["screenshot"]))


def _truncate_value(value: Any, limit: int = _VALUE_TRUNCATE) -> str:
    """截断参数值为安全字符串。"""
    s = str(value)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def _safe_args(args: tuple, kwargs: dict) -> dict:
    """将函数参数转换为安全的日志记录字典，过滤敏感信息。"""
    safe = {}
    # 位置参数用 arg0, arg1, ... 表示
    for i, arg in enumerate(args):
        safe[f"arg{i}"] = _truncate_value(arg)
    # 关键字参数
    for key, value in kwargs.items():
        if key.lower() in _SENSITIVE_KEYS:
            safe[key] = "[redacted]"
        else:
            safe[key] = _truncate_value(value)
    return safe


class OplogSession:
    """操作日志会话，记录一次 web-agent 调用的所有操作流转。"""

    def __init__(self):
        self.enabled = is_enabled()  # 是否启用
        self.screenshot_enabled = is_screenshot_enabled()  # 是否将项目截图记录到日志
        self._session_dir: Path | None = None  # 会话目录
        self._json_path: Path | None = None  # JSON 日志文件路径
        self._text_path: Path | None = None  # 文本日志文件路径
        self._screenshot_dir: Path | None = None  # 截图子目录
        self._step_counter: int = 0  # 操作步骤计数器
        self._start_time: float | None = None  # 会话开始时间
        self._json_file = None  # JSON 日志文件句柄
        self._text_file = None  # 文本日志文件句柄
        self._current_step_screenshots: list[str] = []  # 当前步骤关联的截图路径列表
        self._screenshot_counter: int = 0  # 截图文件计数器

    def _ensure_init(self):
        """懒初始化会话目录和文件（仅在首次操作时创建）。"""
        if self._session_dir is not None:
            return

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        short_id = uuid.uuid4().hex[:4]
        session_name = f"{time_str}_{short_id}"

        self._session_dir = oplog_dir() / date_str / session_name
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._json_path = self._session_dir / "session.json"
        self._text_path = self._session_dir / "session.log"
        self._screenshot_dir = self._session_dir / "screenshots"
        self._screenshot_dir.mkdir(exist_ok=True)

        self._start_time = time.time()

        # 写入会话头信息
        header = {
            "type": "session_start",
            "timestamp": now.isoformat(),
            "pid": os.getpid(),
        }
        self._json_file = open(self._json_path, "a", encoding="utf-8")
        self._write_json(header)

        self._text_file = open(self._text_path, "a", encoding="utf-8")
        self._text_file.write(f"=== 操作流转日志 ===\n")
        self._text_file.write(f"会话开始: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._text_file.write(f"PID: {os.getpid()}\n\n")
        self._text_file.flush()

    def _write_json(self, record: dict):
        """追加写入一条 JSONL 记录。"""
        if self._json_file:
            self._json_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            self._json_file.flush()

    def _write_text(self, line: str):
        """追加写入一行文本日志。"""
        if self._text_file:
            self._text_file.write(line + "\n")
            self._text_file.flush()

    def begin_step(self, func_name: str, args: tuple, kwargs: dict) -> dict:
        """开始记录一个操作步骤，返回步骤上下文。"""
        if not self.enabled:
            return {}
        self._ensure_init()
        self._step_counter += 1
        self._current_step_screenshots = []  # 重置当前步骤截图列表

        step = {
            "step": self._step_counter,  # 步骤序号
            "func": func_name,  # 函数名
            "args": _safe_args(args, kwargs),  # 安全参数
            "start_time": time.time(),  # 开始时间戳
        }

        return step

    def end_step(self, step: dict, result: Any = None, error: Exception | None = None):
        """结束一个操作步骤，记录耗时和结果。"""
        if not self.enabled or not step:
            return

        elapsed_ms = round((time.time() - step["start_time"]) * 1000)  # 耗时(毫秒)
        status = "error" if error else "ok" # 操作状态

        # 构建完整记录
        record = {
            "type": "step",
            "step": step.get("step", 0),
            "func": step.get("func", "unknown"),
            "args": step.get("args", {}),
            "elapsed_ms": elapsed_ms,
            "status": status,
        }
        # 附加截图路径（由 attach_screenshot 收集）
        if self._current_step_screenshots:
            record["screenshots"] = self._current_step_screenshots
        if error:
            record["error"] = f"{type(error).__name__}: {_truncate_value(error, 200)}"  # 异常类型 + 错误信息
        if result is not None and status == "ok":
            record["result_preview"] = _truncate_value(result, 200)  # 结果预览

        # 写入 JSON 日志
        self._write_json(record)

        # 写入文本日志
        ts = datetime.fromtimestamp(step["start_time"]).strftime("%H:%M:%S.%f")[:-3]
        screenshot_info = ""
        if self._current_step_screenshots:
            names = [Path(p).name for p in self._current_step_screenshots]
            screenshot_info = f" 📸 {', '.join(names)}"
        error_info = f" ❌ {_truncate_value(error, 80)}" if error else ""
        line = f"[{ts}] {step.get('func', '?')}() → {status} [{elapsed_ms}ms]{screenshot_info}{error_info}"
        self._write_text(line)

    def attach_screenshot(self, path: str) -> str | None:
        """将项目原有截图关联到当前步骤的日志记录。

        截图文件会被复制到当前会话的 screenshots/ 子目录下，
        日志中记录的路径为 oplog 目录内的路径，便于统一管理。
        仅在 oplog 启用且 screenshot 开关为 true 时记录截图路径。
        项目原有截图不受影响，无论此开关如何都会正常产生。
        返回 oplog 内的路径，或未启用时返回 None。
        """
        if not self.enabled or not self.screenshot_enabled:
            return None  # screenshot 关闭时不记录到日志，但截图本身正常产生
        # 确保会话已初始化
        self._ensure_init()
        if self._screenshot_dir is None:
            self._current_step_screenshots.append(path)
            return path
        # 复制截图到 oplog 目录
        try:
            src = Path(path)
            if not src.exists():
                self._current_step_screenshots.append(path)
                return path
            self._screenshot_counter += 1
            dest = self._screenshot_dir / f"{self._screenshot_counter:03d}_{src.name}"
            shutil.copy2(str(src), str(dest))
            oplog_path = str(dest)
            self._current_step_screenshots.append(oplog_path)
            return oplog_path
        except Exception:
            self._current_step_screenshots.append(path)
            return path

    def get_screenshot_dir(self) -> Path | None:
        """获取当前会话的截图目录路径，用于直接保存截图到 oplog 目录。

        仅在 oplog 启用时返回路径，否则返回 None。
        """
        if not self.enabled:
            return None
        self._ensure_init()
        return self._screenshot_dir

    def record_event(self, event_type: str, details: dict | None = None):
        """记录一个非操作步骤的事件（如 daemon 启动、IPC 连接等）。"""
        if not self.enabled:
            return
        self._ensure_init()
        self._step_counter += 1

        record = {
            "type": "event",  # 事件类型标识
            "step": self._step_counter,
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
        }
        if details:
            # 过滤敏感信息
            safe_details = {}
            for k, v in details.items():
                if k.lower() in _SENSITIVE_KEYS:
                    safe_details[k] = "[redacted]"
                else:
                    safe_details[k] = _truncate_value(v)
            record["details"] = safe_details

        self._write_json(record)

        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        detail_str = ""
        if details:
            safe = {k: v for k, v in details.items() if k.lower() not in _SENSITIVE_KEYS}
            detail_str = f" {json.dumps(safe, ensure_ascii=False, default=str)[:80]}"
        self._write_text(f"[{ts}] ⚡ {event_type}{detail_str}")

    def close(self):
        """关闭会话，写入汇总信息并关闭文件。"""
        if not self.enabled or self._session_dir is None:
            return

        elapsed_total = round((time.time() - self._start_time) * 1000) if self._start_time else 0
        summary = {
            "type": "session_end",
            "timestamp": datetime.now().isoformat(),
            "total_steps": self._step_counter,
            "total_elapsed_ms": elapsed_total,
        }
        self._write_json(summary)

        self._write_text(f"\n--- 会话结束 ---")
        self._write_text(f"总步骤数: {self._step_counter}")
        self._write_text(f"总耗时: {elapsed_total}ms")

        # 关闭文件句柄
        if self._json_file:
            try:
                self._json_file.close()
            except Exception:
                pass
            self._json_file = None
        if self._text_file:
            try:
                self._text_file.close()
            except Exception:
                pass
            self._text_file = None


# 全局会话实例（懒初始化）
_session: OplogSession | None = None


def get_session() -> OplogSession:
    """获取全局操作日志会话实例。"""
    global _session
    if _session is None:
        _session = OplogSession()
    return _session


def reset_session() -> OplogSession:
    """重置全局会话（用于新的 web-agent 调用）。"""
    global _session
    if _session is not None:
        _session.close()
    _session = OplogSession()
    return _session


def close_session():
    """关闭全局会话。"""
    global _session
    if _session is not None:
        _session.close()
        _session = None


def oplog_step(func):
    """装饰器：记录操作步骤的流转信息和耗时。

    当日志功能关闭时，直接透传原始函数调用，零开销。
    当日志功能开启时，记录操作名称、参数、耗时和结果状态。
    项目原有截图通过 attach_screenshot 主动关联到日志。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = get_session()
        if not session.enabled:
            return func(*args, **kwargs)  # 关闭时零开销透传
        step = session.begin_step(func.__name__, args, kwargs)
        try:
            result = func(*args, **kwargs)
            session.end_step(step, result=result)
            return result
        except Exception as e:
            session.end_step(step, error=e)
            raise
    return wrapper
