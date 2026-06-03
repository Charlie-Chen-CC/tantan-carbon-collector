# Frontend - Next.js前端应用

碳管师收资系统的前端，基于Next.js 14 App Router构建。

## 目录结构（Phase 3 重构后）

```
frontend/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # 根布局
│   ├── providers.tsx      # 全局 providers（zustand 初始化 + 401 监听）
│   ├── globals.css        # 全局样式
│   ├── login/             # 登录注册
│   └── dashboard/         # 主页面（Phase 3.4 目标 < 250 行）
│       ├── page.tsx
│       └── page.module.css
├── components/            # 业务组件（Phase 3.3 拆分）
│   ├── FormSidebar.tsx        # 侧边栏
│   ├── FormSection.tsx        # 表单字段渲染 + MultiRowTable
│   ├── FloatingAI.tsx         # 碳排放助手悬浮窗
│   └── FileUploadPanel.tsx    # 文件上传面板
├── hooks/                 # 自定义 hooks（Phase 3.2）
│   ├── useDragPosition.ts     # 拖动定位
│   ├── useAIChat.ts           # AI 对话（修 3.5）
│   ├── useFileUpload.ts       # 文件上传（修 3.7）
│   └── useFormState.ts        # 会话状态机（修 3.6）
├── store/                 # zustand 状态管理（Phase 3.1）
│   └── authStore.ts
├── config/                # 配置
│   └── sectionConfig.ts       # SECTION_NAMES / SECTION_FIELDS
├── services/              # API 调用
│   └── api.ts                 # axios + httpOnly cookie
├── next.config.js         # Next.js配置
└── package.json
```

## 页面结构

### 主页面 (page.tsx)
- 顶部：标题和进度条
- 左侧：表单部分导航栏（9个部分）
- 右侧：表单填写区域
- 右下角：AI助手悬浮窗按钮

### AI悬浮窗
- 左侧：对话历史列表（localStorage持久化）
- 右侧：当前对话聊天区域
- 支持新建/切换/删除对话
- 支持最小化和关闭

## 表单部分

| 部分 | 名称 | 字段类型 |
|------|------|----------|
| 1 | 基本信息 | 文本/下拉 |
| 2 | 产品 | 文本/下拉/多行 |
| 3 | 燃料使用 | 下拉选择 |
| 4 | 电力、热力使用 | 下拉/文本 |
| 5 | 制冷剂使用 | 多行（标号+填充量）|
| 6 | 其他散逸类排放 | 文本 |
| 7 | 三废处理 | 下拉/多行 |
| 8 | 原材料使用 | 文件上传/多行 |
| 9 | 生产耗材 | 多行 |

## API代理

前端通过 `next.config.js` 配置代理：
- `/api/*` → `http://localhost:8000/api/*`

## 错误日志

前端统一通过 `services/api.ts` 处理错误：

- **请求拦截器**：仅注入 `X-Request-ID` 用于追踪（不再打印 Authorization 头）
- **响应拦截器**：5xx 才打 console.error；401 派发 `auth:logout` 自定义事件，AuthProvider 监听后清状态
- **组件错误捕获**：各 catch 块使用 `console.error('[Component] 操作失败:', err)` 记录错误

## 认证

- 唯一认证凭据是后端 `Set-Cookie` 写入的 httpOnly `auth_token`；前端无 token 操作
- `services/api.ts` 的 axios 实例开 `withCredentials: true`，浏览器自动携带 cookie
- 旧 `setAuthToken` / `getAuthToken` 保留为 no-op 仅为兼容；调用方应停止使用
- 401 → 派发 `window.dispatchEvent(new CustomEvent('auth:logout'))` → AuthProvider 收到事件后清空 user state
- **禁止**再使用 `localStorage` 存 token、**禁止**再手动加 `Authorization` 头

## 字段配置

`SECTION_FIELDS` 定义了每个部分的字段元数据：
```typescript
interface FieldDef {
  key: string;               // 英文字段名 (camelCase)
  label: string;
  type: 'text' | 'number' | 'select' | 'file' | 'multi-row';
  placeholder?: string;
  options?: string[];      // select类型
  unit?: string;          // number类型
  maxRows?: number;       // multi-row最大行数
  fields?: FieldDef[];    // multi-row子字段
}
```

## 前后端字段映射

前端使用英文字段名（camelCase），后端返回的数据需要通过 `FormFillAgent.BACKEND_TO_FRONTEND_FIELD_MAP` 映射转换。

**前后端字段名对应示例**：
| 前端 (camelCase) | 后端 (中文) |
|------------------|-------------|
| enterpriseName | 企业名称 |
| industry | 所属行业 |
| contactPhone | 联系方式 |
| productionAddress | 生产地址 |

添加字段时必须同时更新后端映射表和前端 `SECTION_FIELDS` 配置。

## 开发命令

```bash
cd frontend
npm run dev    # 开发模式
npm run build  # 生产构建
```

## 最近变更 (2026-06-02)

### Phase 3.1-3.3 前端重塑
- 引入 zustand@^4.5.0，重写 `store/authStore.ts`（cookie 认证 + 401 事件）
- 4 个 hooks：`useDragPosition` / `useAIChat`（修 3.5）/ `useFileUpload`（修 3.7）/ `useFormState`（修 3.6）
- 4 个组件拆分：`FormSidebar` / `FormSection` / `FloatingAI` / `FileUploadPanel`（重构为纯组件）
- 删 `authStore.tsx`，删 `getAuthToken` / `setAuthToken` 旧接口

## 最近变更 (2026-05-26)

### UI 去AI化
- 移除标题栏渐变色，改为纯色 `#1f4e79`
- 移除按钮渐变色，改为纯色
- 减小圆角：`8px/12px → 4px/6px`
- 移除悬浮放大动画效果
- 文案调整："AI助手" → "碳排放助手"

### 文件上传重构
- 移除单一文件上传入口，只保留批量上传
- 实现 section 间文件隔离：切换 section 时自动刷新该 section 的文件列表
- 新增 API：
  - `GET /api/files/{session_id}/section/{section}` - 获取指定 section 文件列表
  - `DELETE /api/files/{file_id}` - 删除文件

### 关键文件
- `app/dashboard/page.tsx` - 主页面（移除顶部和底部单一上传按钮）
- `app/page.module.css` - 样式（去渐变、减小圆角）
- `components/FileUploadPanel.tsx` - 文件上传面板（section 隔离）
- `services/api.ts` - API 调用（新增文件管理 API）