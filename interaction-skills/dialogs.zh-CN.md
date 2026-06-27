# 对话框

浏览器对话框（`alert`、`confirm`、`prompt`、`beforeunload`）会冻结 JS 线程。根据时机的不同，有两种处理方式。

## 检测

`page_info()` 会自动显示任何打开的对话框：如果有一个待处理的对话框，它会返回 `{"dialog": {"type", "message", ...}}` 而不是通常的视口字典（因为页面的 JS 已经被冻结了）。所以如果你在执行操作后调用 `page_info()` 并看到 `dialog` 键，请在做其他任何操作之前先处理它。

## 响应式：通过 CDP 关闭（推荐）

即使 JS 被冻结也能工作。可处理所有对话框类型，包括 `beforeunload`。

```python
# 关闭并读取消息
cdp("Page.handleJavaScriptDialog", accept=True)   # 接受 / 点击确定
cdp("Page.handleJavaScriptDialog", accept=False)  # 取消 / 点击取消

# 读取对话框内容（从缓冲的 CDP 事件中）
events = drain_events()
for e in events:
    if e["method"] == "Page.javascriptDialogOpening":
        print(e["params"]["type"])     # "alert", "confirm", "prompt", "beforeunload"
        print(e["params"]["message"])  # 对话框文本
```

对反机器人检测不可见——没有向页面注入 JS。

## 主动式：通过 JS 存根

防止对话框出现。适用于预期会有多个 `alert()`/`confirm()` 连续调用的情况。

```python
js("""
window.__dialogs__=[];
window.alert=m=>window.__dialogs__.push(String(m));
window.confirm=m=>{window.__dialogs__.push(String(m));return true;};
window.prompt=(m,d)=>{window.__dialogs__.push(String(m));return d||'';};
""")
# ... 执行会触发对话框的操作 ...
msgs = js("window.__dialogs__||[]")
```

权衡：
- 页面导航后存根会丢失——必须重新运行代码片段
- `confirm()` 总是返回 `true`（自动批准）
- 可被反机器人检测到（`window.alert.toString()` 会显示非原生代码）
- 不能处理 `beforeunload`

## 关于 beforeunload

当离开有未保存更改的页面（表单、编辑器、上传页面）时触发。页面会冻结，直到用户点击离开/停留。

```python
# 方案 A：导航后关闭（CDP 级别，安全）
goto_url("https://new-url.com")
try:
    cdp("Page.handleJavaScriptDialog", accept=True)  # 点击"离开"
except:
    pass  # 没有对话框 — 正常

# 方案 B：导航前阻止（JS 注入，可被检测）
js("window.onbeforeunload=null")
goto_url("https://new-url.com")
```
