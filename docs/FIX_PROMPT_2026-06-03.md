# 修复提示词（给 Claude Code 执行）

> **本文件是一份自包含的 prompt**，可整体复制给 Claude Code 启动一次新会话。
> 它基于 2026-06-03 Code Review 报告（`docs/CODE_REVIEW_2026-06-03.md`）编写。

---

# 【复制以下所有内容作为新 prompt 的输入】

## 角色定位

你是一名资深后端 + 前端工程师，被指派修复碳管师收资系统（tantan）的生产稳定性问题。你需要遵循工程规范、TDD 流程、git 工作流，**不允许引入新 P0**。

## 必读文件（按顺序）

1. `tantan/CLAUDE.md` — 项目根规范
2. `tantan/backend/CLAUDE.md` — 后端规范
3. `tantan/frontend/CLAUDE.md` — 前端规范
4. `tantan/backend/agents/CLAUDE.md` — Agent 模块规范
5. `tantan/docs/CODE_REVIEW_2026-06-03.md` — **2026-06-03 完整审查报告**（你本次要修的内容都在这里）
6. `tantan/docs/CODE_REVIEW_2026-06-01.md` — 上一轮审查（参考用）

## 强制工作流（按顺序执行）

### Step 1: 启动 planning-with-files

立即执行（**不要问"是否需要"**）：

```bash
# 1) 在项目根 tantan/ 下创建规划文件
# 2) 阅读 tantan/task_plan.md tantan/findings.md tantan/progress.md（如果存在）
```

如果项目根没有 `task_plan.md` / `findings.md` / `progress.md`，**先创建**这三个文件（按 planning-with-files 模板：`~/.claude/skills/planning-with-files/templates/`）。

### Step 2: 用 brainstorming skill 确认范围

启动 `superpowers:brainstorming` skill，逐项确认 06-03 报告里 TOP 10 的修复顺序和实现方式。**不要直接动手写代码**。

### Step 3: 每个 Phase 一个 git 分支

```bash
# 备份当前 working tree（如果用户没告诉你已完成备份）
git checkout -b fix/phase1-app-exception-2026-06-03
git add -A
git commit -m "WIP: snapshot before Phase 1"
```

### Step 4: TDD 流程

**先写测试，再写实现**。每个 P0 修复必须有：
- 至少 1 个回归测试（在 `backend/tests/` 或 `frontend/e2e/`）
- 至少 1 个集成测试覆盖 happy + 错误路径
- 测试必须在 CI 跑得通（不能 `test.skip` 跳过）

---

## 修复任务清单（按优先级）

### Phase 1: 止血 P0（1 周内完成）

#### P0-1. AppException 替换 52 处 HTTPException

**位置**：
- `backend/api/chat_router.py` (6 处)
- `backend/api/extract_router.py` (5 处)
- `backend/api/files_router.py` (15 处)
- `backend/api/form_router.py` (7 处)
- `backend/api/sessions_router.py` (3 处)
- `backend/api/history_router.py` (2 处)
- `backend/api/validation.py` (4 处)
- `backend/api/auth.py` (8 处)
- `backend/agents/form_filler/agent.py` (至少 1 处)

**期望**：
```python
# 之前
raise HTTPException(status_code=500, detail=f"AI响应失败: {str(e)}")

# 之后
raise AppException(
    ErrorCode.INTERNAL_ERROR,
    user_message="AI响应失败，请稍后重试",
    developer_message=str(e)  # 仅入日志
)
```

**验证**：
- `backend/tests/backend/api/test_exceptions.py` 写 AST 扫描测试，断言无 `HTTPException(..., str(` 模式
- 每个 router 至少 1 个 happy + 1 个 5xx 错误路径测试
- 启动后故意触发 5xx，前端只看到 `user_message`，看不到 `str(e)`

**不要做**：
- 不要新增 `HTTPException` 包装
- 不要把 `developer_message` 暴露到响应体
- 不要修改 `main.py:125-145` 的 handler（已正确）

---

#### P0-2. LLM/RAG/向量库 异步化（最大工作量）

