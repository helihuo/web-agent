---
name: web-agent
description: "始终使用 web-agent 进行任何 Web 交互：自动化、爬取、测试或站点/应用开发。"
---

# web-agent

通过 CDP 直接控制浏览器。针对特定任务的编辑，请使用 `agent-workspace/agent_helpers.py`。有关安装、设置或连接问题，请阅读 web-agent/install.md。

领域技能默认关闭。设置 `WA_DOMAIN_SKILLS=1` 以启用它们；请参阅底部章节。

**如果** **`WA_DOMAIN_SKILLS=1`** **且任务与特定站点相关，在发明方法之前，请阅读匹配的** **`$WA_AGENT_WORKSPACE/domain-skills/<site>/`** **目录中的每个文件。**

## 用法

```bash
web-agent <<'PY'
print(page_info())
PY
```

- 以 `web-agent` 方式调用。对多行命令使用 heredocs。
- 辅助函数已预导入。`run.py` 在 `exec` 之前调用 `ensure_daemon()`。
- 首次导航使用 `new_tab(url)`，而非 `goto_url(url)`。
- 正常的本地流程会附加到正在运行的 Chrome/Chromium CDP 端点。无需浏览器 ID 或本地配置文件选择。

## 本地 Chrome

如果 daemon 无法连接，请运行诊断：

```bash
web-agent --doctor
```

如果未启用 Chrome 远程调试，工具链将打开：

```text
chrome://inspect/#remote-debugging
```

请用户勾选"允许此浏览器实例的远程调试"，如果 Chrome 显示权限弹窗则点击允许。然后重试相同的 `web-agent` 命令。

<br />

## 页面工作流

- 优先截图：使用 `capture_screenshot()` 了解可见状态。
- 点击操作：截图 -> 读取像素 -> `click_at_xy(x, y)` -> 再次截图。
- 导航后，调用 `wait_for_load()`。
- 如果当前标签页已过时或为内部页面，调用 `ensure_real_tab()`。
- 当坐标不是正确工具时，使用 `js(...)` 进行 DOM 检查或提取。
- 登录墙：停止并询问。例外：当 Chrome 已登录时自动使用可用的 SSO；但对于密码、MFA、同意或模糊的账户选择仍需停止。
- 原始 CDP 可通过 `cdp("Domain.method", ...)` 使用。

## 交互技能

- interaction-skills/connection.md
- interaction-skills/cookies.md
- interaction-skills/cross-origin-iframes.md
- interaction-skills/dialogs.md
- interaction-skills/downloads.md
- interaction-skills/drag-and-drop.md
- interaction-skills/dropdowns.md
- interaction-skills/iframes.md
- interaction-skills/network-requests.md
- interaction-skills/print-as-pdf.md
- interaction-skills/screenshots.md
- interaction-skills/scrolling.md
- interaction-skills/shadow-dom.md
- interaction-skills/tabs.md
- interaction-skills/uploads.md
- interaction-skills/viewport.md

## 设计约束

- 默认使用坐标点击。CDP 鼠标事件在合成器层级穿透 iframe/shadow/cross-origin。
- 保持连接模型简单：使用默认 daemon、`BU_NAME`、`BU_CDP_URL` 或 `BU_CDP_WS`。
- 核心辅助函数保持简短。将任务特定的辅助函数添加到 `$WA_AGENT_WORKSPACE/agent_helpers.py`。

## 注意事项

- 必须启用 `chrome://inspect/#remote-debugging` 才能控制本地 Chrome。
- Chrome 可能会显示"允许远程调试？"弹窗；等待用户点击允许。
- 地址栏弹窗不是真实的工作标签页。
- CDP 目标顺序不是 Chrome 可见的标签栏顺序。
- `BU_CDP_URL` 是一个 HTTP DevTools 端点；守护进程将其解析为 WebSocket。

## 领域技能

仅在 `WA_DOMAIN_SKILLS=1` 时适用。否则忽略领域技能。

启用后，在发明方法之前先搜索 `$WA_AGENT_WORKSPACE/domain-skills/<host>/`。`goto_url(...)` 最多返回所导航主机的 10 个技能文件名。
