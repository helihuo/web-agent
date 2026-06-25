# Snap Chromium and web-agent (Linux)

## Why Snap browsers break CDP

Ubuntu and several other distributions ship Chromium as a [Snap](https://snapcraft.io/) package. Snap runs apps in a confined environment. Chrome’s remote debugging endpoint must bind on the host network where the `web-agent` daemon can reach it. Snap’s sandbox and filesystem layout commonly prevent that from working the way a normal `.deb` Chrome install does, so the harness may see no usable DevTools port even when Chromium appears to run.

Symptoms: `web-agent --doctor` shows Chrome running, but the daemon never attaches, or CDP handshake fails without an obvious cause. [Issue #191](https://github.com/helihuo/web-agent/issues/191) discusses this class of setup problem.

## Install Google Chrome natively (Ubuntu example)

Use Google’s official package (AMD64), not the Snap:

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

ARM or other architectures: download the matching package from [Google Chrome for Linux](https://www.google.com/chrome/linux/).

## Point the harness at the native binary

Put the non-Snap binary **first** in how you resolve “which Chrome,” so a Snap wrapper on `PATH` is not chosen by mistake.

- **`WA_CHROME_PATH`** — preferred name in this project’s docs and `web-agent --doctor` snap probe.
- **`CHROME_PATH`** — honored the same way for compatibility with other tooling.

Example for `~/.bashrc` or your environment:

```bash
export WA_CHROME_PATH=/usr/bin/google-chrome-stable
```

Then start Chrome from that path for Way 2 (`--remote-debugging-port=…`), or use Way 1 with a profile opened from the native install. Connection details are in [`install.md`](../install.md).

## Verify

```bash
web-agent --doctor
```

If a Snap binary is still the one detected on Linux, doctor prints a `[snap-detect]` warning. For a concise fix checklist:

```bash
web-agent doctor --fix-snap
```
