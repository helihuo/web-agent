---
name: web-agent
description: "Always use web-agent for any web interaction: automation, scraping, testing, or site/app work."
---

# web-agent

通过 CDP 直接控制浏览器。针对特定任务的编辑，使用 `agent-workspace/agent_helpers.py`。如遇设置、安装或连接问题，请阅读 web-agent/install.md。

域技能默认关闭。设置 `WA_DOMAIN_SKILLS=1` 可启用；参见底部章节。

**如果** **`WA_DOMAIN_SKILLS=1`** **且任务是特定站点相关的，在自行发明方案之前，请先阅读对应** **`$WA_AGENT_WORKSPACE/domain-skills/<site>/`** **目录下的所有文件。**

## 用法

```bash
web-agent <<'PY'
print(page_info())
PY
```

- 以 `web-agent` 调用。多行命令请使用 heredoc。
- 辅助函数已预导入。`run.py` 在 `exec` 之前会调用 `ensure_daemon()`。
- 首次导航使用 `new_tab(url)`，而非 `goto_url(url)`。
- 正常的本地流程会附加到正在运行的 Chrome/Chromium CDP 端点。无需浏览器 ID 或本地配置文件选择。

## 本地 Chrome

如果守护进程无法连接，运行诊断：

```bash
web-agent --doctor
```

如果 Chrome 远程调试未启用，工具链会打开：

```text
chrome://inspect/#remote-debugging
```

请用户勾选"Allow remote debugging for this browser instance"，如果 Chrome 弹出权限提示框请点击允许。然后重试相同的 `web-agent` 命令。

##

## 页面工作流

- 优先截图：使用 `capture_screenshot()` 了解可见状态。
- 点击流程：截图 → 读取像素 → `click_at_xy(x, y)` → 再次截图。
- 导航后，调用 `wait_for_load()`。
- 如果当前标签页已过期或是内部页面，调用 `ensure_real_tab()`。
- 当坐标不适合时，使用 `js(...)` 进行 DOM 检查或数据提取。
- 登录墙：停止并询问用户。例外：当 Chrome 已登录时，自动使用可用的 SSO；但对于密码、MFA、用户同意或账户选择不明确的情况仍需停止并询问。
- 截图 vs JS：不确定页面状态时截图；已知结构只需数据或精确交互时用 `js()`。
- 原始 CDP 可通过 `cdp("Domain.method", ...)` 使用。

## 交互技能

- connection.md
- cookies.md
- cross-origin-iframes.md
- dialogs.md
- downloads.md
- drag-and-drop.md
- dropdowns.md
- iframes.md
- network-requests.md
- print-as-pdf.md
- profile-sync.md
- screenshots.md
- scrolling.md
- shadow-dom.md
- tabs.md
- uploads.md
- viewport.md

## 设计约束

- 默认使用坐标点击。CDP 鼠标事件在合成器层面可穿透 iframe/shadow/跨域。
- 保持连接模型简单：使用默认守护进程，`BU_NAME`、`BU_CDP_URL` 或 `BU_CDP_WS`。
- 核心辅助函数保持精简。将特定任务的辅助函数添加到 `$WA_AGENT_WORKSPACE/agent_helpers.py`。

## 注意事项

- 本地 Chrome 控制必须启用 `chrome://inspect/#remote-debugging`。
- Chrome 可能显示"Allow remote debugging?"弹窗；等待用户点击允许。
- 地址栏弹出的不是真正的工作标签页。
- CDP 目标顺序不是 Chrome 可见标签栏的顺序。
- `BU_CDP_URL` 是 HTTP DevTools 端点；守护进程会将其解析为 WebSocket。

## 域技能

仅在 `WA_DOMAIN_SKILLS=1` 时适用。否则忽略域技能。

启用后，在自行发明方案之前，先搜索 `$WA_AGENT_WORKSPACE/domain-skills/<host>/`。`goto_url(...)` 会返回所导航主机的最多 10 个技能文件名。
