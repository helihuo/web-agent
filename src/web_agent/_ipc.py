"""守护进程 IPC 管道。POSIX 系统使用 AF_UNIX socket，Windows 使用 TCP 环回地址。"""
import asyncio, json, os, re, secrets, socket, subprocess, sys
from pathlib import Path

from . import paths

IS_WINDOWS = sys.platform == "win32"
# 调用方提供的两个目录：
#   WA_RUNTIME_DIR — 用于 sock/port/pid。macOS 上 AF_UNIX sun_path 限制为 104 字节，
#       因此运行时目录必须较短。调用方负责保持路径长度在预算内。
#       回退到 WA_TMP_DIR（遗留的单目录调用方），然后到 web-agent 运行时目录。
#   WA_TMP_DIR — 用于截图、调试覆盖层、守护进程日志。对路径长度不敏感；
#       调用方可以使用较深的持久化路径。
# 默认情况下，调用方提供的目录被视为每个实例独立，文件使用裸 "wa" 词干。
# 当目录被多个 BU_NAME 值共享且文件名必须携带名称时，
# 设置 WA_RUNTIME_DIR_SHARED=1 或 WA_TMP_DIR_SHARED=1。
WA_TMP_DIR = os.environ.get("WA_TMP_DIR")
WA_RUNTIME_DIR = os.environ.get("WA_RUNTIME_DIR") or WA_TMP_DIR
WA_RUNTIME_DIR_SHARED = os.environ.get("WA_RUNTIME_DIR_SHARED") == "1"
WA_TMP_DIR_SHARED = os.environ.get("WA_TMP_DIR_SHARED") == "1"
_TMP = paths.tmp_dir()
_RUNTIME = paths.ensure_private_dir(Path(WA_RUNTIME_DIR).expanduser().resolve()) if WA_RUNTIME_DIR else paths.runtime_dir()
_TMP.mkdir(parents=True, exist_ok=True)
_RUNTIME.mkdir(parents=True, exist_ok=True)
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")

# 由 serve() 在 Windows 上设置。守护进程的 handle() 要求每个请求都携带
# 此令牌（TCP 环回没有 chmod 等效机制，否则任何本地进程都可以发出 CDP 命令）。
# 在 POSIX 上保持 None，因为 AF_UNIX + chmod 600 就是安全边界。
_server_token = None


def _check(name):  # BU_NAME 的路径遍历防护
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"invalid BU_NAME {name!r}: must match [A-Za-z0-9_-]{{1,64}}")
    return name


def _runtime_stem(name):  # WA_RUNTIME_DIR 隔离时使用 "wa"，否则使用 "wa-<NAME>"
    _check(name)
    return "wa" if WA_RUNTIME_DIR and not WA_RUNTIME_DIR_SHARED else f"wa-{name}"


def _tmp_stem(name):  # WA_TMP_DIR 隔离时使用 "wa"，否则使用 "wa-<NAME>"
    _check(name)
    return "wa" if WA_TMP_DIR and not WA_TMP_DIR_SHARED else f"wa-{name}"


def log_path(name):   return _TMP / f"{_tmp_stem(name)}.log"
def pid_path(name):   return _RUNTIME / f"{_runtime_stem(name)}.pid"
def port_path(name):  return _RUNTIME / f"{_runtime_stem(name)}.port"  # 仅 Windows：保存 {"port","token"} JSON
def _sock_path(name): return _RUNTIME / f"{_runtime_stem(name)}.sock"


def _read_port_file(name):
    """从 Windows 端口文件读取 (port, token)，任何失败时返回 (None, None)。"""
    try:
        d = json.loads(port_path(name).read_text())
        return int(d["port"]), d["token"]
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError):
        return None, None


def sock_addr(name):  # 仅用于显示，在日志行中使用
    if not IS_WINDOWS: return str(_sock_path(name))
    port, _ = _read_port_file(name)
    return f"127.0.0.1:{port}" if port else f"tcp:{_runtime_stem(name)}"


def spawn_kwargs():  # subprocess.Popen 标志，使守护进程脱离当前终端
    if IS_WINDOWS:
        # CREATE_NO_WINDOW：守护进程不创建控制台窗口。CREATE_NEW_PROCESS_GROUP：
        # 守护进程不会收到发送给父终端的 Ctrl-C/Ctrl-Break 信号，因此关闭该终端
        # 不会杀死它。有意省略 DETACHED_PROCESS：根据 Win32 文档，它会覆盖
        # CREATE_NO_WINDOW，导致 Windows 为（仍然是控制台子系统的）python.exe
        # 分配一个新的控制台。
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def connect(name, timeout=1.0):
    """阻塞式客户端。返回 (sock, token)；token 在 POSIX 上为 None，在 Windows 上为十六进制字符串。
    在 Windows 上发送 JSON 请求的调用方必须将 token 作为 req["token"] 包含在内。"""
    if not IS_WINDOWS:
        # Windows 上的 uv-Python 缺少 socket.AF_UNIX，因此此分支必须进行条件守卫。
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout); s.connect(str(_sock_path(name))); return s, None
    port, token = _read_port_file(name)
    if port is None: raise FileNotFoundError(str(port_path(name)))
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout); return s, token


