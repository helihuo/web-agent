# 标签页

**用 CDP 进行控制**，**用界面自动化处理用户可见的顺序**。

## 纯 CDP（跨平台：macOS / Linux / Windows）

```python
tabs = list_tabs()                    # 包括 chrome:// 页面
real_tabs = list_tabs(include_chrome=False)
tid = new_tab("https://example.com")  # 创建 + 附加
switch_tab(tid)                       # 将工具附加到标签页
cdp("Target.activateTarget", targetId=tid)  # 在 Chrome 中显示
print(current_tab())
print(page_info())
```

CDP 擅长的：
- 附加到标签页
- 打开标签页
- 激活已知目标
- 检查 URL/标题/视口
- 截取已附加标签页的截图，即使另一个标签页在前台显示

CDP 不擅长的：
- 匹配用户看到的**从左到右的标签页栏顺序**
- 不通过 URL 过滤就无法判断附加的目标是否是地址栏弹出窗口/内部页面

## 可见顺序（平台界面）

### macOS

```applescript
tell application "Google Chrome"
  set out to {}
  set i to 1
  repeat with t in every tab of front window
    set end of out to {tab_index:i, tab_title:(title of t), tab_url:(URL of t)}
    set i to i + 1
  end repeat
  return out
end tell
```

```applescript
tell application "Google Chrome"
  set active tab index of front window to 2
  activate
end tell
```

### Linux

没有 AppleScript。但同样的分工仍然适用：
- 使用 CDP 进行 `new_tab`、附加、检查、激活已知目标
- 当用户指的是可见顺序时，使用窗口管理器/浏览器界面自动化

常用工具：
- `xdotool`
- `wmctrl`
- 桌面环境脚本（`gdbus`、KWin、GNOME Shell 扩展等）

## 实践中验证有效的规则

- 如果用户期望 Chrome 界面发生可见变化，仅 `switch_tab()` 是**不够的**。
- `Target.activateTarget` 是 CDP 端的"显示此标签页"。
- `list_tabs()` 默认包含 `chrome://newtab/`；当只需要真实页面时，请使用 `include_chrome=False`。
- `chrome://omnibox-popup.top-chrome/` 可能作为虚假页面目标出现；在面向用户的标签页列表中应忽略它。
- 如果页面的 `w=0 h=0`，你可能附加到了错误的目标或非窗口表面。
- 对于动态界面，在打开下拉菜单/模态框后，应重新读取元素矩形再进行坐标点击。
