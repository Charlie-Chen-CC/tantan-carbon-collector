# Task Plan: 重新 Code Review（2026-06-03）

<!--
  重新审查 2026-06-01 报告后的实际项目状态。
  2026-06-01 报告：docs/CODE_REVIEW_2026-06-01.md
  旧规划：见 git 历史（备份分支 backup/pre-refactor-2026-06-01）
  本次要做的：
    1. 探查项目实际状态
    2. 对照旧报告逐项验证修复情况
    3. 找出新结构下的新问题
    4. 落档 docs/CODE_REVIEW_2026-06-03.md
-->

## Goal

在 2026-06-01 Code Review 之后，项目已按报告 Phase 1+2+部分 Phase 6 重构。重新审查：
1. 验证旧报告 P0/P1 是否真修复
2. 找出新结构下新引入的问题
3. 找出旧报告里漏掉但仍然存在的问题
4. 给出 2026-06-03 版报告

## Current Phase

Phase 1：项目结构探查 + 修复进度验证

## Phases

### Phase 1: 探查 + 验证修复进度
- [ ] 列目录结构（backend/frontend 各自新布局）
- [ ] 验证 3 个死代码文件已删（orchestrator/celery_app/manager）
- [ ] 验证 routes.py 拆分（看是否真有 9 个 router 文件）
- [ ] 验证 form_filler 拆分（看是否真有 5 个子模块）
- [ ] 验证 RAG 去 LangChain 包装
- [ ] 验证 python-magic 文件 MIME 验证
- [ ] 验证 PBKDF2 100k 是否升级
- [ ] 验证 Token 改 HttpOnly Cookie
- [ ] 验证 dashboard 拆分 hooks/组件
- [ ] 验证 RAG 包名错配（PGVector）
- **Status:** in_progress

### Phase 2: 派 5 路并行 Agent 重新审查
- [ ] Agent 1: 后端架构（针对拆分后的新结构）
- [ ] Agent 2: 前端架构（针对重构后的 dashboard）
- [ ] Agent 3: 安全（验证旧 P0 修复 + 找新漏洞）
- [ ] Agent 4: 异步并发 + RAG（验证去 LC 后的新实现）
- [ ] Agent 5: 工程规范（CLAUDE.md 执行率、新模块质量）
- **Status:** pending

### Phase 3: 汇总 + 落档
- [ ] 去重合并
- [ ] 输出 2026-06-03 版报告
- [ ] 落档 docs/CODE_REVIEW_2026-06-03.md
- [ ] 更新 task_plan.md / findings.md / progress.md
- **Status:** pending

## Key Questions

1. 旧报告 P0 真修复了？还是只删了文件没改实质？
2. 拆分后新模块间的耦合度如何？是否引入新循环依赖？
3. 去 LangChain 后 RAG 管道是更简单还是更乱？
4. python-magic 实际是否在用？是否回退到无验证？
5. 前端 dashboard 拆 hooks 之后还是不是 God Component？

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 不沿用 2026-06-01 报告 | 旧报告基于已不存在的旧结构，盲目套用会失真 |
| 探查优先于派 Agent | 必须先知道"已修什么"，才能让 Agent 找"未修什么 + 新问题" |
| 5 路并行 Agent 复用 | 与 06-01 同结构，但审查对象是新代码 |
| 报告落档 docs/CODE_REVIEW_2026-06-03.md | 按时间序列保留历史，区分"两轮审查" |
| 启动 planning-with-files 正确流程 | 06-01 漏了，06-03 不重蹈 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 06-01 任务开始未调用 planning-with-files | 1 | 06-03 第一时间建 task_plan.md |
| 06-01 报告未在产出时主动落档 | 1 | 06-03 在 Write 时直接落 docs/ |
| 06-03 启动 `git add -A` 时被用户打断 | 1 | 用户告知"已经全部修改了"，改为先审查再说 |

## Notes

- 备份分支已建：`backup/pre-refactor-2026-06-01`（工作区原始状态）
- 当前 working tree 仍 modified，未 commit
- 06-01 报告里的 3 个死代码文件已被删（orchestrator/celery_app/manager）
- backend/CLAUDE.md 在 06-03 已被项目维护者更新（透露 Phase 2.4/2.5/2.6 已完成）
