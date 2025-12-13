#!/bin/bash

# --- 变量配置 ---
# 默认值设置
APP_DIR=${MUSIC_DIR:-/assets}
SYNC_TIME=${SYNC_INTERVAL:-3600}
REMOTE_FILE=${WEBDAV_REMOTE_PATH:-"/data_package.tar.gz"}

echo "[INIT] System starting..."

# 目录准备
mkdir -p ${APP_DIR} /data/cache /.cache /config
chmod -R 755 /data /.cache

# 激活 Python 环境
source /venv/bin/activate

# 1. 尝试恢复数据 (WebDAV)
if [ -n "$WEBDAV_URL" ]; then
    echo "[INIT] Retrieving external configurations..."
    python /app/core_sync.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_FILE" "/data"
fi

# 2. 资源加载 (HF Dataset 音乐)
if [ -n "$DATASET_MUSIC_NAME" ]; then
    echo "[INIT] Starting resource loader..."
    # 后台运行音乐同步循环
    python /app/res_loader.py "$DATASET_MUSIC_NAME" "$MUSIC_TOKEN" "$APP_DIR" "$SYNC_TIME" "true" &
fi

# 3. 后台备份进程 (WebDAV)
sync_loop() {
    echo "[bg_task] Sync service standby. Interval: ${SYNC_TIME}s"
    # 等待一段时间再开始第一次自动备份
    sleep 60
    while true; do
        sleep $SYNC_TIME
        python /app/core_sync.py push "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_FILE" "/data"
    done
}

if [ -n "$WEBDAV_URL" ]; then
    sync_loop &
fi

# 4. 启动伪装的主进程
# 我们在 Dockerfile 里把 navidrome 改名成了 server_core
SERVICE_BIN="/app/server_core"

if [ -f "$SERVICE_BIN" ]; then
    echo "[INIT] Launching core service..."
    # 这里的 exec 会替换当前 shell 进程，让 server_core 成为 PID 1 (或主进程)
    exec $SERVICE_BIN
else
    echo "[ERROR] Core binary missing."
    exit 1
fi
