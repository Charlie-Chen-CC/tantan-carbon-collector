# 碳管师收资系统 · 第二次系统性 Code Review 报告

**审查时间**：2026-06-03
**对照基准**：2026-06-01 报告 `docs/CODE_REVIEW_2026-06-01.md`
**审查范围**：重构后的 FastAPI + Next.js 14 全栈
**审查方式**：4 路并行深度审查（后端架构 / 前端架构 / 安全异步 / 测试规范），交叉验证
**审查 token 成本**：~371k tokens（4 个 Agent 累计）
**结论一句话**：从 **3-4/10 → 5.5/10**，重构扎实但 3 条 P0 完全未修 + 引入 4 个新 Critical 回归

---

## 一、项目整体评价

| 维度 | 06-01 评分 | 06-03 评分 | 变化 | 关键证据 |
|------|-----------|-----------|------|----------|
| 功能完整度 | 7 | 8 | ↑1 | 9 模块端到端跑通，5 个新 e2e spec |
| 架构合理性 | 3 | 6 | ↑3 | routes 拆 10 文件 / form_filler 拆 5 模块 / dashboard 拆 4 hooks + 4 组件 |
| 代码质量 | 3 | 5.5 | ↑2.5 | 死代码清 1300 行 / 174 个 pytest 函数（+254%）/ RAG 去 LangChain |
| 安全性 | 2 | 6.5 | ↑4.5 | PBKDF2 600k / HttpOnly Cookie / python-magic / slowapi / CORS fail-fast / 速率限制 |
| 性能 | 4 | 4 | 0 | 同步 LLM 阻塞没修 → 仍是 0 |
| 可测试性 | 2 | 5 | ↑3 | 174 个 test 函数 / 5 个新 e2e spec / 7 个 RAG 质量测试 |
| 可维护性 | 3 | 5.5 | ↑2.5 | 1300 行死代码清 / 14 个 CLAUDE.md 更新 / 编码规范明文化 |
| 文档规范性 | 8 | 8 | 0 | 14 个 CLAUDE.md 体系完整，但**执行率仅 75%**（16 条抽 12 条做，4 条完全没做） |

**重构成果**（71% 修复率）：
- ✅ **安全三件套全做实**：PBKDF2 600k / HttpOnly+Secure+SameSite Cookie / python-magic 真实 MIME 探测
- ✅ **拆分到位**：api/ 10 个文件 / form_filler 5 个子模块 / 4 个前端组件 / 4 个 hooks
- ✅ **状态收敛**：state/ 只剩 database_manager.py / 1300 行死代码清完
- ✅ **RAG 重写**：去 LangChain 4 文件 / PGVector 直连 / 真实流式
- ✅ **测试骨架**：174 test_ 函数 / 33 API 集成测试 / 10 e2e / 7 RAG 质量

**重构没修的 P0**（17% 完全未修）：
- ❌ 同步 LLM 阻塞 event loop（`ali_llm.py` 100% 同步，0 个 async/await）
- ❌ AppException 错误处理统一（52 处 HTTPException 0 处 AppException，**3 Agent 独立发现**）
- ❌ `str(e)` 泄露 11+ 处（**3 Agent 独立发现**）

**重构引入的新 Bug**（4 个 Critical）：
- ❌ 文件下载 404（上传 `{file_id}.xlsx` 但下载找 `{file_id}_*`，前缀约定不一致）
- ❌ batch SSE 假流式 + AST 违规（`async def + yield` 混用）
- ❌ codegen 生成的 `sectionConfig.ts` 是非法 TS 语法
- ❌ `'nested'` 类型在 FormSection 无处理器，section 9 两个字段永不显示

**核心矛盾**：**拆得对、改得对、但两条 P0 规范（错误处理 + 异步化）从 0 执行**。CLAUDE.md 写了 16 条规范，只做了 12 条（75%），剩 4 条全部是"统一错误处理"和"异步化"——而这两条恰恰是最影响生产稳定性的。

---

## 二、06-01 vs 06-03 修复进度表（17 项）

