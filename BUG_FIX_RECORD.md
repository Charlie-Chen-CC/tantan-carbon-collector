# Bug修复记录 - 碳管师收资系统

## Bug 1: Section 3/5/6/8 多行表格无法添加

### 问题描述
点击"添加"按钮没有任何反应，Console无日志输出。

### 根本原因
`MultiRowTable` 组件中的 `maxRows` 配置问题：
- Section 3 的所有多行字段 `maxRows` 设置为 `1`
- 组件使用 props 传入的 `entries` 数据，没有使用 `Form.useWatch` 监听表单值变化
- 添加行后 `entries` 没有更新，导致 UI 不刷新

### 修复方案
1. **调整 `maxRows` 配置** - 将相关字段的 `maxRows` 从 1 改为 10
2. **重构 `MultiRowTable` 组件** - 使用 `Form.useWatch` 监听表单值变化

### 修复后状态
✅ 已修复，手动添加功能正常

---

## Bug 2: AI提取数据后无法自动填充/显示

### 问题描述
上传文件后 AI 成功提取数据，后端返回正确，但前端表单不显示数据。需要切换 section 再切回才能看到。

### 后端问题 (已修复)
1. **JSON 解析失败**: `LLMExtractor._parse_json` 只支持简单的正则，无法解析嵌套 JSON
2. **字段格式不匹配**: LLM 返回数组格式，但前端期望扁平格式

### 后端修复
- `file_extractor.py` - 改进 JSON 解析，支持嵌套对象和数组
- `form_filler.py` - 重写 `fill_form` 方法，正确转换多行字段格式

### 后端修复后状态
✅ 后端正确返回 `filled_data`，包含转换后的前端字段格式

---

### 前端问题 (仍未解决)

#### 问题现象
- `form.setFieldValue()` 执行成功（Console 验证通过）
- `form.getFieldValue()` 可以获取到值
- 但 MultiRowTable 组件 UI 不刷新，不显示新数据

#### 已尝试的方案

| 方案 | 实现方式 | 结果 |
|------|----------|------|
| useReducer + forceUpdate | 使用 useReducer 管理渲染计数器 | ❌ 无效 |
| Content 添加 key | `key={formUpdateCounter}` | ❌ 无效 |
| tableData state + useEffect | 本地 state + 监听表单变化 | ❌ 无效 |
| Card 添加 key | `key={renderKey}` | ❌ 无效 |
| 直接使用 form.getFieldValue | 简化组件内部逻辑 | ❌ 无效 |
| Form.useWatch (组件级别) | 在 MultiRowTable 内使用 | ❌ 无效 |
| **Form.useWatch (最新)** | 在 MultiRowTable 内使用 `Form.useWatch(field.key, form)` | 待测试 |

---

### 当前代码状态 (2026-05-25 更新)

#### `MultiRowTable` 组件 - 最新版本
```typescript
function MultiRowTable({ field }: MultiRowTableProps) {
  const form = Form.useFormInstance();

  // 使用 useWatch 监听字段变化，确保数据更新时组件自动重新渲染
  const entries: MultiRowEntry[] = Form.useWatch(field.key, form) || [];

  const handleAddRow = () => {
    // ... 添加逻辑
    form.setFieldValue(field.key, [...entries, newEntry]);
  };

  // ... 其他 handlers
}
```

#### 数据提取处理 - 最新版本
```typescript
if (result.success && result.filled_data) {
  Object.entries(result.filled_data).forEach(([key, value]) => {
    form.setFieldValue(key, value);
  });
  // 后备方案：500ms后刷新页面
  setTimeout(() => {
    window.location.reload();
  }, 500);
  message.success({ content: '数据提取成功，页面将刷新显示', key: 'upload' });
}
```

---

### 待解决问题

1. **数据提取后 UI 不自动刷新** - 已改用 `Form.useWatch`，待用户测试
2. **刷新页面返回登录页** - 与 token 持久化有关，详见下方

---

## Bug 3: 刷新页面返回登录页

### 问题描述
登录后在 dashboard 页面刷新，页面跳转到 `/login`，需要重新登录。

### 原因分析
可能与以下因素有关：
- Token 存储方式（localStorage vs sessionStorage）
- Next.js 客户端水合（hydration）与 localStorage 读取时机
- AuthStore 初始化时序问题

### 相关文件
- `frontend/store/authStore.tsx` - 认证状态管理
- `frontend/services/api.ts` - API 服务层（含 401 响应拦截）

### 当前状态
❌ 未修复 - 需要进一步调查 AuthStore 和 API 拦截器的实现

---

## 待办事项

1. **测试 Bug 2 最新修复** - 验证 `Form.useWatch` 是否解决 UI 刷新问题
2. **修复 Bug 3** - 调查并解决登录状态持久化问题
3. **更新 CLAUDE.md** - 每次代码修改后更新项目文档

---

## 相关文件路径

```
tantan/
├── frontend/
│   ├── app/dashboard/page.tsx    # 主页面组件（含 MultiRowTable）
│   ├── store/authStore.tsx       # 认证状态管理
│   └── services/api.ts           # API 服务层
├── backend/
│   ├── agents/file_extractor.py  # 文件提取
│   ├── agents/form_filler.py     # 表单填充
│   └── api/routes.py             # API 路由
└── BUG_FIX_RECORD.md             # 本文件
```

---

## 测试方法

### Bug 2 测试步骤
1. 登录系统
2. 进入 Section 5 (制冷剂使用)
3. 上传包含制冷剂数据的 Excel 文件
4. 观察 Console 日志:
   - `[Dashboard] setFieldValue: airConditioners = [...]`
5. 观察前端 UI 是否自动显示数据，或 500ms 后页面刷新

### Bug 3 测试步骤
1. 登录系统，进入 dashboard
2. 刷新页面（F5）
3. 观察是否仍在 dashboard 或跳转到 login