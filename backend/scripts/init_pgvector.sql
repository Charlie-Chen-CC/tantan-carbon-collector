-- pgvector 扩展启用脚本 (Phase 6.9 docker-compose)
-- docker-compose 启动时由 postgres 容器自动执行（/docker-entrypoint-initdb.d/）
-- 创建 vector 扩展供后端 PGVector 客户端使用

CREATE EXTENSION IF NOT EXISTS vector;