| # | 06-01 报告项 | 06-03 状态 | 证据 |
|---|-------------|-----------|------|
| S1 | 文件上传 octet-stream 全放行 | ✅ 修复 | `api/validation.py` 新建，python-magic 真实 MIME 探测 |
| S2 | Token localStorage + console.log | ✅ 修复 | `auth.py:217-219` HttpOnly+Secure+SameSite；`authStore.ts` 改 zustand |
| S3 | 无速率限制 | ✅ 修复 | `utils/ratelimit.py`(130 行) + slowapi 启动接入 |
| S4 | PBKDF2 100k | ✅ 修复 | `database.py:19` 600k + 向后兼容 100k |
| S5 | 默认明文凭证 | ✅ 修复 | `main.py:220` REQUIRE_NON_DEFAULT_CREDENTIALS |
| S6 | Cookie `secure=False` 默认 | ⚠️ 半修 | `auth.py:218` 走 config，但生产环境无强校验 |
| 2.1 | 状态管理器 3 套并存 | ✅ 修复 | `state/` 只剩 `database_manager.py`(332 行) |
| 2.1 | OrchestratorAgent 死代码 | ✅ 修复 | 文件已删 |
| 2.2 | routes.py 838 行 | ✅ 修复 | 拆为 10 个文件，聚合器 routes.py 仅 22 行 |
| 2.3 | dashboard 772 行 God Component | ✅ 修复 | 198 行，拆出 4 个组件 + 4 个 hooks |
| 2.4 | RAG 双重包装 | ✅ 修复 | `langchain_llm.py` / `langchain_vectorstore.py` 删 |
| 2.5 | RAG PGVectorStore 包名错配 | ✅ 修复 | `vector_db.py` 用 `PGVectorClient` 直连 |
| 3.5 | /api/chat/stream 假流式 | ✅ 修复 | `chat_router.py:77-155` 用 `StreamingResponse` + `qa_agent.generate_response_stream` |
| 3.6 | TraceContext threading.local 串号 | ✅ 修复 | `utils/logger.py:37` 改 `ContextVar` |
| **3.3** | **同步 LLM 阻塞 event loop** | ❌ 未修 | `ali_llm.py` 100% 同步（**2 Agent 独立发现**）|
| **3.12** | **AppException 错误处理** | ❌ 未修 | 52 处 `HTTPException` 0 处 `AppException`（**3 Agent 独立发现**）|
| **3.12** | **错误体 str(e) 泄露** | ❌ 未修 | 12+ 处仍 `str(e)`（**3 Agent 独立发现**）|
| 3.7 | 字段映射 SSOT | ⚠️ 半修 | SSOT + codegen 跑通，但 codegen 输出 broken TS |
| 6.1 | form_filler.py 1032 行 | ✅ 修复 | 拆为 5 个子模块，最大 301 行 |
| Celery | 死代码 | ✅ 修复 | 目录只剩 CLAUDE.md |

**修复率：12/17 真正修复（71%），2/17 部分修复（12%），3/17 完全未修（17%）**

---

## 三、架构问题（结构性缺陷）

### 3.1 【Critical】AppException 错误处理统一体系完全没有落地
- **位置**：`backend/api/{chat,extract,files,sessions,history,form,validation}_router.py` + `auth.py` 共 **52 处** `raise HTTPException(...)`，**0 处** 用 `AppException`
- **现状**：`main.py:125-145` 装了完美的 `@app.exception_handler(AppException)` + 兜底 `@app.exception_handler(Exception)`；`utils/exceptions.py` 写了 `ErrorCode` 枚举 + `AppException` 类；`backend/api/CLAUDE.md:106` 明确写"旧散乱 `return {"error": str(e)}` / `HTTPException(400, str(e))` 已废弃"
- **风险**：
  1. 错误响应体形如 `{"detail": "AI响应失败: <str(e)>"}` 直接把内部异常原文（含 SQL/路径/堆栈）吐给前端
  2. i18n / 错误码路由无法做
  3. `developer_message` 分离设计完全失效
- **建议**：写个半自动脚本扫所有 router，机械替换 `raise HTTPException(status_code=X, detail=f"...{str(e)}")` → `raise AppException(ErrorCode.X, "user_msg", developer_message=str(e))`，加 pre-commit grep 守门

### 3.2 【Critical】LLM / RAG / 向量库 100% 同步阻塞 event loop（06-01 P0 完全没修）
- **位置**：
  - `backend/rag/ali_llm.py` 100% 同步（`def _call` / `def _sync_call` / `def _stream_call` / `def generate` / `def chat`），0 个 `async def` / `await` / `ainvoke` / `asyncio`
  - `backend/rag/retriever.py:67` 调同步 `vectorstore.similarity_search_with_score`
  - `backend/rag/knowledge_base.py` 同步 `retrieve`
  - `backend/rag/vector_db.py:621` 同步 pymilvus/qdrant/psycopg2 客户端
  - `backend/agents/file_extractor.py:533` `def process` 同步
