# 碳管师收资系统 - 后端 Dockerfile (Phase 6.9)
# 基于 Python 3.11 slim（psycopg2-binary / pgvector 等 C 扩展在 3.11 上 wheel 完备）
#
# 项目结构特殊：`tantan/` 既是项目根目录也是 Python 包名，运行时须在 tantan/ 父目录
#
# 构建：  cd claude_workspace && docker build -f tantan/backend/Dockerfile -t tantan-backend .
# 运行：  docker run --rm -p 8000:8000 --env-file tantan/backend/.env tantan-backend

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# 系统依赖：build-essential（C 扩展编译）+ libpq-dev（psycopg2）+ libmagic1（python-magic）
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 单独装依赖层（利用 Docker 缓存，源码变动不重装）
COPY tantan/backend/requirements.txt /app/tantan/backend/requirements.txt
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ -r /app/tantan/backend/requirements.txt \
    && pip install -i https://mirrors.aliyun.com/pypi/simple/ "setuptools<81"

# 复制后端代码
COPY tantan/backend/ /app/tantan/backend/

# 数据卷挂载点
RUN mkdir -p /app/tantan/uploads /app/tantan/logs
VOLUME ["/app/tantan/uploads", "/app/tantan/logs"]

# 健康检查（main.py 暴露 /health 端点）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

EXPOSE 8000

# 启动：直接调模块入口（uvicorn 在 main.py __main__ 块里启）
CMD ["python", "-m", "tantan.backend.main", "--port", "8000"]
