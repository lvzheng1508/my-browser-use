# Browser-Use No-Screenshot + External OpenAI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a default-off screenshot pipeline switch and a unified external OpenAI configuration model so login-state pages can run stably without screenshot-related blocking.

**Architecture:** Introduce a single config contract that controls screenshot pipeline behavior and OpenAI/OpenAI-compatible provider wiring. In state extraction flow, short-circuit screenshot event emission/waiting when disabled. In model setup flow, normalize provider fields (`api_key`, `base_url`, `model`, structured-output compatibility) before constructing the runtime LLM client.

**Tech Stack:** Python 3.11+, Browser-Use event-driven watchdog architecture, Pydantic v2, pytest (tests/ci), uv, ruff, pyright.

---

## LLM-First 执行协议（给编码大模型）

本计划不是“人工任务清单”，而是给编码大模型直接执行的脚本化规范。  
执行时要求：

- 每次只执行一个 `Task`，不得并行改多个目标。
- 严格按 TDD：先写失败测试，再最小实现，再回归。
- 每个 Task 完成后，输出固定结构：
  - `changed_files`
  - `tests_added_or_updated`
  - `commands_run`
  - `result_summary`
  - `open_risks`
- 不允许偏离已锁定参数：默认禁用截图、双层开关、Agent 优先级覆盖 Browser、screenshot action 为 non-fatal no-op。

### 可复制给大模型的全局系统指令

```text
你正在 browser-use fork 分支执行增量改造。目标：
1) 默认关闭截图链路，跳过截图及相关事件等待；
2) 统一外部 OpenAI 配置（官方 + OpenAI-compatible）。

强约束：
- 严格 TDD：先失败测试 -> 最小实现 -> 回归测试；
- 不做无关重构；
- 保持向后兼容（显式开关可开启旧行为）；
- 所有改动必须可通过 tests/ci 证明。

固定决策（不可更改）：
- disable_screenshot_pipeline 在 Agent 与 Browser 都支持，默认 True；
- Agent 显式参数优先于 Browser 配置；
- screenshot action 在禁用状态下返回 non-fatal no-op（结构化提示，不抛异常）。
```

---

### Task 1: 建立失败测试（截图默认关闭语义）

**Files:**
- Modify: `tests/ci/` 下与 browser state / DOM watchdog 相关测试文件
- Test: `tests/ci/test_*screenshot*.py`（新增或并入现有测试）

**Step 1: Write the failing test**
- 编写测试：默认配置下请求 browser state 时，不应触发 screenshot event，也不应等待 screenshot result。
- 断言：DOM state 可返回，且行为不依赖 screenshot 非空。

**Step 2: Run test to verify it fails**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py::test_default_disable_screenshot_pipeline`
- Expected: FAIL（当前实现仍会进入截图路径或存在截图依赖）。

**Step 3: Write minimal implementation**
- 在配置模型中新增 `disable_screenshot_pipeline: bool = True`（默认关闭）。
- 在状态提取主路径增加短路逻辑：禁用时跳过截图事件触发和等待。
- 将 screenshot 相关结果设为可空安全处理。

**Step 4: Run test to verify it passes**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py::test_default_disable_screenshot_pipeline`
- Expected: PASS

**Step 5: Commit**
- `git add <tests and implementation files>`
- `git commit -m "feat: default disable screenshot pipeline in browser state flow"`

**Prompt Template (copy to coding model):**
```text
执行 Task 1：
1) 在 tests/ci 中新增或更新测试，验证默认配置下不触发 screenshot event 且不等待 screenshot result；
2) 先运行单测确认 FAIL；
3) 实现最小改动使其 PASS；
4) 仅输出：changed_files / tests_added_or_updated / commands_run / result_summary / open_risks。
不要执行 Task 2+。
```

---

### Task 2: 保留向后兼容（显式开启截图）

**Files:**
- Modify: screenshot watchdog / DOM state flow 对应实现文件
- Test: `tests/ci/test_*screenshot*.py`

**Step 1: Write the failing test**
- 测试显式配置 `disable_screenshot_pipeline=False` 时，系统应恢复旧行为并触发截图链路。

**Step 2: Run test to verify it fails**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py::test_enable_screenshot_pipeline_explicitly`
- Expected: FAIL（若开关未完整接入或行为未切换）。

**Step 3: Write minimal implementation**
- 完善开关分支，确保 True/False 两条路径行为稳定可预测。
- 日志中增加开关状态标识，便于运行态排障。

**Step 4: Run test to verify it passes**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py::test_enable_screenshot_pipeline_explicitly`
- Expected: PASS

**Step 5: Commit**
- `git add <tests and implementation files>`
- `git commit -m "feat: add explicit screenshot pipeline compatibility switch"`

**Prompt Template (copy to coding model):**
```text
执行 Task 2：
1) 增加/更新测试：disable_screenshot_pipeline=False 时恢复旧截图链路；
2) 先验证 FAIL，再最小实现改动，再验证 PASS；
3) 增加必要日志标识（开关状态）；
4) 仅输出：changed_files / tests_added_or_updated / commands_run / result_summary / open_risks。
```

---

### Task 3: 统一外部 OpenAI 配置模型（官方 + 兼容网关）

**Files:**
- Modify: `browser_use/llm/` 下 provider 初始化与配置解析相关文件
- Modify: `browser_use/agent/` 下 agent 初始化接收 LLM 配置入口的文件
- Test: `tests/ci/test_*llm*openai*.py`

