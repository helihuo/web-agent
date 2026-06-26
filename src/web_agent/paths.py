"""web-agent 文件系统布局。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def home_dir() -> Path:
    raw = os.environ.get("WA_HOME") or os.environ.get("WEB_AGENT_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return (Path(base).expanduser() / "web-agent").resolve()
    return (Path.home() / ".config" / "web-agent").resolve()


def ensure_private_dir(path: Path) -> Path:
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if not existed and sys.platform != "win32":
        os.chmod(path, 0o700)
    return path


def config_dir() -> Path:
    raw = os.environ.get("WA_CONFIG_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir())


def runtime_dir() -> Path:
    raw = os.environ.get("WA_RUNTIME_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "runtime")


def tmp_dir() -> Path:
    raw = os.environ.get("WA_TMP_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "tmp")


def workspace_dir() -> Path:
    raw = os.environ.get("WA_AGENT_WORKSPACE")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "agent-workspace")


def _load_env_file(p):
    """解析 .env 文件并设置环境变量。"""
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_env():
    """加载 .env 文件（仓库根目录和工作空间目录）。"""
    repo_root = Path(__file__).resolve().parents[2]  # 仓库根目录
    workspace = workspace_dir()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def read_json_config(path: Path) -> dict:
    """读取 JSON 配置文件，文件不存在或解析失败时返回空字典。"""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, OSError, ValueError):
        return {}


def write_json_config(path: Path, data: dict, dir_mode: int = 0o700, file_mode: int = 0o600) -> None:
    """写入 JSON 配置文件，自动创建父目录并设置权限。

    Args:
        path: 配置文件路径
        data: 要写入的字典数据
        dir_mode: 父目录权限（仅非 Windows），默认 0o700
        file_mode: 文件权限（仅非 Windows），默认 0o600
    """
    try:
        parent_existed = path.parent.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed and sys.platform != "win32":
            os.chmod(path.parent, dir_mode)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        if sys.platform != "win32":
            os.chmod(path, file_mode)
    except OSError:
        pass
