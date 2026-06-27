# 连接与标签页可见性

## 地址栏弹出窗口问题

Chrome 刚启动时，唯一的 CDP `type: "page"` 目标是 `chrome://inspect` 和 `chrome://omnibox-popup.top-chrome/`（一个 1 像素的不可见视口）。如果守护进程附加到了地址栏弹出窗口，后续所有操作——包括 `new_tab()` 和 `goto_url()`——都会在 CDP 中存在但可能在 Chrome 界面中不可见的标签页上执行。

守护进程的 `attach_first_page()` 通过在没有真实页面时创建一个 `about:blank` 标签页来处理此问题。如果你仍然停留在不可见的标签页上，可以使用 `switch_tab()`，它会调用 `Target.activateTarget` 将标签页置于前台。

## 启动序列

1. 使用 `daemon_alive()` 检查守护进程是否已在运行
2. 如果存在过期的套接字但守护进程已死亡，清理它们
3. 使用 `list_tabs()` 列出打开的标签页，查看有哪些可用
4. `ensure_real_tab()` 附加到一个真实页面
5. `switch_tab(target_id)` 同时附加并激活（置于前台）

```python
if not daemon_alive():
    import os, ipc
    ipc.cleanup_endpoint("default")
    pid = ipc.pid_path("default")
    if pid.exists(): pid.unlink()
    ensure_daemon()

tabs = list_tabs()
for t in tabs:
    print(t["url"][:60])

tab = ensure_real_tab()
```

## 将 Chrome 置于前台

如果 Chrome 被其他窗口遮挡或在其他桌面上：

```python
import subprocess
subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
```

## 导航

优先在现有标签页上导航，而不是使用 `new_tab()`。通过 CDP 的 `Target.createTarget` 创建的标签页虽然可见，但可能会在活动标签页后面打开。

```python
tab = ensure_real_tab()
goto_url("https://example.com")
```
