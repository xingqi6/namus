#!/bin/bash

# --- 变量配置 ---
# 默认值设置
APP_DIR=${MUSIC_DIR:-/assets}
SYNC_TIME=${SYNC_INTERVAL:-3600}

# 注意：这里的 REMOTE_DIR 对应环境变量 WEBDAV_REMOTE_PATH
# 默认为根目录下的 /navidrome_backups 文件夹
REMOTE_DIR=${WEBDAV_REMOTE_PATH:-"/navidrome_backups"}

echo "[INIT] System starting..."

# 目录准备
mkdir -p ${APP_DIR} /data/cache /.cache /config
chmod -R 755 /data /.cache

# 激活 Python 环境
source /venv/bin/activate

# 1. 尝试恢复数据 (WebDAV)
if [ -n "$WEBDAV_URL" ]; then
    echo "[INIT] Retrieving external configurations..."
    # 传入 REMOTE_DIR (文件夹路径) 而不是具体文件
    python /app/core_sync.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
fi

# 2. 资源加载 (HF Dataset 音乐)
if [ -n "$DATASET_MUSIC_NAME" ]; then
    echo "[INIT] Starting resource loader..."
    python /app/res_loader.py "$DATASET_MUSIC_NAME" "$MUSIC_TOKEN" "$APP_DIR" "$SYNC_TIME" "true" &
fi

# 3. 后台备份进程 (WebDAV)
sync_loop() {
    echo "[bg_task] Sync service standby. Interval: ${SYNC_TIME}s"
    # 启动后先等待一段时间再进行第一次备份
    sleep 300 
    while true; do
        python /app/core_sync.py push "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
        sleep $SYNC_TIME
    done
}

if [ -n "$WEBDAV_URL" ]; then
    sync_loop &
fi

# 4. 启动主进程 (已重命名为 server_core)
SERVICE_BIN="/app/server_core"

if [ -f "$SERVICE_BIN" ]; then
    echo "[INIT] Launching core service..."
    exec $SERVICE_BIN
else
    echo "[ERROR] Core binary missing."
    exit 1
fi
