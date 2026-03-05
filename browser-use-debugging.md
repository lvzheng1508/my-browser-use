# browser-use 登录态网页访问调试记录

## 背景目标

使用 `browser-use` 访问需要登录态的内网页面（58corp docs），由 LLM 自动读取页面内容并做内容总结。

---

## 已完成的工作

### 1. 创建 `browser-use-operator` Skill

路径：`~/.claude/skills/browser-use-operator/scripts/run_browser_use.py`

封装了 browser-use SDK 的调用，支持以下关键参数：

| 参数 | 作用 |
|---|---|
| `--cdp-auto` | 脚本自动用 `--remote-debugging-port=9222` 启动 Chrome，使用 Skill 自管 profile |
| `--cdp-url` | 连接已开启调试端口的 Chrome，复用其登录态 |
| `--no-vision` | 禁止把截图发给 LLM（非多模态模型必须加） |
| `--flash-mode` | 启用 browser-use 轻量模式 |
| `--dont-force-structured-output` | 关闭 JSON Schema 强制结构化输出（兼容不支持 `json_schema` 的模型） |
| `--user-data-dir` | 指定浏览器 profile 目录 |

### 2. 排查并修复的问题

#### 问题 A：Chrome 调试端口限制（新版本安全策略）
- Chrome 108+ 禁止对**默认 profile** 开启远程调试，必须指定非默认的 `--user-data-dir`
- 解决：Skill 使用自管 profile 目录 `~/.claude/skills/browser-use-operator/.browser-user-data`

#### 问题 B：GLM-4.7 不支持视觉输入，报错 1210
- browser-use 默认把截图以 base64 图片形式发给 LLM
- GLM-4.7 不是多模态模型，拒绝图片参数
- 解决：加 `--no-vision` 参数

#### 问题 C：GLM-4.7 JSON 输出被 markdown 包裹
- GLM-4.7 输出 JSON 时会包裹 ` ```json...``` `，browser-use 直接解析报 `Invalid JSON`
- 解决：在脚本中加入 `MarkdownStrippingChatOpenAI` 子类，自动剥去代码块包装

#### 问题 D：`window_width`/`window_height` 在 browser-use 0.12.1 中失效
- 旧 API，0.12.1 改为 `window_size={"width": ..., "height": ...}`
- 解决：已在脚本中更新

#### 问题 E：DeepSeek 不支持 `response_format=json_schema`
- browser-use 默认发 `json_schema` 类型的 `response_format`，DeepSeek 返回 `invalid_request_error`
- 解决：加 `--dont-force-structured-output`，透传 `dont_force_structured_output=True` 给 `ChatOpenAI`

---

## 当前核心阻塞问题

### 问题 F：`ScreenshotWatchdog` 阻塞 DOM 提取（未解决）

这是目前最根本的卡点。

**现象：**
```
DOMWatchdog.on_BrowserStateRequestEvent → ScreenshotEvent → cdp.Page.captureScreenshot → 15s 超时
→ DOMWatchdog 拿不到页面状态 → LLM 每步都看到空页面 → Agent 无法推进
```

**根本原因：**

browser-use 0.12.1 的 DOM 提取流水线里，`DOMWatchdog` 在每次读取 DOM 状态时，会**同步等待**一个后台截图操作（`_capture_clean_screenshot`）。即使设置了 `use_vision=False`，截图仍然会被触发——`use_vision=False` 只是不把截图**发给 LLM**，截图行为本身无法通过公开参数关闭。

在 docs.58corp.com 这类复杂 SPA 页面上，`Page.captureScreenshot` 始终挂起超时。

**已尝试的规避方式：**
- `use_vision=False` ❌ 截图仍触发
- `flash_mode=True` ❌ 仍会触发 ScreenshotWatchdog
- CDP 模式（外部 Chrome） ❌ 截图 hang 更严重
- Playwright 自管浏览器（Playwright 139 + Chrome 145 profile）❌ profile 版本不兼容，启动超时 30s
- Playwright 自管浏览器（新建空 profile）❌ 启动仍超时（可能是 sandbox 网络限制）

---

## 后续解决方案

### 方案一：直接 Monkey-patch ScreenshotWatchdog（推荐，最快）

在 `HELPER_CODE` 中，在 `Agent` 初始化之前，直接 patch 掉截图 watchdog 的事件处理，让它立刻返回空结果而不阻塞：

```python
from browser_use.browser.watchdogs import screenshot_watchdog

_original_handler = screenshot_watchdog.ScreenshotWatchdog.on_ScreenshotEvent.__wrapped__

async def _noop_screenshot(self, event):
    # Skip actual screenshot; return None so DOMWatchdog proceeds without blocking
    return None

screenshot_watchdog.ScreenshotWatchdog.on_ScreenshotEvent = _noop_screenshot
```

风险：如果 browser-use 检查截图结果非空才继续，需要同时把 `raise_if_none=True` 改为 `False`。

### 方案二：降级 browser-use 到 0.11.x

0.12.x 引入了 `bubus` 事件总线架构（`BrowserStartEvent`、`ScreenshotEvent` 等），截图逻辑从 Playwright 直调改为通过事件总线异步触发，导致超时问题。  
0.11.x 直接调 Playwright API，截图失败不会阻塞 DOM 读取。

```bash
pip install browser-use==0.11.4
```

需要验证 0.11.x 的 `BrowserProfile`/`BrowserSession` API 是否相同。

### 方案三：修复 Playwright Chromium 启动超时

当前 Playwright 39 启动超时（30s）原因待确认：
- 可能是 sandbox 网络限制导致 Playwright 无法初始化
- 可能是 `launch_persistent_context` 在拷贝 profile 时耗时过长
- 排查方法：在真实终端（不通过 Cursor）直接跑 `playwright install chromium` 确认安装，再测试裸起 Chromium

### 方案四：绕过 browser-use agent，直接组合 Playwright + LLM（降级方案）

对于"读取页面内容 → LLM 总结"这类**不需要多步交互**的任务，可以跳过 browser-use agent 循环：

1. Playwright 连接/启动 Chrome（已有登录态）
2. 导航到目标 URL，`page.evaluate()` 提取文本
3. 直接调 LLM API（DeepSeek/GLM）做总结

代码已在 `/tmp/fetch_and_summarize.py` 有原型。

对于**需要多步交互**的任务（点击、填表、翻页），仍需走 browser-use agent，此时方案一/二是必须的。

---

## 环境信息

| 项目 | 版本 |
|---|---|
| browser-use | 0.12.1 |
| Playwright Chromium | 139.0.7258.5（刚安装） |
| System Chrome | 145.0.7632.117 |
| Python | 3.12（/opt/anaconda3） |
| 测试模型 | GLM-4.7（不可用）、deepseek-chat（JSON schema 问题已修复）|

## Skill 文件位置

```
~/.claude/skills/browser-use-operator/
├── SKILL.md                  # Skill 说明文档
└── scripts/
    └── run_browser_use.py    # 主脚本（已包含所有修复）
```