**位置**：
- `backend/rag/ali_llm.py`（100% 同步 → 加 `async def achat / astream`）
- `backend/rag/retriever.py`（同步 search → async + to_thread）
- `backend/rag/knowledge_base.py`（同步 retrieve → async + to_thread）
- `backend/rag/vector_db.py`（3 个客户端 search 改 to_thread）
- `backend/agents/file_extractor.py:533`（`def process` → `async def process`）
- `backend/agents/file_processor.py:101-105`（包装真 async）
- `backend/agents/qa_agent.py`（`generate_response_stream` → `async def`）
- `backend/api/chat_router.py:97-129`（event_generator → async generator）

**期望**：
```python
# ali_llm.py
async def achat(self, messages: list) -> dict:
    return await asyncio.to_thread(self._sync_call, messages)

async def astream(self, messages: list) -> AsyncIterator[dict]:
    loop = asyncio.get_event_loop()
    for chunk in await loop.run_in_executor(None, self._stream_call, messages):
        yield chunk
```

**验证**：
- 并发 10 个聊天请求，P95 延迟 < 2s（之前是 5-10s 排队）
- SSE 真正 token-by-token，前端每 0.3s 看到新 chunk
- 启动时 `await asyncio.to_thread(...)` 不阻塞其他路由

**不要做**：
- 不要把整个 `ali_llm.py` 推倒重写（保留同步方法，加 async 包装）
- 不要换成 httpx async 客户端（dashscope SDK 同步接口稳定，`to_thread` 够用）
- 不要 Celery（06-01 报告 P1 删了，本 Phase 不接回）

---

#### P0-3. 文件下载 404 bug（1 行修复）

**位置**：`backend/api/files_router.py:68` 与 `:129`

**期望**：上传和下载的文件名前缀约定必须一致
```python
# 上传
file_path = os.path.join(upload_dir, f"{file_id}_{safe_name}{ext}")  # 改用 _ 分隔

# 或下载
if filename.startswith(file_id + "."):  # 改用 . 匹配
```

**验证**：
- 上传一个文件，记录 `file_id`
- 用 `file_id` 调用 `GET /api/files/{file_id}`，必须返回 200 + 文件内容
- 写 e2e 测试覆盖：上传 → 下载 → 字节流一致

---

#### P0-4. batch SSE 假流式 + AST 违规

**位置**：`backend/api/extract_router.py:107-115`

**期望**：
```python
# 之前（async def + yield = 异步生成器，永远不被迭代）
async def progress_callback(p, t):
    yield ServerSentEvent(event="progress", ...)

# 之后（async def → None，真正回调）
async def progress_callback(p: int, t: int, filename: str = "") -> None:
    await sse_send(ServerSentEvent(
        event="progress",
        data=json.dumps({"processed": p, "total": t, "current": filename})
    ))

# 真正传入
result = await processor.process_batch(file_list, progress_callback=progress_callback)
```

**验证**：
- 批量上传 5 个文件，前端 SSE 收 5 帧 `progress` 事件，最后一帧 `complete`
- `processed` 数字从 1 累加到 5
- 写 e2e：上传 5 文件 → 监听 SSE → 断言 5 帧 + 1 complete

---

#### P0-5. 登出清 localStorage（GDPR 修复）

**位置**：`frontend/store/authStore.ts:52-58` + `frontend/hooks/useAIChat.ts:62`

**期望**：
```typescript
// authStore.ts logout
logout: async () => {
  try {
    await authApi.logout();
  } finally {
    // 清服务端 cookie + 客户端 state + 持久化
    localStorage.removeItem('ai_conversations');
    set({ user: null, isAuthenticated: false, isLoading: false });
  }
},
```

**验证**：
- 写 Playwright 测试：用户 A 登录 → 聊 3 轮 → 登出 → 用户 B 登录 → 断言对话历史为空
- 检查 localStorage 已被清

---

#### P0-6. sectionConfig 'nested' 类型处理器

**位置**：`frontend/config/sectionConfig.ts:138, 140` + `frontend/components/FormSection.tsx:243-245`

