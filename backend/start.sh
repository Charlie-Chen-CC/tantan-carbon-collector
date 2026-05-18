#!/bin/bash
# 碳管师收资系统启动脚本
# 端口被占用时自动切换到下一个可用端口

cd "$(dirname "$0")"

# 默认端口
DEFAULT_PORT=8000
MAX_PORT=8010

# 检查端口是否可用
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -i :$port &> /dev/null
    elif command -v netstat &> /dev/null; then
        netstat -tuln 2>/dev/null | grep -q ":$port "
    else
        # fallback: 直接尝试启动看是否成功
        return 1
    fi
    return $?
}

# 启动函数
start_server() {
    local port=$1
    echo "正在启动后端服务..."
    echo "访问地址: http://localhost:$port"

    # 激活虚拟环境并启动
    if [ -d "venv" ]; then
        source venv/Scripts/activate
    fi

    python main.py --port $port
}

# 主逻辑
find_port() {
    local port=$DEFAULT_PORT

    while [ $port -le $MAX_PORT ]; do
        if ! check_port $port; then
            echo "端口 $port 可用"
            return $port
        fi
        echo "端口 $port 已被占用，尝试下一个..."
        port=$((port + 1))
    done

    echo "错误: 所有端口 ($DEFAULT_PORT-$MAX_PORT) 都被占用"
    exit 1
}

# 检查是否传入了端口参数
if [ "$1" = "--port" ] && [ -n "$2" ]; then
    PORT=$2
    echo "使用指定端口: $PORT"
else
    PORT=$(find_port)
fi

start_server $PORT