- **风险**：
  1. 生产 10 个并发聊天 = 排队 5-10s
  2. SSE"真实流式"实际只是 dashscope 拉 chunk 时 event loop 仍被锁
  3. 部署 nginx/多 worker 也不能解决（每个 worker 都被锁）
- **建议**：
  1. `ali_llm.py` 加 `async def achat / astream` 走 `asyncio.to_thread(Generation.call, ...)` 或 httpx async 客户端
  2. `retriever.py` / `knowledge_base.py` 改 `async def`
  3. `vector_db` 三个客户端的 `search` 改 `to_thread`
  4. `qa_agent` 入口 `async def generate_response_async`，`chat/stream` 端点改 `await`

### 3.3 【Critical】/api/extract/.../batch SSE 是假流式 + 含 AST 违规
- **位置**：`backend/api/extract_router.py:107-115`
- **现象**：
  ```python
  processed = 0
  async def progress_callback(p, t):                  # async def + yield 混用 = 异步生成器
      yield ServerSentEvent(event="progress", ...)    # 从未 await / 迭代
  result = await processor.process_batch(file_list)   # progress_callback 永远不传
  ```
- **AST 验证**：`async def progress_callback` 内含 `yield`，实际是 async generator；从未被 `await` 或迭代
- **风险**：
  1. 前端 SSE 永远只看到 `started → complete` 两帧，"批量进度条"功能不工作
  2. `processed = 0` 是个死变量
  3. `total` 在 line 113 闭包中可见，但 `progress_callback` 永远不执行
- **建议**：
  1. `progress_callback` 改 `async def progress_callback(p, t) -> None: yield ...` 不能是 — 改成发 SSE 帧的真正 async callback
  2. `await processor.process_batch(file_list, progress_callback=progress_callback)` 真正传入
  3. 在 `_extract_file` 内 `for chunk in self.extractor.process_stream(...)` 持续 yield progress

### 3.4 【Critical】文件下载永远 404（重构引入的回归）
- **位置**：`backend/api/files_router.py:68` 与 `:129`
- **现象**：
  ```python
  # 上传 (line 67-68)：保存为 {file_id}.xlsx
  file_path = os.path.join(upload_dir, f"{file_id}{ext}")

  # 下载 (line 128-130)：找 {file_id}_*.xlsx
  for filename in os.listdir(upload_dir):
      if filename.startswith(file_id + "_"):
  ```
- **风险**：上传和下载对文件名前缀约定不一致，**下载端点 100% 失败**，前端要拉回文件时永远收 404
- **建议**：上传路径用 `f"{file_id}_{safe_name}{ext}"`，或下载端 `startswith(file_id)`

### 3.5 【High】路由函数声明 `async def` 但内部 0 个 `await` —— 假异步
- **位置**：`backend/api/{chat_router,form_router,sessions_router,history_router,auth.py}`
- **统计**：
  ```
  chat_router.py       async def=3   await=0
  form_router.py       async def=4   await=0
  sessions_router.py   async def=3   await=0
  history_router.py    async def=1   await=0
  auth.py              async def=7   await=0
  ```
- **现象**：`async def login(...)` → `db.query(...)` → `commit()` → 全是同步阻塞 SQL + Redis 调用。FastAPI 在任何"await 屈服点"之前都是同步执行
- **建议**：要么改 `def login(...)`，要么 SQL 调 `await asyncio.to_thread(...)` + Redis 换 `redis.asyncio`

### 3.6 【High】Token 内存降级 fallback 仍存在（06-01 报告说已删，实际还在）
- **位置**：`backend/api/auth.py:58, 100-116, 128-143`
- **现象**：
  ```python
  _token_store: dict = {}    # 模块级内存 dict
  def create_token(...):
      if is_redis_available():
          try: redis.setex(...)
          except redis.RedisError as e:
              logger.warning(f"...降级到内存存储")
      _token_store[token] = token_data               # 仍然写入
  ```
- **风险**：dev 模式下 Redis 一抖动，全员 token 写入内存；`uvicorn --reload` 一重启，全部 401 登出
- **建议**：删 `_token_store` fallback；Redis 失败直接 `raise AppException(ErrorCode.INTERNAL_ERROR, "认证服务暂不可用")`

---

## 四、高风险问题（重构引入 + 残留）