**期望**：要么
- (A) 删 `'nested'` 类型，改回 `multi-row`
- (B) 新增 `MultiLevelTable` 子组件，结构同 `MultiRowTable`

**验证**：
- section 9 能看到 `freshWater` / `nitrogen` 两个分组
- 截图前后对比

---

#### P0-7. codegen 生成 broken TS 修复

**位置**：`backend/scripts/codegen_field_schema.py:135-169`（`gen_section_config_ts`）

**期望**：
```python
# 不要用 parts.append 拼字符串再 join
# 改用结构化生成：
fields_ts = ",\n    ".join(
    f"{{ key: '{f['key']}', label: '{f['label']}', type: '{f['type']}' }}"
    for f in field['fields']
)
```

**验证**：
- `python -m tantan.backend.scripts.codegen_field_schema --check` 后跑 `npx tsc --noEmit`
- CI 加 step: `npx tsc --noEmit -p frontend/tsconfig.json`

---

#### P0-8. Playwright fixtures 缺失修复

**位置**：`frontend/e2e/fixtures/`（目录不存在）+ `frontend/e2e/upload.spec.ts:12` + `frontend/e2e/extract.spec.ts:12`

**期望**：
- 创建 `frontend/e2e/fixtures/sample.xlsx`（最小 1KB+ 合法 xlsx，可用 `openpyxl` 脚本生成）
- 或改用 `test_doc/extractable_by_section/section3/燃料使用-模拟数据.xlsx`
- 删 `test.skip(!require('fs').existsSync(FIXTURE), ...)` —— 一旦 fixture 存在，**强制运行**

**验证**：
- CI 跑 Playwright，2 个 spec 真的跑（不是 skip）
- 断言上传 + 提取流程通过

---

#### P0-9. useFileUpload 上传文件两次（06-01 P0 复发）

**位置**：`frontend/hooks/useFileUpload.ts:53-54` + `frontend/services/api.ts:220-230`

**期望**：
- 后端 `/api/extract` 改为接收 `file_id`（已存在 `UploadResponse.file_id`）
- 前端 `fileApi.extract` 不再 append file，只传 file_id

**验证**：
- 上传 1 个文件 → 抓包 Network 标签 → 只有 1 个 `POST /api/upload` 请求
- 之前是 1 个 upload + 1 个 extract 都带 file
- 写前端单测断言 `fileApi.extract` mock 调 1 次

---

#### P0-10. useFormState 挂起等 auth check

**位置**：`frontend/app/dashboard/page.tsx:44` + `frontend/hooks/useFormState.ts:47-51`

**期望**：
```typescript
// useFormState 接收 enabled 参数
export function useFormState(autoCreateSession: boolean = true) { ... }

// dashboard 改为
const { user } = useAuthStore();
const { session, ... } = useFormState(user != null);  // auth 就绪才创建
```

**验证**：
- 写 e2e：未登录访问 /dashboard → 重定向到 /login（无 createSession 请求）
- 已登录访问 /dashboard → 1 个 createSession 请求

---

### Phase 2: 错误处理 + 规范落地（1 周）

1. pre-commit hook（`pre-commit` 框架）：ruff + eslint + mypy + `codegen --check` + `tsc --noEmit`
2. CI/CD（`.github/workflows/ci.yml`）：
   - backend: `ruff check` + `pytest tantan/backend/tests`
   - frontend: `npm ci` + `tsc --noEmit` + `playwright test`
   - codegen: `python -m tantan.backend.scripts.codegen_field_schema --check`
3. 删 14 个旧 e2e spec（带 `Authorization: Bearer` 头）+ 3 个 dev 垃圾 + section9 7 个重复 spec 保留 1 个
4. requirements.txt 全部 `==` 锁定（用 `pip-compile`）
5. testcontainers 加 PG fixture（让 CI 跑得了 33 个 API 测试）
6. `modify_agent.VALID_FIELDS` 派生自 `section_defs.py`（SSOT）
7. `qa_agent.section_guides` 去重（line 280-289 vs 485-494）
8. `useAIChat` `loadFromStorage` 从 `useState` 初始值挪到 `useEffect`
9. `useFormState` 的 `console.error` 改白名单 logger（CLAUDE.md 规范）
10. `setAuthToken` / `getAuthToken` no-op 导出删

