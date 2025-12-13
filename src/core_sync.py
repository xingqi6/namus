#!/usr/bin/env python3
import os
import sys
import tarfile
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
# 备份保留数量
MAX_BACKUPS = 5
# 备份文件前缀 (用于识别和伪装)
FILE_PREFIX = "sys_data_"
# 临时文件路径
TEMP_FILE = "/tmp/temp_pkg.tar.gz"

def log(msg):
    print(f"[SYSTEM] {msg}")

def get_client(url, user, password):
    options = {}
    if user and password:
        options = {"auth": (user, password)}
    return Client(url, **options)

def extract_tar(tar_file, dest_dir):
    try:
        with tarfile.open(tar_file, "r:gz") as tar:
            tar.extractall(path=os.path.dirname(dest_dir))
        return True
    except Exception as e:
        log(f"Extraction failed: {str(e)}")
        return False

def get_remote_files(client, remote_dir):
    """获取远程目录下的备份文件列表，按文件名(时间)倒序排列"""
    try:
        if not client.exists(remote_dir):
            return []
        
        # ls 返回的是对象列表
        files = client.ls(remote_dir, detail=True)
        # 筛选出我们的备份文件
        backups = [
            f for f in files 
            if f["type"] == "file" 
            and f["name"].startswith(FILE_PREFIX) 
            and f["name"].endswith(".tar.gz")
        ]
        # 按名称倒序排序 (因为名称包含时间戳: sys_data_2023...)
        # 最新的在前面
        backups.sort(key=lambda x: x["name"], reverse=True)
        return backups
    except Exception as e:
        log(f"List files error: {str(e)}")
        return []

def run_sync(action, url, user, pwd, remote_dir, local_path):
    if not url:
        return

    client = get_client(url, user, pwd)
    
    # 确保远程目录路径格式正确 (去掉末尾斜杠)
    remote_dir = remote_dir.rstrip('/')

    # --- 恢复逻辑 (Pull) ---
    if action == "pull":
        log("Initializing system recovery...")
        
        # 1. 获取所有备份
        backups = get_remote_files(client, remote_dir)
        
        if not backups:
            log("No remote data found. Starting fresh.")
            return

        # 2. 找到最新的备份
        latest_backup = backups[0]
        remote_file_path = os.path.join(remote_dir, latest_backup["name"])
        log(f"Found latest snapshot: {latest_backup['name']}")

        # 3. 下载
        try:
            client.download_file(remote_file_path, TEMP_FILE)
            extract_tar(TEMP_FILE, local_path)
            log("System restored successfully.")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
        except Exception as e:
            log(f"Restore failed: {str(e)}")

    # --- 备份逻辑 (Push) ---
    elif action == "push":
        # 1. 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{FILE_PREFIX}{timestamp}.tar.gz"
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            # 2. 打包本地数据 (排除cache)
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
            
            # 3. 确保远程目录存在
            if not client.exists(remote_dir):
                client.mkdir(remote_dir)
            
            # 4. 上传
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Snapshot uploaded: {filename}")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 5. 清理旧备份 (保留策略)
            backups = get_remote_files(client, remote_dir)
            if len(backups) > MAX_BACKUPS:
                # 获取需要删除的文件列表 (跳过前 MAX_BACKUPS 个)
                to_delete = backups[MAX_BACKUPS:]
                for item in to_delete:
                    delete_path = os.path.join(remote_dir, item["name"])
                    try:
                        client.remove(delete_path)
                        log(f"Rotated/Deleted old snapshot: {item['name']}")
                    except Exception as e:
                        log(f"Failed to delete {item['name']}: {str(e)}")

        except Exception as e:
            log(f"Backup operation failed: {str(e)}")

if __name__ == "__main__":
    # 参数顺序：action, url, user, pwd, remote_dir, local_path
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