### 4.1 【Critical】'nested' 字段类型在 FormSection 无处理器，section 9 两个字段永不显示
- **位置**：`config/sectionConfig.ts:138, 140` + `components/FormSection.tsx:243-245`
- **现象**：`freshWater` 和 `nitrogen` 在 section 9 是 `type: 'nested'`，但 FormSection 的 switch 没有 `'nested'` 分支，默认返回 `null`。用户在 section 9 看不到这两个分组
- **风险**：直接回归——codegen 生成 schema 时 type 多了一个，UI 端未跟进
- **建议**：要么删 `'nested'` 类型，要么补 `MultiLevelTable` 子组件（结构同 `MultiRowTable`）

### 4.2 【Critical】useFormState(true) 在 auth check 完成前触发 createSession
- **位置**：`app/dashboard/page.tsx:44` + `hooks/useFormState.ts:47-51`
- **现象**：`useFormState(true)` 总是立刻挂载，`useEffect` 立即 `createSession()`。`providers.tsx` 的 `initAuthEffects` 也在同一帧 `checkAuth()`，两条请求赛跑
- **风险**：① 401 噪声；② 时序脆弱——后端若放行 `/api/session` 未认证调用，会产生孤儿 session
- **建议**：`useFormState` 接收 `enabled: boolean`，dashboard 传 `user != null` 才创建；或在 `useAuthStore` 的 `isAuthenticated` 变 true 时再触发

### 4.3 【Critical】登出后 AI 对话历史仍留在 localStorage（用户间泄露）
- **位置**：`hooks/useAIChat.ts:62` + `store/authStore.ts:52-58`
- **现象**：`useAIChat` 的 `useEffect` 每次 `conversations` 变化都 `localStorage.setItem('ai_conversations', ...)`。`authStore.logout()` 只调 `authApi.logout()`（清服务端 cookie）+ setState，**从未清 localStorage**
- **风险**：① 06-01 P0 第 5 条没修；② 隐私合规问题（GDPR / 个保法）；③ 不同用户的对话串味
- **建议**：在 `authStore.logout` 加 `localStorage.removeItem('ai_conversations')`，或在 `useAIChat` 监听 `user?.user_id` 变化、按用户 ID 隔离 key（`ai_conversations_${userId}`）

### 4.4 【Critical】codegen 生成的 sectionConfig.ts 是无效 TypeScript
- **位置**：`backend/scripts/codegen_field_schema.py:135-169`（`gen_section_config_ts`）
- **现象**：生成的多行字段产物形如 `fields: [,     { key: 'fuelType', ... },,     { key: 'amount', ... },,   ]` —— `[,{...},,{...},,]` 是非法 TS。Section 9 的 `nested` 类型**完全不生成 fields 子项**
- **风险**：
  1. `FormSection.tsx` 收到 `type: 'multi-row'` 的 `fields: [,,{...},,]` 会在 `fields.map(...)` 阶段抛 `undefined is not a function`
  2. `codegen --check` 只校验"生成文件与 SSOT 一致"，**没校验 TS 语法**，所以错误藏得深
- **建议**：
  1. 修 `gen_section_config_ts`：将 `parts.append` 列表拆出，单独用 `'\n'.join` 写 fields 块
  2. 加 `nested` 分支：`if f.get("nested")` 走嵌套 children 渲染逻辑
  3. CI 加 `npx tsc --noEmit -p frontend/tsconfig.json` 作为 codegen --check 的后续步骤

### 4.5 【Critical】Playwright fixtures 目录不存在，关键 e2e 等于 disabled
- **位置**：`frontend/e2e/upload.spec.ts:16` + `frontend/e2e/extract.spec.ts:16`
- **现象**：
  - `test.skip(!require('fs').existsSync(FIXTURE), ...)`
  - `frontend/e2e/fixtures/` 目录**完全不存在**
  - CI 跑这两个 spec 时 `test.skip` 直接跳过，**2 个 e2e 用例报告通过但实际 0 覆盖**
- **建议**：
  1. 立即创建 `frontend/e2e/fixtures/sample.xlsx`（最小可上传 .xlsx）
  2. 或者改用 `test_doc/extractable_by_section/section3/燃料使用-模拟数据.xlsx` 作为 fixture

### 4.6 【High】useFileUpload.uploadAndExtract 同一文件上传两次（06-01 P0 复发）
- **位置**：`hooks/useFileUpload.ts:53-54` + `services/api.ts:220-230`
- **现象**：`await fileApi.upload(sessionId, section, file)` 再 `await fileApi.extract(sessionId, section, file)`。`fileApi.extract` 把 `file` append 到 FormData 又发一遍
- **建议**：`/api/extract` 改成接收 `file_id`，前端只调 `fileApi.extract(fileId, section, sessionId)`，不再传 file

