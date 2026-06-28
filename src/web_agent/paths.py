"""web-agent 文件系统布局。

.env 文件支持行内注释（值后面的 # 注释），引号内的 # 不受影响。
例如：KEY=value # 这是注释、KEY="value#not_comment"。
"""
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


def _strip_env_inline_comment(value: str) -> str:
    """剥离 .env 值中的行内注释（# 后面的内容），保留引号内的 # 不受影响。"""
    in_single = False  # 是否在单引号字符串内
    in_double = False  # 是否在双引号字符串内
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single  # 切换单引号状态
        elif ch == '"' and not in_single:
            in_double = not in_double  # 切换双引号状态
        elif ch == '#' and not in_single and not in_double:
            return value[:i]  # 找到引号外的 #，截断注释
    return value


def _load_env_file(p):
    """解析 .env 文件并设置环境变量，支持行内注释。"""
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = _strip_env_inline_comment(v)  # 剥离行内注释
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_env():
    """加载 .env 文件（仓库根目录和工作空间目录）。"""
    repo_root = Path(__file__).resolve().parents[2]  # 仓库根目录
    workspace = workspace_dir()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _strip_jsonc_comments(text: str) -> str:
    """剥离 JSONC 风格的 // 单行注释，保留字符串内的 // 不受影响。"""
    import re
    result = []  # 存储处理后的行
    for line in text.splitlines():
        in_string = False  # 当前是否在双引号字符串内
        slash_pos = -1  # 注释 // 的起始位置，-1 表示未找到
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and (i == 0 or line[i - 1] != '\\'):
                in_string = not in_string  # 切换字符串状态
            elif ch == '/' and not in_string and i + 1 < len(line) and line[i + 1] == '/':
                slash_pos = i  # 找到字符串外的 // 注释
                break
            i += 1
        if slash_pos >= 0:
            result.append(line[:slash_pos])  # 截断注释部分
        else:
            result.append(line)
    return "\n".join(result)


def read_json_config(path: Path) -> dict:
    """读取 JSON/JSONC 配置文件，支持 // 单行注释，文件不存在或解析失败时返回空字典。"""
    try:
        raw = path.read_text(encoding="utf-8")
        cleaned = _strip_jsonc_comments(raw)  # 剥离注释后再解析
        return json.loads(cleaned)
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
