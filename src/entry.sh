#!/bin/bash
# ----------------------------------------
echo "============== VERSION CHECK: V8 (PATH-FIXED) =============="
echo "Fixed: WebDAV 301 - Use relative paths for ls/exists/remove"
# ----------------------------------------

# --- 变量配置 ---
APP_DIR=${MUSIC_DIR:-/assets}
# 默认备份间隔1小时
SYNC_TIME=${SYNC_INTERVAL:-3600}
# 默认备份目录
REMOTE_DIR=${WEBDAV_REMOTE_PATH:-"/navidrome_backups"}

echo "[INIT] System online."

# 目录准备
mkdir -p ${APP_DIR} /data/cache /data/hf_cache /.cache /config
chmod -R 755 /data /.cache

# 激活 Python 虚拟环境
source /venv/bin/activate

# ============================================================
# 第一步：启动时恢复数据 (PULL) - 必须完成后才继续
# ============================================================
RESTORE_SUCCESS=false

if [ -n "$WEBDAV_URL" ]; then
    echo "[INIT] =========================================="
    echo "[INIT] STEP 1: Data recovery in progress..."
    echo "[INIT] =========================================="
    
    # 执行恢复操作（同步执行，会阻塞）
    python /app/sync_tool.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
    
    # 检查 Python 脚本的退出状态
    if [ $? -eq 0 ]; then
        RESTORE_SUCCESS=true
        echo "[INIT] ✓ Data recovery completed successfully."
    else
        echo "[INIT] ✗ Data recovery failed or no backup found."
    fi
    
    echo "[INIT] =========================================="
else
    echo "[INIT] No WebDAV configured, skipping data recovery."
fi

# ============================================================
# 第二步：资源加载 (HF Dataset 音乐) - 在恢复完成后才开始
# ============================================================
if [ -n "$DATASET_MUSIC_NAME" ]; then
    echo "[INIT] =========================================="
    echo "[INIT] STEP 2: Loading music resources..."
    echo "[INIT] =========================================="
    
    # 后台运行音乐资源加载器（不阻塞主进程启动）
    python /app/res_loader.py "$DATASET_MUSIC_NAME" "$MUSIC_TOKEN" "$APP_DIR" "$SYNC_TIME" "true" &
    MUSIC_LOADER_PID=$!
    
    echo "[INIT] Music loader started (PID: $MUSIC_LOADER_PID)"
    echo "[INIT] =========================================="
else
    echo "[INIT] No music dataset configured."
fi

# ============================================================
# 第三步：后台备份循环 (PUSH) - 定时自动备份
# ============================================================
backup_daemon() {
    echo "[BACKUP] =========================================="
    echo "[BACKUP] Backup service active."
    echo "[BACKUP] Interval: ${SYNC_TIME}s"
    echo "[BACKUP] =========================================="
    
    # 死循环定时备份
    while true; do
        echo "[BACKUP] ------------------------------------------"
        echo "[BACKUP] Starting backup job at $(date '+%Y-%m-%d %H:%M:%S')"
        echo "[BACKUP] ------------------------------------------"
        
        # 执行备份（同步执行）
        python /app/sync_tool.py push "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$REMOTE_DIR" "/data"
        
        if [ $? -eq 0 ]; then
            echo "[BACKUP] ✓ Backup completed successfully."
        else
            echo "[BACKUP] ✗ Backup failed."
        fi
        
        echo "[BACKUP] Next backup in ${SYNC_TIME}s..."
        echo "[BACKUP] ------------------------------------------"
        sleep $SYNC_TIME
    done
}

# 如果配置了 WebDAV，启动后台备份守护进程
if [ -n "$WEBDAV_URL" ]; then
    backup_daemon &
    BACKUP_PID=$!
    echo "[INIT] Backup daemon started (PID: $BACKUP_PID)"
else
    echo "[INIT] No WebDAV configured, backup service disabled."
fi

# ============================================================
# 第四步：启动主服务 (Navidrome)
# ============================================================
echo "[INIT] =========================================="
echo "[INIT] STEP 3: Launching main service..."
echo "[INIT] =========================================="

SERVICE_BIN="/app/server_core"
if [ -f "$SERVICE_BIN" ]; then
    echo "[INIT] ✓ Core binary found: $SERVICE_BIN"
    echo "[INIT] Starting service on port 4533..."
    echo "[INIT] =========================================="
    
    # 使用 exec 替换当前 shell 进程，确保信号正确传递
    exec $SERVICE_BIN
else
    echo "[INIT] ✗ ERROR: Binary not found at $SERVICE_BIN"
    exit 1
fi
