# E2E Tests - Playwright 端到端测试

基于 Playwright 跑真实浏览器，覆盖 auth/dashboard/form/extract/upload 关键 user flow。

## 目录结构

```
e2e/
├── helpers.ts                       # 公共工具：genTestUser / register / login / logout
├── auth.spec.ts                     # 登录/登出 baseline
├── dashboard.spec.ts                # Dashboard 渲染 baseline
├── form.spec.ts                     # 表单填写 + 确认 + 进度
├── chat.spec.ts                     # 碳排放助手聊天
├── extract.spec.ts                  # AI 提取 happy path（依赖 fixtures/sample.xlsx）
├── upload.spec.ts                   # 文件上传 + 提取 + 填充（依赖 fixtures/sample.xlsx）
├── __n0-8_fixtures-present.spec.ts  # P0-8 守门：fixtures 存在 + spec 文件不再 test.skip
├── fixtures/
│   └── sample.xlsx                  # 5KB 真实 xlsx 来自 test_doc/extractable_by_section/section3
└── CLAUDE.md
```

## 跑测试

```bash
cd frontend
npx playwright test                       # 跑全部 21 测试
npx playwright test __n0-8_fixtures-present.spec.ts  # 只跑 P0-8 守门
npx playwright test --list                # 列出所有测试
```

## Fixtures

P0-8 修复后 `e2e/fixtures/sample.xlsx` 必须存在（5KB，section 3 燃料使用模拟数据）。
- 缺失会让 extract.spec.ts + upload.spec.ts 跑真实上传逻辑（不再静默 skip）
- 守门测试 `__n0-8_fixtures-present.spec.ts` 会 fail 当 fixture 缺失

## Helpers

`helpers.ts` 提供：
- `genTestUser()` - 唯一用户名（避免跨测试污染）
- `register(page, user)` - 注册后自动登录
- `login(page, user)` - 已注册用户登录
- `logout(page)` - 登出
- `waitForDashboardReady(page)` - 等待 dashboard 核心区域就绪

## 最近变更 (2026-06-05)

### P0-8 修复 - Playwright fixtures 不再假 skip
- 创建 `e2e/fixtures/sample.xlsx`（5KB 真实 xlsx，从 test_doc/extractable_by_section/section3/ 复制）
- 改 upload.spec.ts:16 + extract.spec.ts:16：
  - 旧：`test.skip(!require('fs').existsSync(FIXTURE), ...)`（CI 假绿灯）
  - 新：`if (!fs.existsSync(FIXTURE)) { throw new Error(...) }`（缺失直接 fail）
- 新建 `__n0-8_fixtures-present.spec.ts`（3 cases 守门测试）
  - fixture 存在且非空
  - upload.spec.ts 不含 test.skip fixture 模式
  - extract.spec.ts 不含 test.skip fixture 模式
