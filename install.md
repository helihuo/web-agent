---
name: browser-install
description: Install web-agent and connect it to a browser fast.
---

# web-agent install

Use once. For browser work, read `SKILL.md`.

## Fast Path

```bash
uv tool install --python 3.12 --upgrade --force web-agent
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/web-agent"
web-agent skill > "${CODEX_HOME:-$HOME/.codex}/skills/web-agent/SKILL.md"
web-agent <<'PY'
print(page_info())
PY
```

If `page_info()` prints, stop. Setup is done.

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `web-agent` tool install with the latest stable release. It does not uninstall unrelated commands such as `browser-use-Browser` or `browser-use-Terminal`.

For Claude Code or other agents: install `web-agent`, register a skill named `web-agent`, use `web-agent skill` as the body, and use this trigger:

```text
Always use web-agent for any web interaction: automation, scraping, testing, or site/app work.
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Do not edit bundled/vendor plugin caches.

## If Chrome Blocks It

In Chrome:

1. Open `chrome://inspect/#remote-debugging`.
2. Tick "Allow remote debugging for this browser instance".
3. Click Allow on the popup if it appears.
4. Retry `page_info()`.

The checkbox and popup require the user.

## Cloud Browsers

Cloud is optional. Local Chrome does not need a Browser Use API key.

Use any short made-up name; `r7k2` below is just a placeholder.

```bash
web-agent auth login
web-agent <<'PY'
start_remote_daemon("r7k2")
PY
```

Then use it by name:

```bash
BU_NAME=r7k2 web-agent <<'PY'
print(page_info())
PY
```

## If Still Broken

```bash
web-agent --doctor
```

Use the output:

- `chrome running` FAIL: ask the user to open Chrome, or use isolated/cloud browser.
- `daemon alive` FAIL: Chrome remote debugging permission is missing, Chrome is closed, or the CDP endpoint is not reachable.
- update available: run `web-agent --update -y` when you decide to upgrade.

If this still fails, inspect `src/web_agent/admin.py`, `src/web_agent/daemon.py`, and `src/web_agent/_ipc.py`.

Useful:

```bash
web-agent --update -y
web-agent telemetry disable
```

State lives under `${XDG_CONFIG_HOME:-~/.config}/web-agent` by default: auth, telemetry id, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `WA_HOME` or `WEB_AGENT_HOME`.
