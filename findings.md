# Findings & Decisions — 2026-06-03 Code Review

<!--
  本文件汇总 4 路并行 Agent 审查的关键发现。
  完整报告（含每条问题的位置/原因/风险/建议/推荐实现）：docs/CODE_REVIEW_2026-06-03.md
  上次（06-01）报告：docs/CODE_REVIEW_2026-06-01.md
  本次 session 规划：task_plan.md
  本次 session 日志：progress.md
-->

## Requirements

用户原始请求："已经全部修改了，再次审查一遍代码"

## 审查方法

- 4 路并行 Agent 深度审查（后台）：
  - Agent 1：安全 + 异步并发（27 条问题，86k tokens）
  - Agent 2：前端架构（24 条问题，74k tokens）
  - Agent 3：测试 + 工程规范（25 条问题，93k tokens）
  - Agent 4：后端架构（24 条问题，118k tokens）
- 累计 100+ 条原始问题，去重后约 60+ 条
- 关键 P0 多 Agent 交叉验证

## 4 路 Agent 关键发现

### Agent 1：安全 + 异步并发（27 条）
- A1-A3 Critical：ali_llm.py 100% 同步阻塞 / chat_stream 假流式 / extract 同步阻塞
- A6 Medium：batch SSE progress_callback 是 async generator 不是 callable
- B1 Critical：AppException 0 处 raise（与 Agent 4 交叉）
- B2 High：12 处 str(e) 泄露（与 Agent 4 交叉）
- C1 High：PBKDF2 旧 100k 写回升级未实现
- C2 High：COOKIE_SECURE 默认 false，无强校验
- D1 High：Content-Disposition header 无引号
- D4 High：上传大文件全读进内存（1GB × 16 并发 OOM）
- E1 High：LLM 输出无 schema 校验（提示词注入）

### Agent 2：前端架构（24 条）
- B-1 Critical：sectionConfig 'nested' 类型在 FormSection 无处理器（section 9 freshWater/nitrogen 永不显示）
- B-2 Critical：useFormState(true) 在 auth check 前触发 createSession
- B-4 Critical：登出后 AI 对话历史留 localStorage（06-01 P0 完全未修）
- B-3 High：useFileUpload 上传文件两次（06-01 P0 复发）
- B-5 High：useAuth wrapper 7 个独立 selector，组件任意字段变化都重渲染
- B-6 High：FloatingAI 关闭后 hook 状态销毁
- B-7 High：FormSection 类型契约不匹配 + case 'file' 死代码
- B-8 High：条件字段 conditionField 0 存在（业务规则失效）
- B-12 Medium：X-Request-ID 前端生成覆盖后端（06-01 P12 未修）
- B-13/14/15 Medium：14 旧 e2e spec / fixtures 缺失

### Agent 3：测试 + 工程规范（25 条）
- C1 Critical：codegen 生成的 sectionConfig.ts 是无效 TS（[,,{...},,] 数组含空逗号 + nested 不生成子项）
- C2 Critical：AppException 0 处使用（与 Agent 1、4 交叉）
- C3 Critical：Playwright fixtures 缺失，2 个核心 e2e 永久 skip
- H1 High：前端根目录 3 个 dev 垃圾未清（test-section3-debug.js / debug-dashboard.png / section3-ai-extract-result.png）
- H2 High：section9 有 7 个重复 spec 文件
- H3 High：e2e/dashboard.spec.ts 硬编码 "AI助手"（已改"碳排放助手"），5 个用例死测试
- H4 High：11 处 str(e) 泄露（与 Agent 1 交叉）
- H5 High：无 CI/CD
- H6 High：requirements.txt 12 处 >= 而非 ==
- H7 High：API 测试需 PG，CI 跑不起来

