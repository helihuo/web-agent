# web-agent CLI — one-time install prerequisite

This is a **one-time prerequisite**, not part of the regular AI workflow. Do it once; after `web-agent` prints page info, never repeat install/connection steps during normal browser work.

## Install the command

```bash
uv tool install --python 3.12 --upgrade --force web-agent
command -v web-agent   # should print a path
```

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `web-agent` tool install with the latest stable release. It does not uninstall unrelated commands such as `browser-use-Browser` or `browser-use-Terminal`.

For web-agent development, clone the repo into a durable path and run `uv tool install -e .` from the checkout.

## Register the skill

Install/register a skill named `web-agent` using this command for the body:

```bash
web-agent skill
```

For Codex:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/web-agent"
web-agent skill > "${CODEX_HOME:-$HOME/.codex}/skills/web-agent/SKILL.md"
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Never edit bundled/vendor plugin caches.

## Connect to a browser

`web-agent` attaches to a Chrome you already have running. Quick check:

```bash
web-agent <<'PY'
print(page_info())
PY
```

If that prints page info, you're done. If not, run `web-agent --doctor` and follow the connection cases. The two connection methods:

- **Way 1 (real browser):** open Chrome normally, then open `chrome://inspect/#remote-debugging` and tick "Allow remote debugging for this browser instance". On Chrome 144+, click Allow on the first-attach popup. Inherits your logins/extensions — best when the agent acts in your everyday browser.
- **Way 2 (isolated profile, no popups):** launch Chrome with `--remote-debugging-port=9222 --user-data-dir=<non-default path>`, then set `BU_CDP_URL=http://127.0.0.1:9222`. Best for unattended automation.

If the quick path fails after `--doctor`, inspect `src/web_agent/admin.py`, `src/web_agent/daemon.py`, and `src/web_agent/_ipc.py`.

## Keeping current

`web-agent` prints an update banner when a newer PyPI release exists; run `web-agent --update -y` when you decide to upgrade. `web-agent --doctor` also checks the latest version. Telemetry is anonymous and opt-out with `web-agent telemetry disable`.

State lives under `${XDG_CONFIG_HOME:-~/.config}/web-agent` by default: auth, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `WA_HOME` or `WEB_AGENT_HOME`.
