# 碳管师收资系统

碳排放资料收集与表单填报系统，支持AI辅助数据提取和智能问答。

## 项目结构

```
tantan/                          # 项目根目录 (Python包: tantan)
├── backend/                     # FastAPI后端服务
│   ├── Dockerfile               # 后端镜像构建 (Phase 6.9)
│   └── scripts/init_pgvector.sql # pgvector 扩展启用
├── frontend/                    # Next.js前端应用
│   └── Dockerfile               # 前端镜像构建 (Phase 6.9，multi-stage + standalone)
├── docs/                        # 项目文档（Code Review、改进记录）
├── scripts/                     # 辅助脚本
├── uploads/                      # 用户上传文件（不纳入版本控制）
├── logs/                         # 运行日志（不纳入版本控制）
├── test_doc/                     # 测试文档数据
├── docker-compose.yml            # 一键拉起 backend+frontend+postgres+redis (Phase 6.9)
├── .dockerignore
├── start.bat                     # Windows 一键启动
├── start.sh                     # Linux/macOS 启动
├── stop.bat                     # Windows 停止
├── restart.bat                  # Windows 重启
└── CLAUDE.md                    # 项目说明
```

## 技术栈

- **后端**: FastAPI + SQLAlchemy + PostgreSQL + Redis + LangChain/LangGraph
- **前端**: Next.js 14 (App Router) + React + TypeScript
- **AI**: 阿里云DashScope API (通义千问/文本嵌入)

## 启动方式

### 重要：Python包结构

项目使用 `tantan` 作为根包名，目录结构为：
- `tantan/` = Python包根目录
- `tantan/backend/` = 后端代码
- `tantan/frontend/` = 前端代码

**运行时必须设置 PYTHONPATH**：
```bash
# 从workspace目录 (tantan的父目录) 运行
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m tantan.backend.main --port 8000

# 测试运行
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests
```

### 一键启动

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

### Docker 一键拉起

```bash
cd claude_workspace
export DASHSCOPE_API_KEY=sk-xxx
docker compose -f tantan/docker-compose.yml up -d
# 前端：http://localhost:3000
# 后端：http://localhost:8000/docs
# 跟踪日志：docker compose -f tantan/docker-compose.yml logs -f backend
# 停服+清数据卷：docker compose -f tantan/docker-compose.yml down -v
```

镜像构建基于 Python 3.11-slim（后端）+ Node 20-alpine（前端 multi-stage standalone）。
`backend/scripts/init_pgvector.sql` 自动启用 `vector` 扩展。
生产环境必须设 `ALLOWED_ORIGINS`（docker-compose 拒绝空值 → fail-fast）。

### 单独启动

#### 后端
```bash
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m tantan.backend.main --port 8000
# 服务运行在 http://localhost:8000
```

#### 前端
```bash
cd tantan/frontend
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

## 字段映射

后端提取的中文字段名通过 `FormFillAgent.BACKEND_TO_FRONTEND_FIELD_MAP` 映射为前端英文字段名。

如需添加新字段，必须同时更新：
1. `tantan/backend/agents/form_filler.py` 中的 `section_definitions`
2. `BACKEND_TO_FRONTEND_FIELD_MAP` 映射表
3. 前端 `SECTION_FIELDS` 配置

## 测试

```bash
# 从workspace目录运行所有测试
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests --tb=short
```