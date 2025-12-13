#!/bin/bash

# --- 变量配置 ---
APP_DIR=${MUSIC_DIR:-/assets}
SYNC_TIME=${SYNC_INTERVAL:-3600}
# 这里的 REMOTE_DIR 对应你在 HF 填写的 WEBDAV_REMOTE_PATH (例如 /navidrome_backups)
REMOTE_DIR=${WEBDAV_REMOTE_PATH:-"/navidrome_backups"}

echo "[INIT] System starting..."

# 目录准备
mkdir -p ${APP_DIR} /data/cache /.cache /config
chmod -R 755 /data /.cache

# 激活环境
source /venv/bin/activate

# 1. 尝试恢复数据 (Pull)
if [ -n "$WEBDAV_URL" ]; then
    echo "[INIT] Checking for existing backup..."
    python /app/core_sync.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
fi

# 2. 资源加载 (Dataset 音乐)
if [ -n "$DATASET_MUSIC_NAME" ]; then
    echo "[INIT] Starting resource loader..."
    python /app/res_loader.py "$DATASET_MUSIC_NAME" "$MUSIC_TOKEN" "$APP_DIR" "$SYNC_TIME" "true" &
fi

# 3. 后台备份进程 (Push) - 核心修改部分
sync_loop() {
    echo "[bg_task] Backup service active. Interval: ${SYNC_TIME}s"
    
    # 【修改点】去掉所有启动前的 sleep，直接进入循环
    while true; do
        echo "[bg_task] Executing IMMEDIATE backup..."
        python /app/core_sync.py push "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
        
        # 备份完之后再休息
        echo "[bg_task] Backup done. Next run in ${SYNC_TIME}s"
        sleep $SYNC_TIME
    done
}

if [ -n "$WEBDAV_URL" ]; then
    # 让备份进程在后台跑
    sync_loop &
fi

# 4. 启动主进程
SERVICE_BIN="/app/server_core"
if [ -f "$SERVICE_BIN" ]; then
    echo "[INIT] Launching core service..."
    exec $SERVICE_BIN
else
    echo "[ERROR] Core binary missing."
    exit 1
fi
