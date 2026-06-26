import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import _ipc as ipc
from . import auth
from . import paths
from .helpers import NAME, truncate_text
from .paths import _load_env, _load_env_file, read_json_config, write_json_config
from .telemetry import _version

_load_env()


def _process_start_time(pid):
    """获取指定 PID 的不透明进程启动时间指纹，不可用时返回 None。

    两次读取返回相同的非 None 值表示 PID 仍然指向同一个进程；
    不同的值表示 PID 已被复用。restart_daemon() 使用此方法在
    daemon 已拆除其 IPC socket（例如在缓慢的远程关闭期间）时，
    仍能保持强制终止恢复路径正常工作，而不会退回到"信任 pid 文件"
    ——那样会重新引入 PID 复用的风险。

    Linux:   /proc/<pid>/stat 字段 22（自启动以来的时钟滴答数）。
    macOS:   `ps -o lstart= -p <pid>`（绝对时间戳字符串）。
    Windows: 通过 ctypes 调用 GetProcessTimes（FILETIME 创建时间，自 1601 年起 100 纳秒）。
    其他平台：返回 None；restart_daemon 会退回到严格的身份验证检查，
    这比完全不检查更安全。
    """
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                raw = f.read().decode("ascii", errors="replace")
        except (FileNotFoundError, PermissionError, OSError):
            return None
        # 字段 2 是 `(comm)`；comm 可以包含空格和括号，因此从最后一个 `)` 之后分割并索引
        try:
            tail = raw[raw.rindex(")") + 2:].split()
            return tail[19]  # starttime 是字段 22（0 索引：21 - 跳过的 2 = 19）
        except (ValueError, IndexError):
            return None
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                stderr=subprocess.DEVNULL, timeout=2,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        s = out.decode("ascii", errors="replace").strip()
        return s or None
    if sys.platform == "win32":
        # Windows 平台：使用 ctypes 调用 GetProcessTimes 读取内核报告的创建时间，
        # 作为 64 位 FILETIME（自 1601-01-01 起的 100 纳秒间隔）。
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            ]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
        except (OSError, AttributeError):
            return None
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_ft = wintypes.FILETIME()
            kernel_ft = wintypes.FILETIME()
            user_ft = wintypes.FILETIME()
            ok = kernel32.GetProcessTimes(
                h, ctypes.byref(creation), ctypes.byref(exit_ft),
                ctypes.byref(kernel_ft), ctypes.byref(user_ft),
            )
            if not ok:
                return None
            return (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        finally:
            kernel32.CloseHandle(h)
    return None


PYPI_JSON = "https://pypi.org/pypi/web-agent/json"
VERSION_CACHE = paths.config_dir() / "version-cache.json"
VERSION_CACHE_TTL = 24 * 3600
DOCTOR_TEXT_LIMIT = 140


def _log_tail(name):
    try:
        return ipc.log_path(name or NAME).read_text().strip().splitlines()[-1]
    except (FileNotFoundError, IndexError):
        return None


def _needs_chrome_remote_debugging_prompt(msg):
    """当 Chrome 需要检查页面权限流程时返回 True。"""
    lower = (msg or "").lower()
    return (
        "devtoolsactiveport not found" in lower
        or "enable chrome://inspect" in lower
        or "not live yet" in lower
        or (
            "ws handshake failed" in lower
            and (
                "403" in lower
                or "opening handshake" in lower
                or "timed out" in lower
                or "timeout" in lower
            )
        )
    )


def _needs_chrome_permission_popup(msg):
    """当 Chrome 可达但正在等待每个会话的允许弹窗时返回 True。"""
    lower = (msg or "").lower()
    return "permission-blocked" in lower


def _is_local_chrome_mode(env=None):
    """当 daemon 发现的是本地 Chrome 而非远程 CDP WS 时返回 True。"""
    env = env or {}
    return not (
        env.get("BU_CDP_WS")
        or env.get("BU_CDP_URL")
        or os.environ.get("BU_CDP_WS")
        or os.environ.get("BU_CDP_URL")
    )


def daemon_alive(name=None):
    # 使用 Ping 握手（而非简单的连接），这样在 daemon 崩溃后陈旧的 .port 文件和端口复用
    # 不会让我们误将无关的监听器当作我们的 daemon
    return ipc.ping(name or NAME, timeout=1.0)


def _daemon_endpoint_names():
    # WA_RUNTIME_DIR 为每个目录隔离一个 daemon → 不使用文件名前缀发现，
    # 只检查本地端点是否存在。没有 WA_RUNTIME_DIR 时，
    # 或者 WA_RUNTIME_DIR_SHARED=1 时，_RUNTIME 是共享的，
    # 我们通过 glob `wa-*.<suffix>` 查找该运行时目录中的每个 daemon
    suffix = ".port" if ipc.IS_WINDOWS else ".sock"
    if ipc.WA_RUNTIME_DIR and not ipc.WA_RUNTIME_DIR_SHARED:
        return [NAME] if (ipc._RUNTIME / f"wa{suffix}").exists() else []
    names = []
    for p in sorted(ipc._RUNTIME.glob(f"wa-*{suffix}")):
        raw = p.name[3:-len(suffix)]
        try:
            ipc._check(raw)
        except ValueError:
            continue
        names.append(raw)
    return names


def _daemon_browser_connection(name):
    c = None
    try:
        c, token = ipc.connect(name, timeout=1.0)
        response = ipc.request(c, token, {"meta": "connection_status"})
        if "error" in response:
            return None
        page = response.get("page")
        if page:
            page = {"title": page.get("title") or "(untitled)", "url": page.get("url") or ""}
        return {"name": name, "page": page}
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError, KeyError, ValueError, json.JSONDecodeError):
        return None
    finally:
        if c:
            c.close()


