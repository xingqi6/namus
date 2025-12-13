#!/bin/bash

# --- 变量配置 ---
APP_DIR=${MUSIC_DIR:-/assets}
# 默认备份间隔1小时
SYNC_TIME=${SYNC_INTERVAL:-3600}
# 默认备份目录
REMOTE_DIR=${WEBDAV_REMOTE_PATH:-"/navidrome_backups"}

echo "[INIT] System online."

# 目录准备
mkdir -p ${APP_DIR} /data/cache /.cache /config
chmod -R 755 /data /.cache

# 激活环境
source /venv/bin/activate

# 1. 启动时恢复数据 (PULL)
if [ -n "$WEBDAV_URL" ]; then
    echo "[INIT] Checking remote data..."
    # 使用 sync_tool.py (请确保 Dockerfile 里 COPY 的文件名也改了，或者这里用 core_sync.py)
    python /app/sync_tool.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
fi

# 2. 资源加载 (HF Dataset 音乐)
if [ -n "$DATASET_MUSIC_NAME" ]; then
    echo "[INIT] Loading resources..."
    python /app/res_loader.py "$DATASET_MUSIC_NAME" "$MUSIC_TOKEN" "$APP_DIR" "$SYNC_TIME" "true" &
fi

# 3. 后台备份循环 (PUSH)
backup_daemon() {
    echo "[bg_task] Backup service active. Interval: ${SYNC_TIME}s"
    
    # ！！！重点：死循环，立即执行，不等待！！！
    while true; do
        echo "[bg_task] Starting backup job..."
        python /app/sync_tool.py push "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
        
        echo "[bg_task] Job finished. Sleeping for ${SYNC_TIME}s..."
        sleep $SYNC_TIME
    done
}

if [ -n "$WEBDAV_URL" ]; then
    backup_daemon &
fi

# 4. 启动主进程
SERVICE_BIN="/app/server_core"
if [ -f "$SERVICE_BIN" ]; then
    echo "[INIT] Launching core..."
    exec $SERVICE_BIN
else
    echo "[ERROR] Binary not found!"
    exit 1
fi
