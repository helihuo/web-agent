import os, sys, urllib.request

# Windows default stdout encoding is cp1252, which can't encode the 🐴 marker
# helpers prepend to tab titles (or anything else outside Latin-1). Force UTF-8
# so `print(page_info())` doesn't UnicodeEncodeError on Windows. Issue #124(4).
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from .admin import (
    _version,
    NAME,
    daemon_alive,
    ensure_daemon,
    list_cloud_profiles,
    list_local_profiles,
    print_update_banner,
    restart_daemon,
    run_doctor,
    run_doctor_fix_snap,
    run_update,
    start_remote_daemon,
    stop_remote_daemon,
    sync_local_profile,
)
from . import auth, telemetry
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
  web-agent auth login          sign in to Browser Use Cloud for cloud browsers
  web-agent auth login --device-code   sign in from SSH/headless environments
  web-agent auth status         show Browser Use Cloud auth state
  web-agent auth logout         remove stored Browser Use Cloud auth
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


# Probe /json/version (not a bare TCP connect) so a non-Chrome process bound to
# 9222/9223 doesn't masquerade as Chrome and skip the cloud bootstrap. Mirrors
# daemon.py's fallback probe.
def _local_chrome_listening():
    for port in (9222, 9223):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.3).close()
            return True
        except OSError: pass
    return False


# BU_CDP_URL / BU_CDP_WS are documented to override local Chrome discovery
# (install.md:58-59), so they must also block cloud auto-bootstrap. Without this
# guard, start_remote_daemon() in admin.py overwrites BU_CDP_WS in the daemon
# env with a cloud WebSocket URL, silently replacing the user's explicit endpoint
# *and* billing them for a cloud browser they never asked for.
def _explicit_cdp_configured():
    return bool(os.environ.get("BU_CDP_URL") or os.environ.get("BU_CDP_WS"))


def _cloud_auth_configured():
    try:
        auth.get_browser_use_api_key()
        return True
    except (auth.CloudAuthRequired, auth.AuthError, OSError):
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
    if first in {"auth", "skill", "telemetry"}:
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
    if args and args[0] == "auth":
        sys.exit(auth.run_auth_cli(args[1:]))
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
    # Auto-bootstrap a cloud browser is opt-in via BU_AUTOSPAWN — BROWSER_USE_API_KEY alone
    # is not enough, since the key is commonly set for unrelated reasons (profile sync,
    # cloud API calls, parent agents managing their own session). An explicit BU_CDP_URL
    # or BU_CDP_WS also blocks the spawn so we honour the precedence install.md promises.
    cloud_admin = code.lstrip().startswith(("start_remote_daemon(", "stop_remote_daemon("))
    if not cloud_admin:
        if (
            not daemon_alive()
            and not _local_chrome_listening()
            and not _explicit_cdp_configured()
            and _cloud_auth_configured()
            and os.environ.get("BU_AUTOSPAWN")
        ):
            start_remote_daemon(NAME)
        ensure_daemon()
    exec(code, globals())


if __name__ == "__main__":
    main()