### Agent 4：后端架构（24 条）
- C1 Critical：文件下载永远 404（上传 {file_id}.xlsx 但下载找 {file_id}_*，前缀约定不一致）
- C2 Critical：LLM/RAG/向量库 100% 同步阻塞（与 Agent 1 交叉）
- C3 Critical：/api/extract/.../batch SSE 假流式 + AST 违规（async def + yield 混用）
- C4 Critical：8 个 router 共 52 处 raise HTTPException，0 处 AppException（与 Agent 1、3 交叉）
- H1 High：路由函数声明 async def 但 0 await（假异步）
- H2 High：FormFillAgent multi-row 字段散落 bug（06-01 报告 3.7 直接继承）
- H3 High：Token 内存降级 fallback 仍存在（06-01 报告说已删，实际还在）
- H4 High：BatchFileProcessor 包装"假 async"
- H5 High：codegen 25+ 重复 dict key
- H6 High：Section 4 提示词选项未走 section_options.py 注入

## 多 Agent 交叉验证的最关键 P0

| 问题 | 点到的 Agent | 严重度 |
|------|-------------|--------|
| **AppException 0 处使用** | Agent #1 + #3 + #4 | Critical（3 重验证） |
| **`str(e)` 泄露 11+ 处** | Agent #1 + #3 + #4 | Critical（3 重验证） |
| **同步 LLM 阻塞 event loop** | Agent #1 + #4 | Critical（2 重验证） |
| **AI 对话历史留 localStorage** | Agent #2（独立） | Critical |
| **06-01 P0 重复上传** | Agent #2（独立） | High |
| **fixtures 缺失导致 e2e 永久 skip** | Agent #3（独立） | High |

## 06-01 报告里 17 项的修复状态

| # | 06-01 报告项 | 06-03 状态 | 证据 |
|---|-------------|-----------|------|
| S1 | 文件上传 octet-stream 全放行 | ✅ 修复 | api/validation.py 新建，python-magic 真实 MIME 探测 |
| S2 | Token localStorage + console.log | ✅ 修复 | auth.py:217-219 HttpOnly+Secure+SameSite；authStore.ts 改 zustand |
| S3 | 无速率限制 | ✅ 修复 | utils/ratelimit.py(130 行) + slowapi 启动接入 |
| S4 | PBKDF2 100k | ✅ 修复 | database.py:19 600k + 向后兼容 100k |
| S5 | 默认明文凭证 | ✅ 修复 | main.py:220 REQUIRE_NON_DEFAULT_CREDENTIALS |
| S6 | Cookie secure=False 默认 | ⚠️ 半修 | auth.py:218 走 config.COOKIE_SECURE，但生产环境无强校验（C2）|
| 2.1 | 状态管理器 3 套并存 | ✅ 修复 | state/ 只剩 database_manager.py(332 行) |
| 2.1 | OrchestratorAgent 死代码 | ✅ 修复 | 文件已删 |
| 2.2 | routes.py 838 行 | ✅ 修复 | 拆为 10 个文件，聚合器 routes.py 仅 22 行 |
| 2.3 | dashboard 772 行 God Component | ✅ 修复 | 198 行，拆出 4 个组件 + 4 个 hooks |
| 2.4 | RAG 双重包装 | ✅ 修复 | langchain_llm.py / langchain_vectorstore.py 删 |
| 2.5 | RAG PGVectorStore 包名错配 | ✅ 修复 | vector_db.py 用 PGVectorClient 直连 |
| 3.5 | /api/chat/stream 假流式 | ✅ 修复 | chat_router.py:77-155 用 StreamingResponse + qa_agent.generate_response_stream |
| 3.6 | TraceContext threading.local 串号 | ✅ 修复 | utils/logger.py:37 改 ContextVar |
| 3.3 | **同步 LLM 阻塞 event loop** | ❌ 未修 | ali_llm.py 仍是 100% 同步 |
| 3.12 | **AppException 错误处理** | ❌ 未修 | main.py:127 handler 挂着但全项目 0 处 raise |
| 3.12 | **错误体 str(e) 泄露** | ❌ 未修 | 12+ 处仍 str(e) |
| 3.7 | 字段映射 SSOT | ⚠️ 部分修复 | SSOT + codegen 跑通，但 codegen 输出 broken TS（C1）|
| 6.1 | form_filler.py 1032 行 | ✅ 修复 | 拆为 5 个子模块，最大 301 行 |
| Celery | 死代码 | ✅ 修复 | 目录只剩 CLAUDE.md |

**修复率：12/17 真正修复，2/17 部分修复，3/17 完全未修**（占比 71% 修复 / 12% 部分 / 17% 未修）

