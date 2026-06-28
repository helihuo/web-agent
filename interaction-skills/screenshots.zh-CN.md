# 截图

`capture_screenshot()` 会将当前视口写入一张 PNG 图片。文件使用的是**设备像素**——在 2 倍显示屏上，2296×1143 的 CSS 视口会产生 4592×2286 的 PNG。

这一点在以下两方面很重要：

1. **点击坐标是 CSS 像素。** 不要直接从图片上读取目标位置然后传给 `click_at_xy()`，必须先除以 `devicePixelRatio`。最简单的工作流是：截图后，在显示 CSS 坐标的查看器中查看，或者测量相对位置并使用 `js("window.devicePixelRatio")` 进行换算。

2. **部分大语言模型拒绝每边超过 2000 像素的图片。** 在 2 倍显示屏上的长时间会话最终会遇到这个问题。传入 `max_dim=1800` 可在图片进入对话之前进行缩小：

```python
capture_screenshot("/tmp/shot.png", max_dim=1800)
```

缩小仅在图片实际超过 `max_dim` 时才会发生，因此每次截图都开启此选项是安全的。

仅在需要查看视口下方内容时才使用全页截图（`full=True`）——它们比仅视口截图大得多且更慢。

## 何时截图 vs 何时使用 JS/DOM

截图和 JS/DOM 检查适用于不同场景，根据需要选择：

| 使用 `capture_screenshot()` | 使用 `js()` / DOM 选择器 |
|---|---|
| 不确定页面状态——需要*看到*屏幕上有什么 | 已知元素结构——只需读写数据 |
| 通过视觉外观定位按钮或链接 | 使用 `fill_input()` 或 `type_text()` 填充表单 |
| 点击或导航后验证结果 | 使用 `wait_for_load()` / `wait_for_element()` 等待加载 |
| 检测视觉变化（布局偏移、遮罩层） | 提取文本内容或属性 |
| 调试异常渲染 | 检查 `document.readyState` 或元素可见性 |

SKILL.md 中推荐的工作流是：**截图 → 解读 → 操作 → 再次截图**。当已知目标且不需要视觉确认时，使用 `js()`。

## oplog screenshot 开关

`oplog.jsonc` 中的 `screenshot` 选项（或环境变量 `WA_OPLOG_SCREENSHOT`）控制的是**已有**截图是否记录到 oplog 日志中——它**不会**触发自动截图。

- `screenshot: true` — 代码产生的截图（如 `capture_screenshot()`、`WA_DEBUG_CLICKS`）会被复制到 oplog 会话目录，路径记录到日志。
- `screenshot: false` — 这些截图仍正常产生，但路径不记录到 oplog。

### 什么会触发截图

| 触发方式 | 条件 | 如何记录 |
|---|---|---|
| AI 主动调用 `capture_screenshot()` | 始终 | 若 oplog+screenshot 启用则通过 `attach_screenshot()` 记录 |
| `click_at_xy()` 且 `WA_DEBUG_CLICKS=1` | 仅调试模式 | 自动关联到该步骤的日志记录 |
| 领域技能脚本 | 各 skill 逻辑 | 若 oplog+screenshot 启用则通过 `attach_screenshot()` 记录 |

**如果没有代码调用 `capture_screenshot()`，就不会产生截图——无论 oplog screenshot 设置如何。**
