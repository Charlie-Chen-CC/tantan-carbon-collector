# Backend Tests - pytest 套件

## 目录结构

```
tests/
├── conftest.py                        # sys.path 注入
├── backend/
│   ├── api/
│   │   ├── conftest.py                # TestClient + test_user + registered_user fixtures
│   │   ├── test_routes.py             # 路由聚合 + 文件 MIME 验证
│   │   ├── test_auth.py               # 注册/登录/登出/me/cookie
│   │   ├── test_files.py              # 上传 happy/400 octet-stream/401
│   │   ├── test_chat.py               # chat/stream 鉴权
│   │   └── test_form.py               # 会话/表单 CRUD + section 切换
│   ├── agents/
│   │   ├── test_file_extractor.py
│   │   ├── test_file_processor.py
│   │   ├── test_form_filler.py
│   │   ├── test_pdf_splitter.py
│   │   └── test_e2e_pipeline.py       # FileExtract → FormFill → DB 验证
│   ├── rag/
│   │   ├── test_retriever.py          # RAGSearcher 无静默 fallback
│   │   └── test_retrieval_quality.py  # top1 命中 + 排序 + 边界
│   └── utils/
└── CLAUDE.md
```

## 测试命令

```bash
cd "C:/Users/25776/Desktop/work/claude_workspace/tantan"
source tantan/backend/.venv/Scripts/activate

# 全量
PYTHONIOENCODING=utf-8 python -m pytest tantan/backend/tests -v

# 单文件
python -m pytest tantan/backend/tests/backend/api/test_auth.py -v

# 覆盖率
python -m pytest tantan/backend/tests --cov=tantan.backend --cov-report=term-missing
```

## Fixtures

`tests/backend/api/conftest.py` 提供：

| Fixture | 作用域 | 说明 |
|---------|--------|------|
| `client` | function | FastAPI TestClient（每次新实例） |
| `test_user` | function | 唯一测试用户（时间戳后缀） |
| `registered_user` | function | 注册后返回 `{client, user, password}` |
| `db_session` | function | 直接 DB session（清理用） |

## 测试数据隔离

- 用户名带 `api_test_{ms_timestamp}` 后缀
- 每个 test 独立 `client`（cookie 隔离）
- 测试间**不**清理 DB（PostgreSQL 跑测试足够快；如需清理加 `db_session` fixture）

## 最近变更 (2026-06-02)

### Phase 4 补强
- **test_auth.py** (9 cases) - 注册/登录/cookie/登出
- **test_files.py** (6 cases) - 上传 happy + octet-stream 拒绝 + 401
- **test_chat.py** (5 cases) - chat/stream 鉴权 + session 404
- **test_form.py** (10 cases) - session CRUD + form PATCH/confirm/section
- **test_retrieval_quality.py** (7 cases) - RAG top1 命中 + 排序 + 边界
- **test_e2e_pipeline.py** (10 cases) - FormFillAgent Section 1/3/9 全流程

### Phase 5.3 补强
- **test_chat.py** (3 cases) - 流式 SSE 事件序列 + history 持久化 + guidance 规则流式

### Phase 5.4 补强
- **test_trace_context.py** (10 cases) - ContextVar 基本读写 + token 嵌套还原 + 跨 asyncio.Task 传播

### Phase 5.6 补强
- **test_telemetry.py** (8 cases) - OTel 默认关闭 + 启用装 TracerProvider + NoOp tracer fallback

### Phase 5.7 补强
- **test_metrics.py** (11 cases) - Prometheus 默认关闭 + 计数器 inc + /metrics 端点 + histogram + 独立 registry

### Phase 5.8 补强
- **test_ratelimit.py** (15 cases) - slowapi 默认开启 + 装饰器 + 触发 429 + Retry-After 头 + 常量稳定
- **test_section_options.py** (15 cases) - Section 1-9 提示词反硬编码注入断言（Phase 6.1）
- **test_codegen_field_schema.py** (13 cases) - SSOT JSON 结构 + codegen --check + 关键字段断言（Phase 6.3）

### 总数
- 之前：62 tests
- Phase 4：109 tests（+47）
- Phase 5.3：112 tests（+3）
- Phase 5.4：122 tests（+10）
- Phase 5.6：130 tests（+8）
- Phase 5.7：141 tests（+11）
- Phase 5.8：156 tests（+15）
- Phase 6.1：171 tests（+15）
- Phase 6.3：184 tests（+13）
- **P0-2a**：195 tests（+11: 4 bridge + 7 ali_llm async）

## 注意事项

- Windows 平台跑测试必须 `PYTHONIOENCODING=utf-8`（中文 logger.info 不乱码）
- 跑 API 测试需要 PostgreSQL 跑着（COZE 真实 DB）
- 跑 form 切 section 测试用 `?section=N` query 而非 json body（FastAPI 默认行为）
