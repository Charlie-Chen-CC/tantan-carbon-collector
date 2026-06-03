# Components - React 组件层

Next.js 14 App Router + Antd + TypeScript。所有组件以 `'use client'` 开头（需客户端 hooks）。

## 目录结构（Phase 3.3 重构后）

```
components/
├── FormSidebar.tsx        # 侧边栏：Logo + 9 section 步骤节点 + 折叠
├── FormSection.tsx        # 单 section 表单字段渲染（包含 MultiRowTable 子组件）
├── FloatingAI.tsx         # 碳排放助手悬浮窗（对话列表 + 聊天区）
├── FileUploadPanel.tsx    # 文件上传面板（批量上传 + section 隔离）
└── CLAUDE.md
```

## 组件契约

### FormSidebar

| Prop | 类型 | 说明 |
|------|------|------|
| `collapsed` | `boolean` | 折叠状态 |
| `currentSection` | `number` | 当前 section（1-9） |
| `progress` | `Record<string, string>` | 各 section 状态（completed / in_progress / not_started） |
| `onToggleCollapse` | `() => void` | 折叠/展开切换 |
| `onSectionChange` | `(section: number) => void` | 点击 section 节点 |

无内部状态，纯展示 + 回调。父组件负责持久化 collapsed 状态。

### FormSection

| Prop | 类型 | 说明 |
|------|------|------|
| `fields` | `FieldDef[]` | 当前 section 字段定义 |
| `watchedValues` | `Record<string, any>` | 表单值快照（用于条件字段判断） |
| `onFileUpload` | `(file: File) => void` | 文件上传回调（FormSection 只触发，业务由父组件做） |

**关键设计**：FormSection 不包含 `<Form>` 容器，父组件提供 `form` 实例 + `key`（保证 section 切换时表单重置）。

子组件：
- `MultiRowTable`：用 `Form.useFormInstance()` 拿 form 实例，用 `Form.useWatch(field.key, form)` 订阅多行数据
- 字段渲染：`text` / `number` / `select` / `file` / `multi-row`
- 条件字段：`conditionField` + `conditionValue`，不满足返回 `null`

### FloatingAI

| Prop | 类型 | 说明 |
|------|------|------|
| `open` | `boolean` | 是否展开 |
| `onClose` | `() => void` | 关闭回调 |
| `sessionId` | `string \| null` | 当前会话 ID（无则禁用发送） |
| `currentSection` | `number` | 当前 section（消息上下文） |
| `initialPos` | `{x, y}` | 初始位置（默认 `{x: 24, y: 20}`） |
| `onPositionChange` | `(pos) => void` | 拖动结束位置同步给父组件 |

**关键 hook 集成**：
- `useAIChat()`：对话列表 + 当前消息 + 发送（内部 `useRef activeConvIdRef` 防止 3.5 消息重复）
- `useDragPosition({ initial, threshold: 5 })`：拖动定位（threshold 区分点击 vs 拖动）

### FileUploadPanel

| Prop | 类型 | 说明 |
|------|------|------|
| `sessionId` | `string` | 当前会话 ID |
| `section` | `number` | 当前 section（用于文件隔离） |
| `onDataExtracted` | `(data) => void` | extract 返回的 filled_data 透传 |

**重构要点**：
- 用 `useFileUpload(sessionId, section)` hook 替代手写 fetch（统一走 `fileApi` axios + httpOnly cookie）
- hook 内部 `useRef uploadingRef` 防止 3.7 重复上传
- 切换 section 时 hook `useEffect(refresh)` 自动刷新文件列表

## 与 Hooks 的对应关系

```
FormSidebar     → 无（纯展示）
FormSection     → 无（Form.useFormInstance + Form.useWatch）
FloatingAI      → useAIChat + useDragPosition
FileUploadPanel → useFileUpload
```

## 样式

所有组件共用 `app/dashboard/page.module.css` 样式（避免组件级 CSS 文件散乱）。新增 className 前缀约定：
- 侧边栏：`sider*` / `steps*`
- 表单：`fieldGroup*` / `multiRow*`
- AI 窗：`ai*`
- 上传：`fileUpload*`

## 最近变更 (2026-06-02)

### Phase 3.3 - 拆 4 个组件
- 从 `app/dashboard/page.tsx`（772 行）抽出 4 个独立组件
- 复用 Phase 3.2 的 4 个 hooks
- FormSection 单独封装 MultiRowTable 子组件
- FloatingAI 用 useAIChat + useDragPosition 替代内联 useState 重复实现
- FileUploadPanel 重构为纯组件，删 getAuthToken（已废弃）+ 手写 fetch

### 行数控制
- FormSidebar: ~80 行
- FormSection: ~180 行（包含 MultiRowTable）
- FloatingAI: ~140 行
- FileUploadPanel: ~150 行