## 06-03 新发现（06-01 报告没提到的）

| 位置 | 问题 | 严重度 |
|------|------|--------|
| `backend/api/files_router.py:68 vs 129` | 文件下载 404（重构引入） | Critical |
| `backend/api/extract_router.py:107-115` | batch SSE 假流式 + AST 违规 | Critical |
| `backend/scripts/codegen_field_schema.py:135-169` | 生成 broken TS 语法 | Critical |
| `frontend/e2e/fixtures/` | 目录不存在，2 个核心 e2e 永久 skip | Critical |
| `config/sectionConfig.ts:138, 140` | 'nested' 类型在 FormSection 无处理器 | Critical |
| `hooks/useFormState.ts:47-51` | auth check 前触发 createSession | Critical |
| `hooks/useAIChat.ts:62 + authStore.ts:52` | 登出后 AI 对话留 localStorage | Critical |
| `backend/agents/form_filler/mapping.py:49-73` | codegen 25+ 重复 dict key | High |
| `backend/api/auth.py:58, 100-116` | Token 内存降级 fallback 仍存在 | High |
| `backend/api/chat_router.py` | 路由 async def 但 0 await | High |
| `components/FormSection.tsx:185-194` | 条件字段 conditionField 0 存在 | High |
| `hooks/useFileUpload.ts:53-54` | 上传文件两次（06-01 P0 复发） | High |
| `frontend/e2e/section9-*.spec.ts` | 7 个重复 spec 文件 | Medium |
| `services/api.ts:30-31` | X-Request-ID 覆盖后端 trace | Medium |
| `backend/models/database.py:60-84` | PBKDF2 旧 100k 写回升级未实现 | High |

## 重构后整体评价（综合 4 Agent 共识）

- 06-01 评分 3-4/10 → 06-03 评分 5.5/10
- "安全 + 拆分 + 状态收敛"三大类（约 70% 工作量）做实
- "统一错误处理 + 异步化"两条 P0 规范完全没落地
- 引入至少 4 个新 Bug（文件下载 404、batch SSE 假流式、codegen 重复 key、'nested' 类型无处理器）
- 修复率 71% / 部分 12% / 未修 17%
- **核心运行时问题（LLM 阻塞）+ 错误体安全**仍是 0 进展

## 决策记录

| Decision | Rationale |
|----------|-----------|
| 06-03 不沿用 06-01 报告 | 旧报告基于已不存在的旧结构，盲目套用会失真 |
| 4 路并行 Agent 复用 | 与 06-01 同结构，但审查对象是新代码 |
| 探查优先于派 Agent | 必须先知道"已修什么"，才能让 Agent 找"未修什么 + 新问题" |
| 多 Agent 交叉验证 P0 | AppException / str(e) / 同步 LLM 都是 2-3 Agent 独立发现，可信度极高 |
| 报告落档 docs/CODE_REVIEW_2026-06-03.md | 按时间序列保留历史，区分"两轮审查" |
| 启动 planning-with-files 正确流程 | 06-01 漏了，06-03 第一时间建 task_plan.md / findings.md / progress.md |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| 06-01 任务开始未调用 planning-with-files | 06-03 第一时间建 task_plan.md |
| 06-01 报告未在产出时主动落档 | 06-03 在 Write 时直接落 docs/ |
| 06-03 启动 `git add -A` 时被用户打断 | 用户告知"已经全部修改了"，改为先审查再说 |
| 06-03 4 个后台 Agent 跑出 100+ 条原始问题 | 按严重度去重合并，按用户 8 节格式组织 |

## Resources

- 完整报告：`docs/CODE_REVIEW_2026-06-03.md`
- 上次报告：`docs/CODE_REVIEW_2026-06-01.md`
- 本次规划：`task_plan.md`
- 本次日志：`progress.md`
- 备份分支：`backup/pre-refactor-2026-06-01`（git 创建但未 commit）
- 14 个项目 CLAUDE.md（覆盖项目根、backend、frontend、agents、rag、app 等）
- 4 个 Agent 输出（保存在 tasks/*.output，不读，避免 context 溢出）