### 4.7 【High】FormSection 类型契约不匹配 + `case 'file'` / `onFileUpload` 死代码
- **位置**：`components/FormSection.tsx:175, 223-236, 240` + `app/dashboard/page.tsx:155`
- **现象**：
  1. `onFileUpload: (file: File) => void` 但父组件传的是 `fillFormFromExtracted: (data: Record<string, any>) => void`——类型撒谎
  2. `sectionConfig.ts` 全文 0 个 `type: 'file'` 字段，`case 'file'` 永远走不到
- **建议**：`onFileUpload` 删掉（FileUploadPanel 已经做了），`case 'file'` 分支一起删

### 4.8 【High】条件字段 `conditionField` 在 schema 中 0 存在，对应代码全死
- **位置**：`components/FormSection.tsx:185-194` + `config/sectionConfig.ts`（grep `conditionField` 0 命中）
- **现象**：CLAUDE.md 明确说 section 1 的 `reportingPeriod` 应在 `isCalendarYear = '否'` 时显示，但 `sectionConfig.ts:38-39` 两个字段都没标 `conditionField`
- **建议**：在 `BACKEND_TO_FRONTEND_FIELD_MAP` codegen 阶段为 section 1 的 `reportingPeriod` 加 `conditionField: 'isCalendarYear', conditionValue: '否'`

### 4.9 【High】codegen 25+ 重复 dict key
- **位置**：`backend/agents/form_filler/mapping.py:49-73`（Section 3 部分）
- **现象**：Section 3 有 11 个 multi-row 字段，每个都带子字段 `燃料类型/使用量/单位`。codegen 把 11×3=33 个 sub_field 都提升成 top-level dict key。`{"燃料类型": "fuelType", ...}` 被写 11 次
- **建议**：codegen 不再把 sub_field 提升到 top-level（sub_field 应该在 nested lookup）

### 4.10 【High】FormFillAgent multi-row 字段散落 bug（06-01 报告 3.7 直接继承）
- **位置**：`backend/agents/form_filler/agent.py:43-53` + `backend/rag/ali_llm.py` 同步 LLM
- **现象**：`else` 分支用 `MAP.get(backend_field, backend_field)` 把每个键直接平铺到 `mapped_data`。LLM 返回平展 dict 时，子字段全部孤立在 mapped_data 顶层
- **建议**：`_transform_multi_row` 改成"先按 `is_array=True` 的 field 名 list 聚合子字段"；加 e2e 测试断言 `mapped_data["boilerFuel"][0]["fuelType"] == ...`

### 4.11 【High】BatchFileProcessor 包装"假 async"
- **位置**：`backend/agents/file_processor.py:101-105` + `backend/agents/file_extractor.py:533`
- **现象**：`for f in group_files: result = await self._extract_file(f)` "await" 但内部是 sync LLM
- **建议**：`file_extractor.process` 改 `async def process`，LLM 调 `await asyncio.to_thread(self.llm_client.chat, ...)`

---

## 五、性能问题

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| P1 | `backend/rag/ali_llm.py` | 100% 同步阻塞（详见 3.2） | 改 `async def` + `to_thread` |
| P2 | `backend/api/extract_router.py:107-113` | batch SSE progress_callback 死代码（详见 3.3） | 修实现 |
| P3 | `backend/state/database_manager.py:78-89, 304-329` | `get_session` / `_session_to_dict` 用 `db_session.section_data` lazy relationship，每次访问都触发 SQL（**N+1 隐式**） | 改 `selectinload(Session.section_data)` |
| P4 | `backend/rag/retriever.py:62-76` | `vectorstore.similarity_search_with_score` 同步调 knowledge_base.retrieve | 改 async + to_thread |
| P5 | `hooks/useFormState.ts:82-83` | `confirmSection` 后立即 `reloadSession()` 拉全 session（N+1 风险） | 后端 confirm 响应里直接返回更新后的 `progress` |
| P6 | `hooks/useAuth` wrapper 7 个独立 selector | 组件任意字段变化都重渲染（zustand 官方 anti-pattern） | 改 `useShallow` |
| P7 | `utils/__init__.py` | 一次性 import 4 个 utils 文件 → 任何 `from tantan.backend.utils import X` 都会加载 `prometheus_client` / `opentelemetry` / `slowapi` 探针 | 改成延迟 import |

