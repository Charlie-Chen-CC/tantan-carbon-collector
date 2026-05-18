# 碳管师收资系统

碳排放资料收集与表单填报系统，支持 AI 辅助数据提取和智能问答。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + PostgreSQL + Redis + LangChain/LangGraph
- **前端**: Next.js 14 (App Router) + React + TypeScript + Ant Design
- **AI**: 阿里云 DashScope API (通义千问/文本嵌入)

## 功能特性

- **表单填报** - 9个部分的碳排放数据收集表单，支持多行动态字段
- **文件提取** - 支持 xlsx, xls, pdf, docx, doc, pptx, md, png, jpg, jpeg 格式，AI 自动提取数据并填充表单
- **批量处理** - 多个证明文件智能分组、优先级提取、结果合并
- **AI助手** - 悬浮窗形式，支持专业问题问答和填报指导
- **进度跟踪** - 显示各部分完成状态

## 快速启动

### 一键启动（Windows）

```bash
start.bat
```

### 单独启动

**后端**
```bash
cd backend
source venv/Scripts/activate
python main.py --port 8000
```

**前端**
```bash
cd frontend
npm run dev
```

## 项目结构

```
tantan/
├── backend/          # FastAPI 后端服务
│   ├── agents/      # AI Agent 模块
│   ├── api/          # REST API 路由
│   ├── rag/          # RAG 知识库检索
│   └── models/       # 数据库模型
├── frontend/         # Next.js 前端应用
│   ├── app/          # App Router 页面
│   ├── components/   # React 组件
│   └── services/     # API 服务层
└── uploads/          # 用户上传文件存储
```

## 环境变量

后端需要配置 `.env` 文件：

```
DASHSCOPE_API_KEY=your_api_key
DATABASE_URL=postgresql://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379
VECTOR_DB_TYPE=pgvector
```

## 文档

详细技术文档见各模块的 `CLAUDE.md` 文件。