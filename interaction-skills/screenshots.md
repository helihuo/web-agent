# Screenshots

`capture_screenshot()` writes a PNG of the current viewport. The file is in **device pixels** — on a 2× display a 2296×1143 CSS viewport produces a 4592×2286 PNG.

That matters for two reasons:

1. **Click coordinates are CSS pixels.** Don't read a target off the image and pass it to `click_at_xy()` directly without dividing by `devicePixelRatio`. The simplest workflow is to take the screenshot, look at it in a viewer that shows CSS coordinates, or measure relative positions and use `js("window.devicePixelRatio")` to convert.

2. **Some LLMs reject images > 2000 px per side.** Long sessions on 2× displays will eventually hit this. Pass `max_dim=1800` to downscale the file before it gets into the conversation:

```python
capture_screenshot("/tmp/shot.png", max_dim=1800)
```

The downscale only happens when the image actually exceeds `max_dim`, so it's safe to leave on for every shot.

Use full-page screenshots (`full=True`) only when you need to see content below the fold — they are much larger and slower than viewport-only.

## When to screenshot vs. when to use JS/DOM

Screenshots and JS/DOM inspection serve different purposes. Choose based on what you need:

| Use `capture_screenshot()` | Use `js()` / DOM selectors |
|---|---|
| Unknown page state — need to *see* what's on screen | Known element structure — just need to read/write data |
| Locating a button or link by visual appearance | Filling form inputs with `fill_input()` or `type_text()` |
| Verifying the result after a click or navigation | Waiting for load with `wait_for_load()` / `wait_for_element()` |
| Detecting visual changes (layout shifts, overlays) | Extracting text content or attributes |
| Debugging unexpected rendering | Checking `document.readyState` or element visibility |

The recommended workflow from SKILL.md is: **screenshot → interpret → act → screenshot again**. Use `js()` when you already know what you're looking for and don't need visual confirmation.

## oplog screenshot switch

The `screenshot` option in `oplog.jsonc` (or `WA_OPLOG_SCREENSHOT` env var) controls whether **existing** screenshots are recorded in the oplog — it does **not** trigger automatic screenshots.

- `screenshot: true` — screenshots produced by your code (e.g. `capture_screenshot()`, `WA_DEBUG_CLICKS`) are copied into the oplog session directory and their paths are logged.
- `screenshot: false` — those screenshots are still produced normally, but their paths are not recorded in the oplog.

### What triggers screenshots

| Trigger | Condition | How it's recorded |
|---|---|---|
| AI calls `capture_screenshot()` explicitly | Always | Via `attach_screenshot()` if oplog+screenshot enabled |
| `click_at_xy()` with `WA_DEBUG_CLICKS=1` | Debug mode only | Auto-attached to the step's log entry |
| Domain skill scripts | Per-skill logic | Via `attach_screenshot()` if oplog+screenshot enabled |

**If no code calls `capture_screenshot()`, no screenshots are produced — regardless of the oplog screenshot setting.**
