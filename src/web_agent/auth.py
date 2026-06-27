"""web-agent 认证模块。

此模块提供认证相关的辅助函数和错误类型。
"""
from __future__ import annotations

import os
from pathlib import Path

from . import paths


class AuthError(RuntimeError):
    """认证相关错误。"""
    pass


def auth_path() -> Path:
    """返回认证文件路径。"""
    override = os.environ.get("WA_AUTH_PATH")
    if override:
        return Path(override).expanduser()
    return paths.config_dir() / "auth.json"


def auth_status() -> dict:
    """返回认证状态。"""
    return {"status": "missing", "source": None, "path": str(auth_path())}