def browser_connections():
    """具有健康 CDP 浏览器连接的实时 web-agent daemon 及其附加页面。"""
    out = []
    for name in _daemon_endpoint_names():
        conn = _daemon_browser_connection(name)
        if conn:
            out.append(conn)
    return out


def active_browser_connections():
    """统计具有健康 CDP 浏览器连接的实时 web-agent daemon 数量。"""
    return len(browser_connections())


def _doctor_short_text(value, limit=None):
    limit = limit or DOCTOR_TEXT_LIMIT
    return truncate_text(value, limit)


def _is_snap_browser(path: str) -> bool:
    """当 Chrome 二进制路径位于 /snap/ 下（Linux 上的 Snap 沙箱）时返回 True。"""
    # 将路径中的反斜杠替换为正斜杠，确保 Windows 和 POSIX 路径格式一致
    normalized_path = path.replace("\\", "/")
    return bool(path) and "/snap/" in normalized_path.lower()


def _doctor_snap_probe_path(path: str) -> str:
    raw = str(path)
    try:
        resolved = os.path.realpath(raw)
    except OSError:
        resolved = raw
    return raw if _is_snap_browser(raw) else resolved


def _doctor_probe_chrome_binary_for_snap():
    """返回找到的第一个 Chrome/Chromium 二进制的 (标签, 探测路径)，否则返回 (None, None)。

    在搜索 PATH 中的常见名称之前，优先使用 WA_CHROME_PATH 和 CHROME_PATH。
    """

    for key in ("WA_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser()
        try:
            if p.is_file():
                return (p.name, _doctor_snap_probe_path(str(p)))
        except OSError:
            continue
    for cmd in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium"):
        w = shutil.which(cmd)
        if not w:
            continue
        try:
            return (cmd, _doctor_snap_probe_path(w))
        except OSError:
            continue
    return (None, None)


def _snap_linux_headless_doc_url():
    return "https://github.com/helihuo/web-agent/blob/main/docs/snap-linux-headless.md"


def run_doctor_fix_snap():
    """打印将 Snap Chromium 替换为原生 Chrome 以支持 CDP 的步骤。始终返回 0。"""
    doc = _snap_linux_headless_doc_url()
    print("web-agent doctor --fix-snap")
    print()
    print("Snap-packaged Chromium cannot expose DevTools the way web-agent needs.")
    print(f"Full background: {doc}")
    print()
    print("1. Install Google Chrome from Google's .deb (not the Snap store):")
    print("   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
    print("   sudo apt install ./google-chrome-stable_current_amd64.deb")
    print()
    print("2. Point the harness (and your shell) at the native binary so PATH does not")
    print("   pick the Snap wrapper first. Example for bash (~/.bashrc or session env):")
    print("   export WA_CHROME_PATH=/usr/bin/google-chrome-stable")
    print("   # CHROME_PATH is also honored by doctor's snap probe if you prefer that name.")
    print()
    print("3. Launch Chrome from that path (Way 2) or open Chrome normally (Way 1),")
    print("   enable remote debugging per install.md, then verify:")
    print("   web-agent --doctor")
    print()
    return 0


def ensure_daemon(wait=60.0, name=None, env=None):
    """幂等操作。自动修复陈旧的 daemon、冷启动的 Chrome 以及 chrome://inspect 上缺失的允许操作。"""
    if daemon_alive(name):
        # 陈旧的 daemon 会接受连接并回复 meta:*（纯 Python），即使到 Chrome 的 CDP WS 已断开
        # ——使用真实的 CDP 调用进行探测并要求返回 "result"
        # 必须通过 ipc.connect 以便在 Windows（TCP 环回）上也能正常工作；
        # 直接使用 AF_UNIX 会在每次热调用时失败并导致 daemon  churn
        try:
            s, token = ipc.connect(name or NAME, timeout=3.0)
            resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
            if "result" in resp: return
        except Exception: pass
        restart_daemon(name)

    local = _is_local_chrome_mode(env)
    for attempt in (0, 1):
        e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
        p = subprocess.Popen(
            [sys.executable, "-m", "web_agent.daemon"],
            env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **ipc.spawn_kwargs(),
        )
        deadline = time.time() + wait
        while time.time() < deadline:
            if daemon_alive(name): return
            if p.poll() is not None: break
            time.sleep(0.2)
        msg = _log_tail(name) or ""
        if local and attempt == 0 and _needs_chrome_permission_popup(msg):
            print('web-agent: Chrome is asking "Allow remote debugging?". Click Allow in Chrome, then retry browser work.', file=sys.stderr)
            restart_daemon(name)
            raise RuntimeError(
                "permission-blocked: wait for the user to click Allow in the Chrome permission popup before retrying."
            )
        if local and attempt == 0 and _needs_chrome_remote_debugging_prompt(msg):
            _open_chrome_inspect()
            print('web-agent: at chrome://inspect/#remote-debugging, tick "Allow remote debugging for this browser instance" and click Allow on the popup that appears', file=sys.stderr)
            restart_daemon(name)
            continue
        raise RuntimeError(msg or f"daemon {name or NAME} didn't come up -- check {ipc.log_path(name or NAME)}")


def restart_daemon(name=None):
    """尽力而为的 daemon 关闭 + socket/pid 清理。

    名称是历史原因：调用者通常在此之后再次调用 `web-agent`，
    这会通过 ensure_daemon() 自动生成一个新的 daemon。
    函数本身只负责停止。

    在任何进程信号之前通过 ipc.identify() 验证身份，
    因此陈旧的 pid 文件（其编号已被无关进程复用）永远不会被 SIGTERM。
    如果 daemon 不可达，我们只清理 pid 文件和 socket 并返回——
    永远不会升级为按 pid 文件强制终止。
    """
    import signal

    name = name or NAME
    pid_path = str(ipc.pid_path(name))

    # 分别跟踪两条信息：
    #   - daemon_pid：daemon 自报告的 PID，或 None。只有运行此版本（或更新版本）的
    #     daemon 会在 ping 响应中包含 `pid`；升级前的 daemon 只返回 {pong: True}，
    #     此处会返回 None。
    #   - daemon_alive：是否有任何 daemon 响应 ping。保持关闭 IPC 路径在升级期间
    #     正常工作——否则，仍在运行的升级前 daemon 的 socket 会在进程存活时被删除。
    daemon_pid = ipc.identify(name, timeout=5.0)
    daemon_alive = daemon_pid is not None or ipc.ping(name, timeout=1.0)
    # 快照 daemon 的进程启动时间作为次要身份检查。
    # IPC socket 可能在进程退出前消失（例如，关闭路径拆除 socket 然后等待缓慢的
    # 远程 `stop` PATCH），因此 identify() 中途返回 None 并不能证明进程已死亡。
    # 在 SIGTERM 之前比较启动时间让我们能够恢复缓慢关闭的原始强制终止行为，
    # 而不会重新打开 PID 复用漏洞——复用的 PID 会有不同的启动时间。
    daemon_start = _process_start_time(daemon_pid)

    if daemon_alive:
        try:
            c, token = ipc.connect(name, timeout=5.0)
            ipc.request(c, token, {"meta": "shutdown"})
            c.close()
        except Exception:
            pass

    if daemon_pid is not None:
        for _ in range(75):
            try:
                os.kill(daemon_pid, 0)
                time.sleep(0.2)
            except (ProcessLookupError, OSError, SystemError, OverflowError):
                break
        else:
            # 在升级为 SIGTERM 之前重新验证身份。两个可接受的信号，按优先级排序：
            #   1. ipc.identify() 仍然返回相同的 PID——daemon 的 IPC 是活跃的，
            #      daemon 卡住了。可以安全终止。
            #   2. 原始 PID 的启动时间指纹未变——同一个进程，只是退出缓慢
            #      （例如，卡在远程停止中）。IPC 可能已经消失；这是预期行为。
            # 如果两者都不成立，PID 可能已被复用；跳过 SIGTERM。
            verified_pid = ipc.identify(name, timeout=1.0)
            same_process = verified_pid == daemon_pid or (
                daemon_start is not None
                and _process_start_time(daemon_pid) == daemon_start
            )
            if same_process:
                try:
                    os.kill(daemon_pid, signal.SIGTERM)
                except (ProcessLookupError, OSError, SystemError, OverflowError):
                    pass

    ipc.cleanup_endpoint(name)
    try:
        os.unlink(pid_path)
    except FileNotFoundError:
        pass


def list_local_profiles():
    """检测此机器上的本地浏览器配置文件。调用 `profile-use list --json`。"""
    if not shutil.which("profile-use"):
        raise RuntimeError("profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh")
    return json.loads(subprocess.check_output(["profile-use", "list", "--json"], text=True))


def _repo_dir():
    """如果是可编辑的 git 克隆安装，返回仓库根目录，否则返回 None。"""
    for p in Path(__file__).resolve().parents:
        if (p / ".git").is_dir():
            return p
    return None


def _install_mode():
    """可编辑克隆返回 "git"，已安装的 wheel 返回 "pypi"，否则返回 "unknown"。"""
    if _repo_dir():
        return "git"
    return "pypi" if _version() else "unknown"


def _cache_read():
    """读取版本缓存文件。"""
    return read_json_config(VERSION_CACHE)


def _cache_write(data):
    """写入版本缓存文件。"""
    write_json_config(VERSION_CACHE, data, dir_mode=0o700, file_mode=0o600)


def _latest_release_tag(force=False):
    """返回最新的 PyPI 版本，或 None。缓存 24 小时以避免频繁请求 PyPI。"""
    cache = _cache_read()
    now = time.time()
    if not force and cache.get("tag") and now - cache.get("fetched_at", 0) < VERSION_CACHE_TTL:
        return cache["tag"]
    try:
        tag = json.loads(urllib.request.urlopen(PYPI_JSON, timeout=5).read()).get("info", {}).get("version") or ""
    except Exception:
        return cache.get("tag")  # 回退到上次已知的版本
    tag = tag.lstrip("v")
    _cache_write({**cache, "tag": tag, "fetched_at": now})
    return tag or None


def _version_tuple(v):
    """尽力而为的 PEP 440 风格解析：alpha < beta < rc < final。"""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?", v or "", re.I)
    if not m:
        return (0, 0, 0, 3, 0)
    nums = [int(p) for p in m.group(1).split(".")[:3]]
    nums.extend([0] * (3 - len(nums)))
    pre = (m.group(2) or "").lower()
    pre_rank = {"a": 0, "b": 1, "rc": 2}.get(pre, 3)
    pre_num = int(m.group(3) or 0)
    return (*nums, pre_rank, pre_num)


def check_for_update():
    """(当前版本, 最新版本, 是否有新版本)。如果 API 不可达且没有缓存，latest 可能为 None。"""
    cur = _version()
    latest = _latest_release_tag()
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    return cur, latest, newer


def print_update_banner(out=None):
    """每天向 stderr 打印一次更新横幅。已是最新或离线时保持静默。"""
    out = out or sys.stderr
    cache = _cache_read()
    today = time.strftime("%Y-%m-%d")
    if cache.get("banner_shown_on") == today:
        return
    cur, latest, newer = check_for_update()
    if not newer:
        return
    print(f"[web-agent] update available: {cur} -> {latest}", file=out)
    print(f"[web-agent] agents: run `web-agent --update -y` to upgrade and restart the daemon", file=out)
    _cache_write({**cache, "banner_shown_on": today})


def _chrome_running():
    """跨平台尽力检查是否有正在运行的基于 Chromium 的浏览器。"""
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.check_output(["tasklist"], text=True, timeout=5)
            names = ("chrome.exe", "msedge.exe", "helium.exe")
        else:
            out = subprocess.check_output(["ps", "-A", "-o", "comm="], text=True, timeout=5)
            names = ("Google Chrome", "chrome", "chromium", "Microsoft Edge", "msedge", "helium")
        return any(n.lower() in out.lower() for n in names)
    except Exception:
        return False


def _open_chrome_inspect():
    """打开 chrome://inspect/#remote-debugging 以便用户可以勾选复选框。"""
    url = "chrome://inspect/#remote-debugging"
    if platform.system() == "Darwin":
        try:
            subprocess.run([
                "osascript",
                "-e", 'tell application "Google Chrome" to activate',
                "-e", f'tell application "Google Chrome" to open location "{url}"',
            ], timeout=5, check=False)
            return
        except Exception:
            pass
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass


def run_doctor():
    """只读诊断。仅当一切看起来健康时返回 0。"""
    cur = _version()
    mode = _install_mode()
    chrome = _chrome_running()
    daemon = daemon_alive()
    connections = browser_connections()
    try:
        auth_state = auth.auth_status()
    except (auth.AuthError, OSError) as e:
        auth_state = {"status": "error", "source": None, "reason": str(e)}
    cloud_auth = auth_state.get("status") == "authenticated"
    latest = _latest_release_tag()
    # 只有当我们知道已安装版本时才声称有更新——否则 `cur or "(unknown)"`
    # 会被解析为 (0,)，导致每个最新版本都被标记为更新版本
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    cur_display = cur or "(unknown)"
    doc_url = _snap_linux_headless_doc_url()

    def row(label, ok, detail=""):
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")

    print("web-agent doctor")
    print(f"  platform          {platform.system()} {platform.release()}")
    print(f"  python            {sys.version.split()[0]}")
    print(f"  version           {cur_display} ({mode})")
    if latest:
        print(f"  latest release    {latest}" + (" (update available)" if newer else ""))
    else:
        print("  latest release    (could not reach PyPI)")
    if platform.system() == "Linux":
        bname, bpath = _doctor_probe_chrome_binary_for_snap()
        if bname and bpath and _is_snap_browser(bpath):
            print("[snap-detect]")
            print(f"Browser: {bname} (snap) — WARNING: Snap confinement prevents CDP binding.")
            print(f"  Fix: Install Chrome natively (see docs/snap-linux-headless.md)")
            print(f"  Docs: {doc_url}")
    row("chrome running", chrome, "" if chrome else "start chrome/edge")
    row("daemon alive", daemon, "" if daemon else "see install.md")
    row("active browser connections", bool(connections), str(len(connections)))
    for conn in connections:
        page = conn.get("page")
        if page:
            title = _doctor_short_text(page["title"])
            url = _doctor_short_text(page["url"])
            print(f"        {conn['name']} — active page: {title} — {url}")
        else:
            print(f"        {conn['name']} — active page: (no real page)")
    row("Browser Use cloud auth", cloud_auth, auth_state.get("source") or auth_state.get("reason") or "optional: web-agent auth login")
    # 核心健康检查 = chrome + daemon。云认证是可选的。
    return 0 if (chrome and daemon) else 1


def _prompt_yes(question, default_yes=True, yes=False):
    if yes:
        return True
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        ans = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default_yes
    if not ans:
        return default_yes
    return ans.startswith("y")


def run_update(yes=False):
    """拉取最新版本并（在提示后）重启 daemon 以加载更改的代码。
    
    成功时返回 0，失败时返回非零值。"""
    cur, latest, newer = check_for_update()
    # 只有当我们确实知道已安装的版本时，才以"已是最新"为由提前返回。
    # 否则 `newer=False` 只意味着"无法比较"——继续执行更新流程。
    if cur and latest and not newer:
        print(f"web-agent is up to date ({cur}).")
        return 0
    if cur and latest:
        print(f"updating web-agent: {cur} -> {latest}")
    elif latest:
        print(f"installed version unknown; will try to update to {latest}.")
    else:
        print("could not reach PyPI; will try to update anyway.")

    mode = _install_mode()
    if mode == "git":
        repo = _repo_dir()
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
        if status.returncode != 0:
            print(f"git status failed: {status.stderr.strip()}", file=sys.stderr)
            return 1
        if status.stdout.strip():
            print(f"refusing to update: uncommitted changes in {repo}", file=sys.stderr)
            print("commit or stash them first, or run `git -C %s pull` yourself." % repo, file=sys.stderr)
            return 1
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"])
        if r.returncode != 0:
            return r.returncode
    elif mode == "pypi":
        tool_upgrade = subprocess.run(["uv", "tool", "upgrade", "web-agent"])
        if tool_upgrade.returncode != 0:
            return tool_upgrade.returncode
    else:
        print("unknown install mode; can't auto-update.", file=sys.stderr)
        return 1

    # 使横幅/标签缓存失效，这样新版本就不会继续提示更新了。
    cache = _cache_read()
    cache.pop("banner_shown_on", None)
    _cache_write(cache)

    if daemon_alive():
        if _prompt_yes("restart the running daemon so it picks up the new code?", default_yes=True, yes=yes):
            restart_daemon()
            print("daemon stopped; it will auto-restart on next `web-agent` call.")
        else:
            print("daemon left running on old code. run `web-agent` and it'll use the new code after the daemon recycles.")
    print("update complete.")
    return 0
