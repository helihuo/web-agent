---
name: browser-install
description: 快速安装 web-agent 并连接到浏览器。
---

# web-agent 安装

使用一次。对于浏览器工作，请阅读 `SKILL.md`。

## 快速路径

```bash
uv tool install --python 3.12 --upgrade --force web-agent
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/web-agent"
web-agent skill > "${CODEX_HOME:-$HOME/.codex}/skills/web-agent/SKILL.md"
web-agent <<'PY'
print(page_info())
PY
```

如果 `page_info()` 打印成功，停止。设置已完成。

`--python 3.12` 防止 uv 选择支持旧 Python 版本的旧版本。`--upgrade --force` 将任何先前的 `web-agent` 工具安装替换为最新的稳定版本。它不会卸载不相关的命令，例如 `browser-use-Browser` 或 `browser-use-Terminal`。

对于 Claude Code 或其他代理：安装 `web-agent`，注册一个名为 `web-agent` 的技能，使用 `web-agent skill` 作为主体，并使用此触发器：

```text
始终使用 web-agent 进行任何 Web 交互：自动化、抓取、测试或网站/应用工作。
```

如果选择了旧的用户安装的 `browser` 或 `browser-use` 技能，请手动删除该过时的技能目录。不要编辑捆绑/供应商插件缓存。

## 如果 Chrome 阻止

在 Chrome 中：

1. 打开 `chrome://inspect/#remote-debugging`。
2. 勾选"允许此浏览器实例的远程调试"。
3. 如果出现弹出窗口，点击允许。
4. 重试 `page_info()`。

复选框和弹出窗口需要用户操作。

## 云浏览器

云是可选的。本地 Chrome 不需要 Browser Use API 密钥。

使用任何简短的虚构名称；下面的 `r7k2` 只是一个占位符。

```bash
web-agent auth login
web-agent <<'PY'
start_remote_daemon("r7k2")
PY
```

然后通过名称使用它：

```bash
BU_NAME=r7k2 web-agent <<'PY'
print(page_info())
PY
```

## 如果仍然有问题

```bash
web-agent --doctor
```

使用输出：

- `chrome running` 失败：要求用户打开 Chrome，或使用隔离/云浏览器。
- `daemon alive` 失败：缺少 Chrome 远程调试权限，Chrome 已关闭，或 CDP 端点不可达。
- 有可用更新：当您决定升级时运行 `web-agent --update -y`。

如果仍然失败，检查 `src/web_agent/admin.py`、`src/web_agent/daemon.py` 和 `src/web_agent/_ipc.py`。

有用的：

```bash
web-agent --update -y
web-agent telemetry disable
```

状态默认位于 `${XDG_CONFIG_HOME:-~/.config}/web-agent` 下：认证、遥测 ID、代理工作区、运行时套接字、日志、截图和临时文件。使用 `WA_HOME` 或 `WEB_AGENT_HOME` 覆盖。