**性能瓶颈总账**：6 个新性能问题，其中 3 个是同步阻塞（P1 / P4 / P11），P2 是死代码伪装，P3 是隐性 N+1。

---

## 六、安全问题

| # | 等级 | 位置 | 问题 | 修复 |
|---|------|------|------|------|
| S1 | Critical | `backend/api/{chat,extract,files,sessions,history,form}_router.py` | 52 处 HTTPException 0 处 AppException，错误体泄露内部信息（详见 3.1） | 详见 3.1 |
| S2 | Critical | `hooks/useAIChat.ts:62 + authStore.ts:52` | 登出后 AI 对话留 localStorage（详见 4.3） | 详见 4.3 |
| S3 | Critical | `backend/rag/ali_llm.py` | 100% 同步阻塞（影响所有安全审计场景） | 详见 3.2 |
| S4 | High | `backend/agents/file_extractor.py:413-444` | LLMExtractor 对 LLM 输出**无 schema 校验**，提示词注入风险 | 用 pydantic 模型按 `section_definitions` 校验 |
| S5 | High | `backend/api/files_router.py:60-62` | 上传大文件全读进内存（1GB × 16 并发 OOM） | 用 `starlette.datastructures.UploadFile.read(size=N)` 流式读取 |
| S6 | High | `backend/api/files_router.py:164` | Content-Disposition 头用未引号包裹的 basename（header injection 风险） | 用 `urllib.parse.quote(filename, safe='')` 编码 |
| S7 | High | `backend/models/database.py:60-84` | PBKDF2 旧 100k 用户**永远不会被升级**（验证通过后只更新 last_login_at，不重写 hash） | 登录成功检测旧格式后调 `User.hash_password(body.password)` 写回 |
| S8 | High | `backend/api/auth.py:121, 136` | `verify_token` 的 `logger.info` 打印 token 前 20 字符 | 去掉 `token[:20]` 日志 |
| S9 | High | `backend/config/settings.py:49` + `backend/main.py` | `COOKIE_SECURE` 默认 false + 启动期无强校验 | `if ENVIRONMENT == "production" and not COOKIE_SECURE: raise RuntimeError(...)` |
| S10 | Medium | `backend/api/extract_router.py:107-115` | batch SSE 把 `str(e)` 推到 EventSource data 里持续泄露 | 同 S1 |
| S11 | Medium | `services/api.ts:30-31` | `X-Request-ID` 前端生成覆盖后端 `X-Trace-ID`，链路追踪混乱（06-01 P12 未修） | 统一字段名 + 删前端生成 |

**安全态势对比 06-01**：
- ✅ 已修：6 项（HttpOnly Cookie / python-magic / slowapi / CORS fail-fast / 默认凭证检查 / 速率限制）
- ❌ 未修：3 项（同步 LLM 阻塞 / AppException / str(e) 泄露）—— **3 Agent 独立发现**
- 🆕 新增：5 项（AI 对话留 localStorage / LLM 输出无 schema 校验 / 大文件 OOM / Content-Disposition 注入 / PBKDF2 写回升级缺失 / token 写日志）

---

## 七、可维护性问题

### 7.1 规范执行率打分（CLAUDE.md 16 条抽 12 条做 4 条完全没做 = 75%）

| CLAUDE.md 条款 | 执行率 | 证据 |
|----------------|--------|------|
| PBKDF2 600k | 100% | `database.py:19` |
| HttpOnly Cookie | 100% | `auth.py:213-219` |
| python-magic 真实 MIME | 100% | `validation.py:79` |
| ContextVar 替代 threading.local | 100% | `logger.py:37` |
| CORS 生产 fail-fast | 100% | `main.py:163-184` |
| State 统一 DatabaseStateManager | 100% | 7 个 router 全部用 |
| routes.py 22 行聚合器 | 100% | - |
| form_filler 拆 5 模块 | 100% | - |
| RAG 去 LangChain | 100% | 4 文件 |
| 死代码清理 1300 行 | 100% | - |
| `/api/chat/stream` 真实流式 | 100% | - |
| **同步 LLM 阻塞 event loop** | **0%** | 0 处修复（C2） |
| **AppException 统一异常** | **5%** | handler 挂着但 0 处 raise（C4） |
| **错误体不泄露内部信息** | **0%** | 11+ 处仍 `str(e)` |
| **提示词反硬编码** | 80% | Section 1/2/3/5 走 section_options 注入；Section 4 漏 |
| 字段映射 SSOT | 30% | SSOT + codegen 跑通 + 测试有；但 codegen 输出 broken TS |
| 错误处理统一用 AppException | 5% | 规范写进 CLAUDE.md 但代码 0 处用 |
| 添加字段同时更新 X/Y/Z | 85% | SSOT 化 + codegen 自动同步 4 个文件；缺 e2e 防 drift |
| 测试覆盖补齐 | 70% | 174 个 test_ 函数（CLAUDE.md 报告 184），前端 18 spec（2 个永久 skip） |
| 依赖锁定 | 50% | requirements.lock.txt 已生成但 requirements.txt 仍 12 处 >= |
| 加 CI/CD | 0% | 无 .github/workflows/，无 pre-commit hook |