### Phase 3: 性能与可观测（持续）

1. Token 内存 fallback 删（`auth.py:58, 100-116`）
2. 大文件流式上传（`UploadFile.read(size=N)` 累加 + 10MB 立刻 raise）
3. PBKDF2 写回升级（登录成功检测旧格式后调 `User.hash_password` 写回）
4. N+1 修复（`selectinload`）
5. Telemetry / Metrics 全面启用

### Phase 4: LLM 安全与一致性（持续）

1. pydantic schema 校验 LLM 输出
2. 提示词注入黑名单（"忽略"、"system"、"assistant"）
3. enum 白名单越界告警
4. multi-row 字段聚合逻辑（`agent.py:43-53` 的 `else` 分支）
5. codegen sub_field 不再提升到 top-level
6. form_filler SSOT 与 modify_agent VALID_FIELDS 派生

---

## 编码规范（强制）

### 必须遵守（来自 14 个 CLAUDE.md）

1. **动代码必更新 CLAUDE.md**（feedback memory 强制规则）
2. **新增/弃用模块必更新 requirements.txt**（feedback memory 强制规则）
3. **禁止 `try/except: pass` 静默吞错**（`backend/CLAUDE.md:82-99` 明确）
4. **业务异常统一用 `AppException(ErrorCode, user_message, developer_message)`**（`backend/api/CLAUDE.md:106-111`）
5. **添加字段必须同时更新 4 处**（`backend/CLAUDE.md:97-103`）：
   - `agents/form_filler/section_defs.py` 的 `section_definitions`
   - `agents/form_filler/mapping.py` 的 `BACKEND_TO_FRONTEND_FIELD_MAP`
   - 若为多行字段，还需 `agents/form_filler/transformers.py` 的 `MULTI_ROW_TRANSFORMERS`
   - 前端 `tantan/frontend/config/sectionConfig.ts` 的 `SECTION_FIELDS`
6. **提示词中不得包含硬编码选项值**（`backend/agents/CLAUDE.md:80-81`）—— 必须从 `section_options.py` f-string 注入
7. **生产环境必须显式设置 `ALLOWED_ORIGINS`**（`backend/CLAUDE.md:83-84`）

### 绝对禁止

- ❌ 把 `str(e)` 直接放进响应体（必须走 AppException 的 user_message）
- ❌ 在已有同步方法上增加 `async def` 但不 await（假异步）
- ❌ 修改 `main.py:125-145` 的 exception_handler
- ❌ 引入新依赖而不更新 requirements.txt
- ❌ 用 `test.skip` 跳过测试作为"通过"
- ❌ 删 06-01 报告里"已修"项的代码（PBKDF2 600k / HttpOnly Cookie / python-magic / slowapi / CORS fail-fast / ContextVar / form_filler 5 模块 / dashboard 4 hooks 4 组件）
- ❌ 在 commit message 里写"WIP"或"fix"（必须写 why）

---

## git 工作流

### 分支命名

```
fix/phase1-p0-1-app-exception
fix/phase1-p0-2-llm-async
fix/phase1-p0-3-download-404
...
```

### commit message 规范

```
<type>(<scope>): <subject>

<body explaining WHY>

Refs: docs/CODE_REVIEW_2026-06-03.md#P0-1
```

type 取值：`feat` / `fix` / `refactor` / `test` / `docs` / `chore`
scope 取值：`backend/api` / `backend/agents` / `frontend/hooks` / `frontend/components` / `infra`

### 每个 PR 限额

- 改动 < 200 行（不含测试和 mock 数据）
- 改动超过 500 行必须拆 PR

### 备份策略

