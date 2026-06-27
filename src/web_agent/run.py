import os, sys, urllib.request

"""
Windows 默认标准输出编码为 cp1252，无法编码 🐴 标记
helpers 在标签页标题前添加该标记（或 Latin-1 之外的任何字符）。
强制使用 UTF-8 以避免 `print(page_info())` 在 Windows 上引发 UnicodeEncodeError。
Issue #124(4)。
"""
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from .admin import (
    _version,
    daemon_alive,
    ensure_daemon,
    list_local_profiles,
    print_update_banner,
    restart_daemon,
    run_doctor,
    run_doctor_fix_snap,
    run_update,
)
from . import telemetry
from .helpers import *

HELP = """Web Agent

Read SKILL.md for the default workflow and examples.

Typical usage:
  web-agent <<'PY'
  ensure_real_tab()
  print(page_info())
  PY

Helpers are pre-imported. The daemon auto-starts and connects to the running browser.

Commands:
  web-agent --version        print the installed version
  web-agent --doctor         diagnose install, daemon, and browser state
  web-agent doctor           same as --doctor
  web-agent doctor --fix-snap   print how to fix Snap Chromium blocking CDP (Linux)
  web-agent skill               print the web-agent skill text
  web-agent telemetry status    show anonymous telemetry opt-out state
  web-agent --update [-y]    pull the latest version (agents: pass -y)
  web-agent --reload         stop the daemon so next call picks up code changes
"""

USAGE = """Usage:
  web-agent <<'PY'
  print(page_info())
  PY
"""


# 探测 /json/version（而非简单的 TCP 连接），避免绑定到 9222/9223 的非 Chrome 进程
# 被误认为 Chrome。与 daemon.py 的回退探测逻辑一致。
def _local_chrome_listening():
    for port in (9222, 9223):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.3).close()
            return True
        except OSError: pass
    return False


def _print_skill():
    from importlib import resources
    print(resources.files("web_agent").joinpath("SKILL.md").read_text(), end="")


def _telemetry_command(args):
    if not args:
        return "script"
    first = args[0]
    if first in {"-h", "--help"}:
        return "help"
    if first == "--version":
        return "version"
    if first in {"--doctor", "doctor"}:
        return "doctor"
    if first == "--update":
        return "update"
    if first == "--reload":
        return "reload"
    if first == "--debug-clicks":
        return "debug-clicks"
    if first in {"skill", "telemetry"}:
        return first
    return "usage"


def main():
    args = sys.argv[1:]
    if not (args and args[0] == "telemetry"):
        telemetry.capture("web_agent.cli", {"command": _telemetry_command(args)})
    if args and args[0] in {"-h", "--help"}:
        print(HELP)
        return
    if args and args[0] == "--version":
        print(_version() or "unknown")
        return
    if args and args[0] == "--doctor":
        sys.exit(run_doctor())
    if args and args[0] == "doctor":
        rest = args[1:]
        if rest == ["--fix-snap"]:
            sys.exit(run_doctor_fix_snap())
        if rest:
            print("usage: web-agent doctor [--fix-snap]", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_doctor())
    if args and args[0] == "skill":
        if len(args) != 1:
            print("usage: web-agent skill", file=sys.stderr)
            sys.exit(2)
        _print_skill()
        return
    if args and args[0] == "telemetry":
        sys.exit(telemetry.run_telemetry_cli(args[1:]))
    if args and args[0] == "--update":
        yes = any(a in {"-y", "--yes"} for a in args[1:])
        sys.exit(run_update(yes=yes))
    if args and args[0] == "--reload":
        restart_daemon()
        print("daemon stopped — will restart fresh on next call")
        return
    if args and args[0] == "--debug-clicks":
        os.environ["WA_DEBUG_CLICKS"] = "1"
        args = args[1:]
    if not args and not sys.stdin.isatty():
        code = sys.stdin.read()
        if not code.strip():
            sys.exit(USAGE)
    else:
        sys.exit(USAGE)
    print_update_banner()
    # 确保 daemon 正在运行（无论 Chrome 是否监听，daemon 都必须启动）
    if not daemon_alive():
        ensure_daemon()
    exec(code, globals())


if __name__ == "__main__":
    main()
