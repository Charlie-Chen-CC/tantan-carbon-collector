# 碳管师收资系统

碳排放资料收集与表单填报系统，支持AI辅助数据提取和智能问答。

## 项目结构

```
tantan/
├── backend/          # FastAPI后端服务
├── frontend/         # Next.js前端应用
└── uploads/          # 用户上传文件存储目录
```

## 技术栈

- **后端**: FastAPI + SQLAlchemy + PostgreSQL + Redis + LangChain/LangGraph
- **前端**: Next.js 14 (App Router) + React + TypeScript
- **AI**: 阿里云DashScope API (通义千问/文本嵌入)

## 一键启动

项目根目录有启动脚本，自动检测端口占用并切换：

```bash
# Windows
start.bat

# Linux/macOS
./start.sh
```

脚本会自动：
1. 检测8000-8010端口，找可用后端端口
2. 检测3000-3010端口，找可用前端端口
3. 更新前端API代理配置
4. 同时启动前后端服务

## 快速启动（单独启动）

### 后端
```bash
cd backend
# 激活虚拟环境
source venv/Scripts/activate
# 启动服务（默认8000，可通过 --port 指定）
python main.py --port 8000
# 服务运行在 http://localhost:8000
```

### 前端
```bash
cd frontend
npm run dev
# 服务运行在 http://localhost:3000
```

## 环境变量

后端需要配置 `.env` 文件（参考 `backend/.env.example`）：
- `DASHSCOPE_API_KEY` - 阿里云API密钥
- `DATABASE_URL` - PostgreSQL连接字符串
- `REDIS_URL` - Redis连接字符串
- `VECTOR_DB_TYPE` - 向量数据库类型 (pgvector/milvus/qdrant)

## 主要功能

1. **表单填报** - 9个部分的碳排放数据收集表单，支持多行动态字段
2. **文件提取** - 上传Excel文件，AI自动提取数据并填充表单
3. **AI助手** - 悬浮窗形式，支持专业问题问答和填报指导
4. **进度跟踪** - 显示各部分完成状态