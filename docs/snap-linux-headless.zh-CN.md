# Snap Chromium 与 web-agent（Linux）

## 为什么 Snap 浏览器会导致 CDP 连接失败

Ubuntu 和其他几个发行版将 Chromium 作为 [Snap](https://snapcraft.io/) 包分发。Snap 会在受限环境中运行应用程序。Chrome 的远程调试端点必须绑定在主机网络上，`web-agent` 守护进程才能访问它。Snap 的沙盒和文件系统布局通常会阻止其像正常的 `.deb` Chrome 安装那样工作，因此即使 Chromium 看起来在运行，测试框架也可能找不到可用的 DevTools 端口。

症状：`web-agent --doctor` 显示 Chrome 正在运行，但守护进程始终无法连接，或者 CDP 握手失败且没有明显原因。[Issue #191](https://github.com/helihuo/web-agent/issues/191) 讨论了此类配置问题。

## 原生安装 Google Chrome（以 Ubuntu 为例）

使用 Google 官方软件包（AMD64），而非 Snap：

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

ARM 或其他架构：从 [Google Chrome for Linux](https://www.google.com/chrome/linux/) 下载对应的软件包。

## 将测试框架指向原生二进制文件

将非 Snap 的二进制文件放在解析"哪个 Chrome"的**最前面**，避免误选 `PATH` 上的 Snap 包装器。

- **`WA_CHROME_PATH`** — 本项目文档和 `web-agent --doctor` Snap 探测中的首选变量名。
- **`CHROME_PATH`** — 为兼容其他工具而同样支持的环境变量。

在 `~/.bashrc` 或你的环境配置中添加示例：

```bash
export WA_CHROME_PATH=/usr/bin/google-chrome-stable
```

然后使用该路径启动 Chrome 进行方式 2（`--remote-debugging-port=…`），或使用方式 1 配合原生安装打开的配置文件。连接详情见 [`install.md`](../install.md)。

## 验证

```bash
web-agent --doctor
```

如果在 Linux 上检测到的仍然是 Snap 二进制文件，doctor 会打印 `[snap-detect]` 警告。获取简要修复清单：

```bash
web-agent doctor --fix-snap
```
