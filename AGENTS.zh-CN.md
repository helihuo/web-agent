web-agent 是一个轻量层，通过可编辑的 CDP 工具将 agent 连接到浏览器。

# 代码优先级
- 清晰性
- 精确性
- 低冗余度
- 通用性

# 概述
核心代码位于 `src/web_agent/`：
- `admin.py` — daemon 生命周期、诊断、更新、配置文件管理
- `daemon.py` — 浏览器与 agent 之间长期运行的中间进程
- `helpers.py` — CDP 封装和核心浏览器原语，自动导入到 `-c` 脚本中
- `run.py` — `web-agent` CLI

`SKILL.md` 告诉 agent 如何使用该工具和 CLI。
`install.md` 告诉 agent 如何安装它、附加浏览器以及故障排除。

操作该工具的 agent 仅在 `agent-workspace/` 内编辑：
- `agent_helpers.py` — agent 添加的特定任务浏览器辅助函数
- `domain-skills/` — agent 编写和读取的技能

# 贡献
考虑真正需要什么。优先选择修复 bug 的最小差异。
