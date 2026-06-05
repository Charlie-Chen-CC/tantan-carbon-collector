# Task Plan: P0 修复（2026-06-04 起）

<!--
  基于 docs/CODE_REVIEW_2026-06-03.md 报告的 TOP 10 P0 修复
  用户原始指令：按 P0-1 → P0-10 顺序，每个 P0 一个 git 分支 + TDD + 验证 + commit
  详细清单见用户提示词 + progress.md
-->

## Goal

按 2026-06-03 报告的 TOP 10 P0 修复，每个 P0 一个独立分支、TDD、验证、commit。
不允许引入新 P0，遵循 feedback memory 强制规则（动代码必更新 CLAUDE.md，模块变更必更新 requirements.txt）。

## Current Phase

Phase 4：P0-1 完成 / 准备 P0-3

## Phases

### Phase 4: P0 修复（2026-06-04 起，预计 1 周）

- [x] **P0-1** AppException 替换 52 处 HTTPException（分支：fix/phase1-p0-1-app-exception）
- [ ] **P0-2** LLM/RAG/向量库 异步化（最大工作量）
- [ ] **P0-3** 文件下载 404 bug 修复
- [ ] **P0-4** batch SSE 假流式 + AST 违规
- [ ] **P0-5** 登出清 localStorage（GDPR）
- [ ] **P0-6** sectionConfig 'nested' 类型处理器（选 B：新增 MultiLevelTable）
- [ ] **P0-7** codegen 生成 broken TS 修复
- [ ] **P0-8** Playwright fixtures 缺失修复
- [ ] **P0-9** useFileUpload 上传文件两次修复（改 /api/extract 接收 file_id）
- [ ] **P0-10** useFormState 挂起等 auth check

**Status:** P0-1 done, 9 remaining

### Phase 5: 错误处理 + 规范落地（1 周）
- pre-commit hook（ruff + eslint + mypy + codegen --check + tsc --noEmit）
- CI/CD（GH Actions：lint → test → build）
- 删 14 个旧 e2e spec + 3 个 dev 垃圾 + section9 7 个重复 spec 保留 1 个
- requirements.txt 全部 `==` 锁定
- testcontainers 加 PG fixture
- `modify_agent.VALID_FIELDS` 派生自 `section_defs.py`
- `qa_agent.section_guides` 去重
- useAIChat loadFromStorage 改 useEffect
- useFormState console.error 改白名单 logger
- setAuthToken / getAuthToken no-op 删

### Phase 6: 性能与可观测（持续）
- Token 内存 fallback 删
- 大文件流式上传
- PBKDF2 写回升级
- N+1 修复
- Telemetry / Metrics 全面启用

### Phase 7: LLM 安全与一致性（持续）
- pydantic schema 校验 LLM 输出
- 提示词注入黑名单
- enum 白名单越界告警
- multi-row 字段聚合逻辑
- codegen sub_field 不再提升到 top-level
- form_filler SSOT 与 modify_agent VALID_FIELDS 派生

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| 顺序：P0-1 → P0-3 → P0-5 → P0-4 → P0-6 → P0-7 → P0-8 → P0-9 → P0-10 → P0-2 | P0-2 工作量最大且会触多个模块，放最后专注；其余按 ROI 排 |
| P0-6 选 (B) MultiLevelTable | 保留 section 9 分组语义，方案更完整 |
| P0-9 改 /api/extract 接收 file_id | 消除重复上传，cleaner than 前端兼容 |
| 完整 P0-1 → P0-10 一次走完 | 用户确认 4-5 天连续工作 |
| TDD：AST 守门 + 集成测试 | 防止回归（重构引入 4 个新 Critical Bug） |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| `_project_root()` parents[3] 算错（实际需要 parents[4]） | 1 | 直接 print 调试后修正 |
| `str()` AST 误报 developer_message=str(e) | 1 | 修正测试只扫 user_message/detail |
| `app.router.remove_route` 不存在 | 1 | 改用 `routes = [r for r in routes if r.path != path]` |

## Notes

- P0-1 commit 准备中（52 处替换 + 20 测试通过 + 58/58 全量 API 测试通过）
- 项目根：inner `tantan/` 是 git 仓库，working tree 在 v1.0 分支基础上
- 备份分支：`backup/pre-refactor-2026-06-01`（06-01 重构前），新增 `fix/phase1-p0-1-app-exception`（P0-1）

---

## 历史：2026-06-03 Code Review（已完成）

<!--
  重新审查 2026-06-01 报告后的实际项目状态。Phase 1-3 已完成。
  详细见 findings.md + docs/CODE_REVIEW_2026-06-03.md。
-->

