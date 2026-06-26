"""web-agent 的尽力而为、可选择退出的遥测功能。

仅发送低基数的操作事件。调用者应传递类别、
状态和布尔值，永远不要传递 URL、选择器、页面文本、提示或凭据。
"""

from __future__ import annotations

import json
import os
import platform
import re
import urllib.request
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import paths
from .paths import read_json_config, write_json_config


POSTHOG_KEY = "phc_rCPCLPtaXB3EuBdiH7JLKtU2Wj5iPnuwdsbw58CnjYXc"  # PostHog API 密钥
POSTHOG_HOST = "https://eu.i.posthog.com"  # PostHog 服务器地址
DISABLE_ENVS = ("WA_TELEMETRY", "WEB_AGENT_TELEMETRY")  # 禁用遥测的环境变量名
FORBIDDEN_KEYS = (  # 禁止出现在属性中的敏感键名
    "api_key",
    "content",
    "cookie",
    "email",
    "href",
    "key",
    "message",
    "password",
    "path",
    "prompt",
    "query",
    "secret",
    "selector",
    "text",
    "title",
    "token",
    "url",
    "uri",
)


def _config_dir() -> Path:
    """
    获取配置目录路径。
    """
    return paths.config_dir()


def _config_path() -> Path:
    """
    获取配置文件路径。
    """
    return _config_dir() / "telemetry.json"


def _load_config() -> dict:
    """
    加载配置文件。
    从配置文件读取并返回字典，如果文件不存在或解析失败则返回空字典。
    """
    return read_json_config(_config_path())


def _save_config(data: dict) -> None:
    """
    保存配置文件。
    将数据序列化为 JSON 并写入配置文件，设置适当的文件权限。
    """
    write_json_config(_config_path(), data)


def _version() -> str:
    """
    获取 web-agent 包的版本号。
    返回包的版本字符串，如果未安装则返回空字符串。
    """
    try:
        return version("web-agent")
    except PackageNotFoundError:
        return ""
    except Exception:
        return ""


def _env_disabled() -> bool:
    """
    检查环境变量是否禁用了遥测功能。
    如果任一环境变量设置为禁用值则返回 True。
    """
    return any((os.environ.get(name) or "").lower() in {"0", "false", "no", "off"} for name in DISABLE_ENVS)


def _valid_install_id(raw) -> bool:
    """
    验证安装 ID 是否有效。
    检查是否为符合 UUID 格式的字符串（32-36 个十六进制字符）。
    """
    return isinstance(raw, str) and re.fullmatch(r"[0-9a-f-]{32,36}", raw) is not None


def _install_id(config: dict | None = None, *, create: bool = True) -> str | None:
    """
    获取或创建安装 ID。
    从配置中读取安装 ID，如果无效且 create 为 True 则生成新的 UUID 并保存。
    """
    config = config if config is not None else _load_config()
    raw = config.get("install_id")
    if _valid_install_id(raw):
        return raw
    if not create:
        return None
    install_id = str(uuid.uuid4())
    _save_config({**config, "install_id": install_id})
    return install_id


def is_enabled() -> bool:
    """
    检查遥测功能是否启用。
    如果环境变量未禁用且配置中未禁用则返回 True。
    """
    if _env_disabled():
        return False
    return not bool(_load_config().get("disabled"))


def status() -> dict:
    """
    获取遥测功能状态信息。
    返回包含启用状态、禁用原因、安装 ID 和配置路径的字典。
    """
    config = _load_config()
    env_disabled = _env_disabled()
    enabled = not env_disabled and not bool(config.get("disabled"))
    return {
        "enabled": enabled,
        "disabled_by_env": env_disabled,
        "disabled_by_config": bool(config.get("disabled")),
        "install_id": _install_id(config, create=enabled),
        "config_path": str(_config_path()),
    }


def set_enabled(enabled: bool) -> dict:
    """
    设置遥测功能的启用状态。
    更新配置中的 disabled 字段并保存，然后返回新的状态信息。
    """
    config = _load_config()
    config["disabled"] = not enabled
    _save_config(config)
    return status()


def _safe_properties(properties: dict | None) -> dict:
    """
    过滤和清理属性数据。
    移除敏感信息，限制字符串长度，确保属性安全可发送。
    """
    out = {}
    for key, value in (properties or {}).items():
        safe_key = re.sub(r"[^A-Za-z0-9_$.-]+", "_", str(key))[:80]
        lowered = safe_key.lower()
        if not safe_key or any(word in lowered for word in FORBIDDEN_KEYS):
            continue
        if isinstance(value, bool) or value is None:
            out[safe_key] = value
        elif isinstance(value, int | float):
            out[safe_key] = value
        else:
            safe_value = str(value)
            if "://" in safe_value:
                safe_value = "[redacted]"
            out[safe_key] = safe_value[:120]
    return out


def capture(event: str, properties: dict | None = None) -> None:
    """
    捕获并发送遥测事件。
    如果遥测启用，将事件数据和系统信息发送到 PostHog。
    """
    if not is_enabled():
        return
    try:
        config = _load_config()
        props = {
            "web_agent_version": _version() or "unknown",
            "python_version": platform.python_version(),
            "os": platform.system() or "unknown",
            "machine": platform.machine() or "unknown",
            "$process_person_profile": False,
            **_safe_properties(properties),
        }
        payload = {
            "api_key": POSTHOG_KEY,
            "distinct_id": _install_id(config),
            "event": event,
            "properties": props,
        }
        data = json.dumps(payload).encode("utf-8")
        host = os.environ.get("WA_POSTHOG_HOST", POSTHOG_HOST).rstrip("/")
        req = urllib.request.Request(
            f"{host}/i/v0/e/",
            method="POST",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "web-agent"},
        )
        urllib.request.urlopen(req, timeout=float(os.environ.get("WA_TELEMETRY_TIMEOUT", "1"))).close()
    except Exception:
        return


def run_telemetry_cli(argv: list[str]) -> int:
    """
    运行遥测命令行接口。
    处理 status、enable、disable 命令，返回退出码。
    """
    if not argv or argv == ["status"]:
        print(json.dumps(status(), indent=2))
        return 0
    if argv == ["disable"]:
        print(json.dumps(set_enabled(False), indent=2))
        return 0
    if argv == ["enable"]:
        print(json.dumps(set_enabled(True), indent=2))
        return 0
    print("usage: web-agent telemetry [status|enable|disable]")
    return 2
