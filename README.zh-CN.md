<br />

# Web Agent 

🌐 [English](./README.md) | **中文** 

通过一个轻量、可编辑的 CDP 工具，将 LLM 直接连接到你的真实浏览器。适用于需要**完全自由**的浏览器任务。

一个连接到 Chrome 的 websocket，中间没有任何阻隔。代理在执行过程中会编写缺失的内容。工具在每次运行时都会自我改进。

将安装提示粘贴到你的编程代理中。

```
  ● agent: 想要上传文件
  │
  ● agent-workspace/agent_helpers.py → 缺少辅助函数
  │
  ● agent 编写它                         agent_helpers.py
  │                                                       + 自定义辅助函数
  ✓ 文件已上传
```

**你将再也不用使用浏览器了。**

## 安装提示

粘贴到 Claude Code 或 Codex 中：

```text
Install or upgrade web-agent to the latest stable version with uv using Python 3.12, register the skill from `web-agent skill`, and connect it to my browser. Follow web-agent/install.md if setup or connection fails.
```

代理将打开 `chrome://inspect/#remote-debugging`。勾选复选框以便代理可以连接到你的浏览器：

<img src="docs/setup-remote-debugging.png" alt="Remote debugging setup" width="520" style="border-radius: 12px;" />

当每次附加的弹窗出现时，点击允许（Chrome 144+）：

<img src="docs/allow-remote-debugging.png" alt="Allow remote debugging popup" width="520" style="border-radius: 12px;" />

查看 [agent-workspace/domain-skills/](agent-workspace/domain-skills/) 获取示例任务。

<br />

## 架构（4 个核心文件约 1000 行代码）

- `install.md` — 首次安装和浏览器引导
- `SKILL.md` — 日常使用
- `src/web_agent/` — 受保护的核心包
- `${XDG_CONFIG_HOME:-~/.config}/web-agent/agent-workspace/agent_helpers.py` — 代理编辑的辅助代码
- `${XDG_CONFIG_HOME:-~/.config}/web-agent/agent-workspace/domain-skills/` — 代理编辑的可复用站点特定技能

普通的 `web-agent` 辅助调用会附加到正在运行的 Chrome/Chromium CDP 端点。对于隔离的自动化，你可以使用 `--remote-debugging-port` 启动 Chrome 并传递 `BU_CDP_URL`，或使用 Browser Use 云浏览器。

## 开发

从代码库中，使用 `./web-agent` 运行当前工作树，而无需激活虚拟环境或依赖全局安装的命令：

```bash
./web-agent <<'PY'
print(page_info())
PY
```

面向代理的普通文档应该继续使用 `web-agent`；`./web-agent` 启动器仅用于本地仓库测试。

## 贡献

欢迎 PR 和改进。最好的帮助方式：**为 agent-workspace/domain-skills/ 贡献一个新的领域技能**，针对你经常使用的站点或任务（LinkedIn 推广、在 Amazon 上订购、报销费用等）。每个技能都教会代理选择器、流程和边缘情况，否则它必须重新发现这些内容。

- **技能由工具编写，而不是由你编写。** 只需使用代理运行你的任务——当它发现一些非显而易见的内容时，它会自行归档技能（参见 [SKILL.md](SKILL.md)）。请不要手动编写技能文件；代理生成的文件反映了浏览器中实际工作的内容。
- 打开一个 PR，将生成的 `domain-skills/<site>/` 文件夹复制到此仓库的 `agent-workspace/domain-skills/` 示例中——小而专注非常好。
- 同样欢迎错误修复、文档调整和辅助改进。
- 浏览现有技能（`github/`、`linkedin/`、`amazon/`、...）以了解其形状。

如果你不确定从哪里开始，请打开一个问题，我们会为你指出有用的方向。

## 领域技能

设置 `WA_DOMAIN_SKILLS=1` 以启用来自代理工作区的领域技能。此仓库的 [agent-workspace/domain-skills/](agent-workspace/domain-skills/) 目录包含通过 PR 贡献的示例。

***