修复开始前：
```bash
git checkout master
git pull  # 假设有 remote
git checkout -b fix/snapshot-before-2026-06-03
git add -A
git commit -m "chore: snapshot before 06-03 fix phase"
git checkout -b fix/phase1-p0-1-app-exception
```

---

## 完成标准（每个 P0 都必须达到）

### 启动验证
```bash
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m tantan.backend.main --port 8000
# 必须：① 启动无 error ② CORS fail-fast 配置正确 ③ 健康检查通过
```

### 测试验证
```bash
# 后端
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests --tb=short
# 必须：所有 test_ 跑过（无 skip 除非真的不适用）

# 前端
cd tantan/frontend
npm run lint  # 必须 0 error
npx tsc --noEmit  # 必须 0 error
npx playwright test  # 必须所有 spec 跑过（fixtures 已建）
```

### codegen 验证
```bash
python -m tantan.backend.scripts.codegen_field_schema --check
npx tsc --noEmit -p frontend/tsconfig.json
# 两者都必须 0 error
```

### CLAUDE.md 同步

修复完后，**必须**更新对应模块的 CLAUDE.md：
- 后端代码改 → 更新 `backend/CLAUDE.md` 或子模块 CLAUDE.md
- 前端代码改 → 更新 `frontend/CLAUDE.md` 或 `frontend/app/CLAUDE.md` 或 `frontend/hooks/CLAUDE.md`
- 字段映射改 → 更新 `backend/agents/CLAUDE.md` 第 80-90 行的字段映射说明
- 提示词改 → 更新 `backend/agents/CLAUDE.md` 第 60-78 行的提示词约束

### requirements.txt 同步

每次新增 / 弃用 / 升级依赖：
```bash
# 新增
echo "new-package==X.Y.Z" >> tantan/backend/requirements.txt

# 弃用
# 删除 tantan/backend/requirements.txt 中对应行
# 并在 tantan/backend/CLAUDE.md 的"启动方式"或"依赖"章节加注释
```

---

## 进度跟踪

每次修复完一个 P0，**必须**更新 `tantan/task_plan.md` 的 Phase 状态 + 在 `tantan/progress.md` 写 session log。

完成时输出以下格式的总结：

```markdown
## P0-X 修复完成

- **分支**：`fix/phase1-p0-X-xxx`
- **commit**：`abc1234`
- **改动**：
  - 新增/修改 N 个文件
  - 新增 N 个测试
  - 更新 N 个 CLAUDE.md
- **验证**：
  - 启动 ✓
  - pytest ✓ (N passed)
  - playwright ✓ (N passed)
  - codegen ✓
  - tsc ✓
- **回归测试**：
  - `backend/tests/backend/api/test_exceptions.py::test_no_http_exception_with_str_e`
  - ...
- **文档**：
  - `tantan/backend/CLAUDE.md` 更新第 N 章节
- **下一步**：P0-(X+1)
```

---

## 边界情况

### 如果用户没做 git 备份

启动前先建议：
```bash
git status  # 看是否 dirty
git checkout -b backup/before-2026-06-03-fix
git add -A
git commit -m "chore: backup before 06-03 fix"
```

### 如果项目根已有 task_plan.md / findings.md / progress.md

直接读，不要重建。**尊重已有的规划**。

### 如果发现 06-03 报告漏掉了某些问题

加到 `findings.md` 的 "06-03 报告漏掉" 章节，并在 commit message 标注 `Refs: 06-03 report gap`。

### 如果某个 P0 修复需要 > 1 天

停下来**先 commit 当前进度**为 WIP，写明卡点，然后回到用户确认是否继续。

---

## 开始执行

1. 先读 `tantan/task_plan.md` / `findings.md` / `progress.md`（如果存在）
2. 用 `superpowers:brainstorming` skill 确认 06-03 报告 TOP 10 的实现细节
3. 按 P0-1 → P0-10 顺序执行
4. 每个 P0 一个 git 分支 + commit + 完整验证
5. 每完成一个 P0 更新 task_plan.md 和 progress.md

**不要直接动手写代码**。先规划，再 TDD，再实现，再验证，再 commit。
