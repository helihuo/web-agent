<br />

# Web Agent 

🌐 **English** | [中文](./README.zh-CN.md) 

Connect an LLM directly to your real browser with a thin, editable CDP harness. For browser tasks where you need **complete freedom**.

One websocket to Chrome, nothing between. The agent writes what's missing during execution. The harness improves itself every run.

Paste the setup prompt into your coding agent.

```
  ● agent: wants to upload a file
  │
  ● agent-workspace/agent_helpers.py → helper missing
  │
  ● agent writes it                         agent_helpers.py
  │                                                       + custom helper
  ✓ file uploaded
```

**You will never use the browser again.**

## Setup prompt

Paste into Claude Code or Codex:

```text
Install or upgrade web-agent to the latest stable version with uv using Python 3.12, register the skill from `web-agent skill`, and connect it to my browser. Follow https://github.com/helihuo/web-agent/blob/main/install.md if setup or connection fails.
```

The agent will open `chrome://inspect/#remote-debugging`. Tick the checkbox so the agent can connect to your browser:

<img src="docs/setup-remote-debugging.png" alt="Remote debugging setup" width="520" style="border-radius: 12px;" />

Click Allow when the per-attach popup appears (Chrome 144+):

<img src="docs/allow-remote-debugging.png" alt="Allow remote debugging popup" width="520" style="border-radius: 12px;" />

See [agent-workspace/domain-skills/](agent-workspace/domain-skills/) for example tasks.

<br />

## Architecture (\~1k lines across 4 core files)

- `install.md` — first-time install and browser bootstrap
- `SKILL.md` — day-to-day usage
- `src/web_agent/` — protected core package
- `${XDG_CONFIG_HOME:-~/.config}/web-agent/agent-workspace/agent_helpers.py` — helper code the agent edits
- `${XDG_CONFIG_HOME:-~/.config}/web-agent/agent-workspace/domain-skills/` — reusable site-specific skills the agent edits

Plain `web-agent` helper calls attach to the running Chrome/Chromium CDP endpoint. For isolated automation, launch Chrome yourself with `--remote-debugging-port` and pass `BU_CDP_URL`, or use a Browser Use cloud browser.

## Development

From a checkout, use `./web-agent` to run the current working tree without activating a virtualenv or depending on the globally installed command:

```bash
./web-agent <<'PY'
print(page_info())
PY
```

Normal agent-facing docs should keep using `web-agent`; the `./web-agent` launcher is only for local repo testing.

## Contributing

PRs and improvements welcome. The best way to help: **contribute a new domain skill** under [agent-workspace/domain-skills/](agent-workspace/domain-skills/) for a site or task you use often (LinkedIn outreach, ordering on Amazon, filing expenses, etc.). Each skill teaches the agent the selectors, flows, and edge cases it would otherwise have to rediscover.

- **Skills are written by the harness, not by you.** Just run your task with the agent — when it figures something non-obvious out, it files the skill itself (see [SKILL.md](SKILL.md)). Please don't hand-author skill files; agent-generated ones reflect what actually works in the browser.
- Open a PR with the generated `domain-skills/<site>/` folder copied into this repo's `agent-workspace/domain-skills/` examples — small and focused is great.
- Bug fixes, docs tweaks, and helper improvements are equally welcome.
- Browse existing skills (`github/`, `linkedin/`, `amazon/`, ...) to see the shape.

If you're not sure where to start, open an issue and we'll point you somewhere useful.

## Domain skills

Set `WA_DOMAIN_SKILLS=1` to enable domain skills from the agent workspace. This repo's [agent-workspace/domain-skills/](agent-workspace/domain-skills/) directory contains examples to contribute via PR.

***

