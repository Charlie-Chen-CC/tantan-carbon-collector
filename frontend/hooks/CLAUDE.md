# Hooks - 自定义 React Hooks 层

业务逻辑下沉到 hooks，组件只负责渲染。

## 目录结构（Phase 3.2 创建）

```
hooks/
├── useDragPosition.ts    # 通用拖动定位（悬浮球/悬浮窗共用）
├── useAIChat.ts          # AI 对话管理（解决 3.5 消息重复）
├── useFileUpload.ts      # 文件上传 + section 隔离（解决 3.7 重复上传）
├── useFormState.ts       # 会话 + 表单状态机（解决 3.6 createSession 闭包）
└── CLAUDE.md
```

## Hook 详细说明

### useDragPosition

**用途**：通用拖动定位，悬浮球 + 悬浮窗共用。

```typescript
const { position, isDragging, wasJustDragged, dragHandlers, reset } = useDragPosition({
  initial: { x: 0, y: 0 },
  threshold: 5,  // 触发拖动的最小位移（区分点击 vs 拖动）
});
```

**返回字段**：
- `position`：当前位置
- `isDragging`：是否正在拖动
- `wasJustDragged`：本次按下是否触发了拖动（用于 onClick 中区分）
- `dragHandlers`：直接展开到元素的 `{ onMouseDown }`
- `reset(newPos?)`：重置位置

**实现关键**：
- 用 `useRef` 存起点和是否已移动标记，避免 state 异步更新导致漏判
- 监听 `document.mousemove` / `mouseup`（不是元素局部事件，跟随鼠标）

### useAIChat

**用途**：AI 对话管理。持久化到 localStorage（key: `ai_conversations`）。

```typescript
const { conversations, currentConvId, currentMessages, isLoading,
        inputMessage, setInputMessage, setCurrentConvId,
        sendMessage, newConversation } = useAIChat();
```

**关键 bug 修复 - 3.5 消息重复**：
- 用 `useRef activeConvIdRef` 锁定本次发送的 convId
- 异步过程中即便 React state 变了，append 仍写到正确对话
- 配套：函数式 setState 避免基于旧值读写

**API 调用**：`chatApi.send(sessionId, text, { current_section: section })`

### useFileUpload

**用途**：文件上传 + section 隔离。

```typescript
const { files, isUploading, uploadAndExtract, deleteFile, refresh } = useFileUpload(sessionId, section);
```

**关键 bug 修复 - 3.7 重复上传**：
- `useRef uploadingRef` 同步检查 + 设置（state 异步会有窗口期）
- `uploadAndExtract`：上传 → 提取 → 返回 filled_data（不写入 form）
- 父组件拿到 filled_data 后自行 `form.setFieldValue`

**Section 隔离**：
- `useEffect(refresh)` 监听 sessionId/section 变化自动重刷文件列表
- 切换 section 时无需手动调用 refresh

### useFormState

**用途**：会话 + 表单状态机。

```typescript
const { session, loadState, currentSection,
        switchSection, confirmSection, reloadSession } = useFormState(autoCreate);
```

**关键 bug 修复 - 3.6 createSession 闭包**：
- 状态机：`idle` → `loading` → `ready` / `error`
- `useRef createdRef` 防止 Strict Mode / 多次 effect 触发时的重复创建
- 失败时回滚 `createdRef = false` 允许重试

**State 字段**：
- `session`：当前会话（`SessionData | null`）
- `loadState`：4 态状态机
- `currentSection`：便捷访问（`session?.current_section ?? 1`）

## Hook 设计原则

1. **不直接操作 antd `form` 实例** - 表单实例由组件管理，hook 只提供数据
2. **错误用 message.error / console.error** - 不抛异常给组件（组件只关心成功路径）
3. **持久化副作用放在 useEffect** - 不在 useState 初始值里访问 localStorage
4. **不返回 JSX** - 渲染逻辑在组件中
5. **依赖数组精准** - 用 useRef 持有 sessionId 等会变值，避免 callback 重新创建

## 引用关系

- `useAIChat` → `chatApi` (services/api.ts)
- `useFileUpload` → `fileApi` (services/api.ts)
- `useFormState` → `sessionApi`, `formApi` (services/api.ts)
- `useDragPosition` → 纯函数无外部依赖

## 最近变更 (2026-06-02)

### Phase 3.2 - 写 4 个 hooks
- useDragPosition：通用拖动，threshold + useRef 防误判
- useAIChat：用 useRef activeConvIdRef 修 3.5 消息重复
- useFileUpload：用 uploadingRef 修 3.7 重复上传
- useFormState：用 createdRef + 状态机修 3.6 createSession 闭包