**总体执行率：约 75%** — 头部"安全/去 LangChain/拆分/死代码"全做，但**统一错误处理 + 异步化两条 P0 规范完全没落地**。

### 7.2 其他可维护性问题

- **7.2.1【High】** 前端根目录 3 个 dev 垃圾未清（`test-section3-debug.js` / `debug-dashboard.png` / `section3-ai-extract-result.png`）
- **7.2.2【High】** section9 有 7 个重复 spec 文件（`ai-check` / `ai-extract` / `api-test` / `final-test` / `scroll-check` / `simple-test` / `verify-saved`）
- **7.2.3【High】** 14 个旧 e2e spec 仍带 `Authorization: Bearer` 头，已被 cookie 取代
- **7.2.4【High】** `e2e/dashboard.spec.ts` 选 `.ant-menu-item`（不存在，新版用 `<Sider>`）+"AI助手"文案（已改"碳排放助手"）
- **7.2.5【High】** 无 CI/CD（`.github/` 不存在）
- **7.2.6【High】** requirements.txt 仍有 12 处 `>=` 而非 `==`
- **7.2.7【High】** TestClient 跑 API 测试需真 PG，CI 跑不起来（应加 testcontainers / GH Actions postgres service）
- **7.2.8【Medium】** `modify_agent.py:145-206` `VALID_FIELDS` 硬编码 100+ 字段名，与 `form_filler/section_defs.py` 漂移
- **7.2.9【Medium】** `qa_agent.py:280-289` 与 `:485-494` `section_guides` 字典**复制了两遍**
- **7.2.10【Medium】** `agents/__init__.py:411-444` 重导出符号表与 `form_filler/__init__.py` 有 7+ 个重叠
- **7.2.11【Medium】** `useAIChat` `loadFromStorage` 在 `useState` 初始化调用，违反 hooks/CLAUDE.md:97 "持久化副作用放在 useEffect"
- **7.2.12【Medium】** `useFormState` 内 4 处 `console.error('[useFormState] ...', err)` 把 err 全量打印（CLAUDE.md 明确禁止）
- **7.2.13【Medium】** 14 个旧 e2e spec + 22 个其他 .test.ts 仍带 `Authorization: Bearer` 头
- **7.2.14【Medium】** `e2e/dashboard.spec.ts` 是重构前的旧 spec，选择器已失效
- **7.2.15【Low】** `useFormState.confirmSection` 已 message.error，dashboard 的 try/catch 永远到不了（接口不一致）
- **7.2.16【Low】** `setAuthToken` / `getAuthToken` no-op 导出可删
- **7.2.17【Low】** `api.ts` `(error as any).appErrorCode` / `appUserMessage` 无人读取
- **7.2.18【Low】** `FormSidebar.onToggleCollapse` prop 声明但不消费
- **7.2.19【Low】** 注释文化弱：routers 几乎全无 docstring
- **7.2.20【Low】** `agents/file_extractor.py:35-57` 9 个 `extractors` 字典在 `extract_from_bytes` 内**每次调用都重建**

---

## 八、最优先修复 TOP 10

按"严重度 × 修复 ROI"排序，**总计 ~5 人天可消除所有 Critical/High**：

