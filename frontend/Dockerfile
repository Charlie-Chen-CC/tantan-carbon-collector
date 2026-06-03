# 碳管师收资系统 - 前端 Dockerfile (Phase 6.9)
# 多阶段构建：deps 装包 → builder 构建 → runner 精简运行
#
# 构建：  cd claude_workspace && docker build -f tantan/frontend/Dockerfile -t tantan-frontend .
# 运行：  docker run --rm -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://host:8000 tantan-frontend

# ============== 阶段 1: 依赖 ==============
FROM node:20-alpine AS deps
WORKDIR /app
COPY tantan/frontend/package.json tantan/frontend/package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm ci --no-audit --no-fund

# ============== 阶段 2: 构建 ==============
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY tantan/frontend/ ./
# 关键：Next.js standalone 模式生成最小化的 .next/standalone 目录
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ============== 阶段 3: 运行时 ==============
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# 非 root 用户（安全）
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# 复制 standalone 产物
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public 2>/dev/null || true

USER nextjs

EXPOSE 3000

# 健康检查（Next.js 启动后 / 返回 200）
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
