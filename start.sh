#!/bin/bash
# 碳管师收资系统 - 一键启动脚本
# 前后端自动检测端口，被占用时自动切换

echo "========================================"
echo "  碳管师收资系统启动器"
echo "========================================"
echo ""

# ===== 配置 =====
BACKEND_PORT=8000
BACKEND_MAX_PORT=8010
FRONTEND_PORT=3000
FRONTEND_MAX_PORT=3010

# ===== 检测端口函数 =====
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -i :$port &> /dev/null
    elif command -v ss &> /dev/null; then
        ss -tuln 2>/dev/null | grep -q ":$port "
    else
        return 1
    fi
}

# ===== 查找可用后端端口 =====
while check_port $BACKEND_PORT; do
    if [ $BACKEND_PORT -lt $BACKEND_MAX_PORT ]; then
        echo "[后端] 端口 $BACKEND_PORT 已被占用，尝试 $((BACKEND_PORT+1)) ..."
        BACKEND_PORT=$((BACKEND_PORT+1))
    else
        echo "[错误] 后端所有端口 (8000-$BACKEND_MAX_PORT) 都被占用"
        exit 1
    fi
done

# ===== 查找可用前端端口 =====
while check_port $FRONTEND_PORT; do
    if [ $FRONTEND_PORT -lt $FRONTEND_MAX_PORT ]; then
        echo "[前端] 端口 $FRONTEND_PORT 已被占用，尝试 $((FRONTEND_PORT+1)) ..."
        FRONTEND_PORT=$((FRONTEND_PORT+1))
    else
        echo "[错误] 前端所有端口 (3000-$FRONTEND_MAX_PORT) 都被占用"
        exit 1
    fi
done

echo "[后端] 使用端口: $BACKEND_PORT"
echo "[前端] 使用端口: $FRONTEND_PORT"
echo ""

# ===== 更新前端API代理配置 =====
echo "[配置] 更新前端API代理..."
cd "$(dirname "$0")/frontend"
sed -i.bak "s/localhost:[0-9]*/localhost:$BACKEND_PORT/g" next.config.js

# ===== 启动后端 =====
echo "[后端] 正在启动..."
cd "$(dirname "$0")/backend"
if [ -d "venv" ]; then
    source venv/Scripts/activate
fi
python main.py --port $BACKEND_PORT &
BACKEND_PID=$!
echo "[后端] 后端服务已启动 (PID: $BACKEND_PID, 端口 $BACKEND_PORT)"

# ===== 启动前端 =====
echo "[前端] 正在启动..."
cd "$(dirname "$0")/frontend"
PORT=$FRONTEND_PORT npm run dev &
FRONTEND_PID=$!
echo "[前端] 前端服务已启动 (PID: $FRONTEND_PID, 端口 $FRONTEND_PORT)"

echo ""
echo "========================================"
echo "  启动完成！"
echo "  后端: http://localhost:$BACKEND_PORT"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo "  按 Ctrl+C 停止服务"
echo "========================================"