def request(c, token, req):
    """在已打开的 socket 上执行一次性发送 + 接收 + 解析。在 Windows 上注入 token。
    返回解析后的 JSON 响应。调用方负责关闭 socket。"""
    if token: req = {**req, "token": token}
    c.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(1 << 16)
        if not chunk: break
        data += chunk
    return json.loads(data or b"{}")


def ping(name, timeout=1.0):
    """当且仅当存活守护进程响应 ping 时返回 True。防止过期的 .port 文件和端口复用：
    裸 TCP 连接可能成功连接到守护进程崩溃后占用该端口的无关进程；
    只有我们的守护进程会回答 {"pong":true}。"""
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return False
    try:
        resp = request(c, token, {"meta": "ping"})
        # request() 返回解析后的 JSON，可能是任何有效值（来自过期或恶意端点的
        # 列表、标量等）。任何不是 {pong: true} 字典的值都视为"不是我们的
        # 守护进程"——永远不要盲目调用 .get()。
        return isinstance(resp, dict) and resp.get("pong") is True
    except (OSError, ValueError, AttributeError):
        return False
    finally:
        try: c.close()
        except OSError: pass


def identify(name, timeout=1.0):
    """返回存活守护进程的 PID，若不可达则返回 None。

    由 restart_daemon() 使用，用于向身份已端到端验证的进程（存活 IPC +
    自报 PID）发送信号，而非信任可能已被无关进程复用的 pid 文件中的数字。"""
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return None
    try:
        resp = request(c, token, {"meta": "ping"})
        # request() 返回解析后的 JSON，可能是任何有效值（来自过期或恶意端点的
        # 列表、标量等）。任何不是 {pong: true} 字典的值返回 None——永远不要
        # 对非字典类型调用 .get()。
        if not isinstance(resp, dict) or resp.get("pong") is not True:
            return None
        pid = resp.get("pid")
        # `type(pid) is int`（而非 isinstance）有意拒绝 bool：在 Python 中
        # isinstance(True, int) 为 True，因此恶意或有缺陷的守护进程可能回复
        # {"pid": True}，而我们将其视为 PID 1（init 进程）。
        # 同时拒绝 0 和负数——os.kill(0, sig) 会向调用进程组中的所有进程发送信号，
        # os.kill(-1, sig) 会向调用方能访问的所有进程发送信号。上限为 2**31，
        # 因为 C 的 pid_t 通常是有符号 32 位整数，超出该范围的值会导致 os.kill()
        # 抛出 OverflowError，该异常会在 restart_daemon() 执行清理之前传播出去。
        # Linux 的 pid_max 在实践中也被限制为 2**22。
        return pid if type(pid) is int and 0 < pid < (1 << 31) else None
    except (OSError, ValueError, AttributeError):
        return None
    finally:
        try: c.close()
        except OSError: pass


async def serve(name, handler):
    """运行服务器直到被取消。handler(reader, writer) 在两种平台上看到相同的接口。"""
    global _server_token
    if not IS_WINDOWS:
        path = str(_sock_path(name))
        if os.path.exists(path): os.unlink(path)
        # umask 0o077 使 bind() 以 0600 权限创建 socket——在 chmod 之前没有 TOCTOU 时间窗口。
        old_umask = os.umask(0o077)
        try: server = await asyncio.start_unix_server(handler, path=path)
        finally: os.umask(old_umask)
        _server_token = None
        async with server: await asyncio.Event().wait()
        return
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    _server_token = secrets.token_hex(32)
    pf = port_path(name)
    # 原子写入，确保并发读取者永远不会看到写入一半的文件。
    tmp = pf.with_name(pf.name + ".tmp")
    tmp.write_text(json.dumps({"port": port, "token": _server_token}))
    os.replace(tmp, pf)
    try:
        async with server: await asyncio.Event().wait()
    finally:
        try: pf.unlink()
        except FileNotFoundError: pass


def expected_token():
    """正在运行的守护进程所接受的 token，POSIX 上为 None。"""
    return _server_token


def cleanup_endpoint(name):  # 尽力清理；若已不存在则静默忽略
    p = _sock_path(name) if not IS_WINDOWS else port_path(name)
    try: p.unlink()
    except FileNotFoundError: pass
