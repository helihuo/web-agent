web-agent is a thin layer that connects agents to browsers via an editable CDP harness.

# Code priorities
- Clarity
- Precision
- Low verbosity
- Versatility

# Overview
Core code lives in `src/web_agent/`:
- `admin.py` — daemon lifecycle, diagnostics, updates, profile management
- `daemon.py` — the long-lived middleman process between the browser and the agent
- `helpers.py` — CDP wrapper and core browser primitives auto-imported into `-c` scripts
- `run.py` — the `web-agent` CLI

`SKILL.md` tells agents how to use the harness and CLI.
`install.md` tells agents how to install it, attach a browser, and troubleshoot.

An agent operating the harness only edits inside `agent-workspace/`:
- `agent_helpers.py` — task-specific browser helpers the agent adds
- `domain-skills/` — skills the agent writes and reads

## Internal modules
- `_ipc.py` — IPC communication layer, handles inter-process communication between the daemon and helpers
- `auth.py` — Browser Use cloud authentication, manages API keys and login state
- `cdp_client.py` — CDP WebSocket client, wraps the Chrome DevTools Protocol connection
- `paths.py` — Path and directory management, provides utilities for config directories, runtime directories, etc.
- `telemetry.py` — Anonymous telemetry, collects usage statistics (can be disabled)

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug.