| 优先级 | 问题 | 修复耗时 | 跨 Agent 验证 | 风险 |
|--------|------|----------|--------------|------|
| **P0** | 3.1 AppException 替换 52 处 HTTPException | 0.5 天 | 3 Agent | 错误体泄露 / i18n 失效 |
| **P0** | 3.4 文件下载 404 修复（1 行） | 0.1 天 | 1 Agent | 重构引入回归 |
| **P0** | 3.3 batch SSE 假流式 + AST 违规 | 0.5 天 | 1 Agent | 进度条功能失效 + AST 违规 |
| **P0** | 3.2 LLM/RAG/向量库 异步化 | 1.5 天 | 2 Agent | 生产并发必崩 |
| **P0** | 4.3 登出清 localStorage（1 行） | 0.1 天 | 1 Agent | GDPR 违规 / 用户间泄露 |
| **P0** | 4.1 sectionConfig 'nested' 类型处理器 | 0.5 天 | 1 Agent | section 9 两个字段不显示 |
| **P0** | 4.4 codegen 生成 broken TS 修复 | 0.5 天 | 1 Agent | SSOT 整个工作流崩 |
| **P0** | 4.5 Playwright fixtures 缺失 | 0.2 天 | 1 Agent | 2 个核心 e2e 永久 skip |
| **P1** | 4.6 上传文件两次（改 file_id 路径） | 0.5 天 | 1 Agent | 06-01 P0 复发 |
| **P1** | 4.2 useFormState 挂起等 auth check | 0.3 天 | 1 Agent | 401 噪声 + 时序赛跑 |

**总修复量**：约 4.7 人天（**1 个工程师 1 周可搞定 P0**）。

---

## 九、建议重构路线

### Phase 1：止血 P0（1 周）
1. **3.1** AppException 替换 52 处 HTTPException
2. **3.2** LLM/RAG/向量库 异步化
3. **3.3** batch SSE 修实现
4. **3.4** 文件下载 404 修复
5. **4.1** sectionConfig 'nested' 类型处理器
6. **4.3** 登出清 localStorage
7. **4.4** codegen 生成 broken TS 修复
8. **4.5** Playwright fixtures 创建
9. **4.6** 上传文件两次修
10. **4.2** useFormState 挂起等 auth check

### Phase 2：错误处理 + 规范落地（1 周）
1. pre-commit hook（ruff + eslint + mypy + codegen --check + tsc --noEmit）
2. CI/CD（GH Actions：lint → test → build）
3. 删 14 个旧 e2e spec + 3 个 dev 垃圾 + section9 7 个重复 spec 保留 1 个
4. requirements.txt 全部 `==` 锁定
5. testcontainers 加 PG fixture
6. `modify_agent.VALID_FIELDS` 派生自 `section_defs.py`
7. `qa_agent.section_guides` 去重
8. 重导出符号表统一入口
9. `useAIChat` loadFromStorage 改 useEffect
10. `useFormState` console.error 改白名单 logger

### Phase 3：性能与可观测（持续）
1. 全量 LLM/DB/Vector 调用 async 化（与 3.2 一起做）
2. Token 内存 fallback 删（3.6）
3. N+1 修复（P3 / P5）
4. 大文件流式上传（S5）
5. PBKDF2 写回升级（S7）
6. Telemetry / Metrics 全面启用

### Phase 4：LLM 安全与一致性（持续）
1. pydantic schema 校验 LLM 输出（S4）
2. 提示词注入黑名单
3. enum 白名单越界告警
4. multi-row 字段聚合逻辑（H10）
5. Codegen sub_field 不再提升到 top-level（H9）
6. form_filler SSOT 与 modify_agent VALID_FIELDS 派生

### Phase 5：前端细节打磨（持续）
1. 路由守卫 middleware
2. useShallow 替代 useAuth wrapper
3. 条件字段 conditionField 补齐
4. FloatingAI 提到 zustand store
5. dashboard 错误态 UI

---

## 十、写在最后

**重构方向对、做了一半**。06-01 报告的"安全 + 拆分 + 状态收敛"三大类（约 70% 工作量）做实了，**工程底座明显比 06-01 报告时更稳**。但 06-01 报告里"统一错误处理 + 异步化"两条 P0 规范**从 0 执行**——14 个 CLAUDE.md 写了 16 条规范，只做了 12 条（75%），剩 4 条全部是"AppException 统一"和"异步化"，而这两条恰恰是**最影响生产稳定性的**。

更糟的是，**重构过程还引入了 4 个新 Critical Bug**（文件下载 404 / batch SSE 假流式 / codegen broken TS / 'nested' 字段无处理器），说明"拆"和"改"的过程中**没做回归测试**。e2e 测不到这些，因为 fixtures 缺失导致 2 个核心 e2e 永久 skip，CI 给的是**假绿灯**。

**关键 1 周工作量 = P0 全部清零**。修起来不难，难的是承认"重构做得不完整"。

如果只做一件事：**让 AppException 0 处使用 + LLM 异步化**——这两条是 3 Agent 独立交叉验证的最关键 P0，是当前 100% 阻塞生产稳定性的根因。
