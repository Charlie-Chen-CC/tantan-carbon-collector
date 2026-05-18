# Frontend - Next.js前端应用

碳管师收资系统的前端，基于Next.js 14 App Router构建。

## 目录结构

```
frontend/
├── app/                    # Next.js App Router
│   ├── page.tsx           # 主页面（表单+AI悬浮窗）
│   ├── page.module.css    # 主页面样式
│   ├── layout.tsx         # 根布局
│   └── globals.css        # 全局样式
├── components/            # React组件（预留）
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

- **请求拦截器**：记录所有请求的 `method`、`url`、`X-Request-ID`
- **响应拦截器**：记录所有响应的 `status`、错误详情和完整堆栈
- **组件错误捕获**：各 catch 块使用 `console.error('[Component] 操作失败:', err)` 记录错误

错误日志格式：
```typescript
{
  type: 'API Error',
  requestId: string,
  method: string,
  url: string,
  status: number,
  message: string,
  stack: string,
  timestamp: string
}
```

## 字段配置

`SECTION_FIELDS` 定义了每个部分的字段元数据：
```typescript
interface FieldDef {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'file' | 'multi-row';
  placeholder?: string;
  options?: string[];      // select类型
  unit?: string;          // number类型
  maxRows?: number;       // multi-row最大行数
  fields?: FieldDef[];    // multi-row子字段
}
```

## 开发命令

```bash
cd frontend
npm run dev    # 开发模式
npm run build  # 生产构建
```