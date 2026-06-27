# web-agent CLI — 一次性安装前置条件

这是一个**一次性前置条件**，不属于常规 AI 工作流。只需执行一次；当 `web-agent` 打印出页面信息后，在正常浏览器工作中无需再重复安装/连接步骤。

## 安装命令

```bash
uv tool install --python 3.12 --upgrade --force web-agent
command -v web-agent   # should print a path
```

`--python 3.12` 防止 uv 选择支持旧版 Python 的旧版本。`--upgrade --force` 会用最新稳定版替换之前安装的 `web-agent` 工具，不会卸载无关命令如 `browser-use-Browser` 或 `browser-use-Terminal`。

如需开发 web-agent，请将仓库克隆到一个持久路径，并在检出目录中运行 `uv tool install -e .`。

## 注册技能

使用以下命令获取技能内容，安装/注册名为 `web-agent` 的技能：

```bash
web-agent skill
```

适用于 Codex：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/web-agent"
web-agent skill > "${CODEX_HOME:-$HOME/.codex}/skills/web-agent/SKILL.md"
```

如果旧的用户安装的 `browser` 或 `browser-use` 技能被优先选取，请手动删除该过时的技能目录。切勿编辑内置/供应商插件缓存。

## 连接浏览器

`web-agent` 附加到你已经在运行的 Chrome。快速检查：

```bash
web-agent <<'PY'
print(page_info())
PY
```

如果打印出页面信息，说明已就绪。否则，运行 `web-agent --doctor` 并按照连接提示操作。两种连接方式：

- **方式一（真实浏览器）：** 正常打开 Chrome，然后打开 `chrome://inspect/#remote-debugging` 并勾选"Allow remote debugging for this browser instance"。在 Chrome 144+ 上，首次附加时点击弹窗中的允许。继承你的登录状态/扩展 — 当代理在你日常浏览器中操作时最佳。
- **方式二（隔离配置文件，无弹窗）：** 使用 `--remote-debugging-port=9222 --user-data-dir=<非默认路径>` 启动 Chrome，然后设置 `BU_CDP_URL=http://127.0.0.1:9222`。适用于无人值守自动化。

如果快速路径在 `--doctor` 之后仍然失败，请检查 `src/web_agent/admin.py`、`src/web_agent/daemon.py` 和 `src/web_agent/_ipc.py`。

## 保持更新

当有新的 PyPI 版本时，`web-agent` 会打印更新提示横幅；在你决定升级时运行 `web-agent --update -y`。`web-agent --doctor` 也会检查最新版本。遥测是匿名的，可通过 `web-agent telemetry disable` 退出。

状态数据默认存储在 `${XDG_CONFIG_HOME:-~/.config}/web-agent` 下：认证、代理工作区、运行时套接字、日志、截图和临时文件。可通过 `WA_HOME` 或 `WEB_AGENT_HOME` 覆盖。