**Step 1: Write the failing test**
- 测试 1：官方 OpenAI 配置（仅 `api_key + model`）可初始化并执行。
- 测试 2：OpenAI-compatible 配置（`api_key + base_url + model`）可初始化并执行。
- 测试 3：不支持 `json_schema` 的端点可通过统一配置禁用强制 structured output。

**Step 2: Run test to verify it fails**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py -k "openai or compatible or structured"`
- Expected: FAIL（当前配置分叉或兼容策略不统一）。

**Step 3: Write minimal implementation**
- 新增统一配置模型（Pydantic v2，`extra='forbid'`）。
- 在 LLM 装配阶段将统一模型映射到运行时客户端参数。
- 将 `dont_force_structured_output` 等兼容项纳入同一配置语义。

**Step 4: Run test to verify it passes**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py -k "openai or compatible or structured"`
- Expected: PASS

**Step 5: Commit**
- `git add <tests and implementation files>`
- `git commit -m "feat: unify openai and openai-compatible configuration"`

**Prompt Template (copy to coding model):**
```text
执行 Task 3：
1) 用统一配置模型覆盖官方 OpenAI + OpenAI-compatible；
2) 增加测试：官方配置可用、compatible 配置可用、不支持 json_schema 可降级；
3) 先 FAIL 后 PASS，采用最小实现；
4) 仅输出：changed_files / tests_added_or_updated / commands_run / result_summary / open_risks。
```

---

### Task 4: 登录态路径回归测试（人工预登录前提）

**Files:**
- Modify: `tests/ci/` 中与 profile/CDP 连接相关测试
- Modify: `examples/` 中认证/真实浏览器相关示例（仅必要最小更新）

**Step 1: Write the failing test**
- 场景：复用已有登录态（profile/CDP），在默认禁用截图下完成页面读取/基本交互。
- 断言：流程可推进，不因截图链路阻塞。

**Step 2: Run test to verify it fails**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py::test_login_state_flow_without_screenshot_pipeline`
- Expected: FAIL（若任一链路仍隐式依赖截图）。

**Step 3: Write minimal implementation**
- 修复残余截图依赖点。
- 确保错误消息对“登录态任务建议人工预登录”有清晰提示。

**Step 4: Run test to verify it passes**
- Run: `uv run pytest -vxs tests/ci/test_<new_or_updated_file>.py::test_login_state_flow_without_screenshot_pipeline`
- Expected: PASS

**Step 5: Commit**
- `git add <tests/examples/implementation files>`
- `git commit -m "test: validate login-state flows with screenshot pipeline disabled"`

**Prompt Template (copy to coding model):**
```text
执行 Task 4：
1) 增加登录态回归测试（人工预登录前提），验证默认无截图链路可推进；
2) 修复残余截图依赖；
3) 先 FAIL 后 PASS；
4) 仅输出：changed_files / tests_added_or_updated / commands_run / result_summary / open_risks。
```

---

### Task 5: 文档与全量验证

**Files:**
- Modify: `README.md`
- Modify: `docs/customize/agent/all-parameters.mdx`
- Modify: `docs/customize/browser/all-parameters.mdx`（若开关暴露在 Browser 级）
- Modify: `docs/supported-models.mdx`（如需补充兼容配置说明）

**Step 1: Write/update docs-first expectations**
- 在文档中明确：
  - 默认禁用截图链路的目的与影响；
  - 如何显式开启截图；
  - 官方 OpenAI 与兼容网关统一配置示例；
  - 登录态建议：人工预登录 + 复用 profile/CDP。

**Step 2: Run validation commands**
- `uv run ruff check --fix`
- `uv run ruff format`
- `uv run pyright`
- `uv run pytest -vxs tests/ci`

**Step 3: Verify outputs**
- Expected: lint/type/tests 全通过；无新增阻塞性回归。

**Step 4: Commit**
- `git add README.md docs/ tests/ browser_use/`
- `git commit -m "docs: document no-screenshot default and unified openai config"`

**Prompt Template (copy to coding model):**
```text
执行 Task 5：
1) 更新 README + docs 参数文档 + quickstart 兼容示例；
2) 运行 ruff/pyright/tests/ci 全量验证；
3) 仅输出：changed_files / commands_run / result_summary / remaining_gaps。
```

---

## 风险与回滚策略

- **风险 1：** 某些流程隐式依赖 screenshot 非空。  
  **缓解：** 全链路可空处理 + 回归测试覆盖。  
- **风险 2：** 兼容网关参数差异导致初始化失败。  
  **缓解：** 配置模型中增加显式兼容字段与错误提示。  
- **回滚：** 将 `disable_screenshot_pipeline` 默认值切回旧行为，并保留开关供灰度排查。

---

## 已锁定执行参数

- 开关采用双层暴露：`Agent` 与 `Browser` 均支持 `disable_screenshot_pipeline`，默认 `True`。  
- 优先级采用就近覆盖：`Agent` 显式参数优先于 `Browser` 配置。  
- CLI 同步提供该开关，并与 Python API 保持相同默认值。  
- `screenshot` action 在禁用状态下采用 non-fatal no-op：返回结构化提示，不中断任务。  
- 兼容网关示例纳入 quickstart 与参数文档，避免用户重复踩坑。

---

Plan complete and saved to `docs/plans/2026-03-05-browser-use-no-screenshot-openai-implementation-plan.md`.
