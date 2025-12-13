#!/usr/bin/env python3
import os
import sys
import tarfile
import time
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
FILE_PREFIX = "sys_backup_"
TEMP_FILE = "/tmp/pkg_cache.dat"  # 伪装的临时文件名

def log(msg):
    print(f"[SYSTEM] {msg}", flush=True)

def get_client(url, user, password):
    options = {}
    if user and password:
        options = {"auth": (user, password)}
    # 增加超时设置，防止卡死
    options["timeout"] = 30
    return Client(url, **options)

def recursive_mkdir(client, remote_path):
    """
    暴力递归创建目录
    例如: /A/B/C -> 先检查/A, 再/A/B, 最后/A/B/C
    """
    if remote_path == "" or remote_path == "/":
        return

    # 规范化路径
    parts = [p for p in remote_path.split("/") if p]
    current_path = ""
    
    for part in parts:
        current_path += "/" + part
        try:
            if not client.exists(current_path):
                log(f"Creating missing directory: {current_path}")
                client.mkdir(current_path)
        except Exception as e:
            # 某些网盘如果目录已存在mkdir会报错，这里做个容错
            log(f"Dir check warning ({current_path}): {str(e)}")

def run_sync(action, url, user, pwd, remote_dir, local_path):
    if not url:
        log("Config Error: WEBDAV_URL is empty!")
        return

    # 路径清理：确保开头有/，结尾没有/
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    log(f"Connecting to: {url}")
    
    try:
        client = get_client(url, user, pwd)
        # 尝试列出根目录来测试连接
        client.ls("/", detail=False)
    except Exception as e:
        log(f"CRITICAL: Connection Refused! Check URL/User/Pwd. Details: {str(e)}")
        return

    # --- 备份模式 (PUSH) ---
    if action == "push":
        log(f"Starting Backup to: {remote_dir}")
        
        # 1. 确保目录存在 (递归创建)
        recursive_mkdir(client, remote_dir)

        # 2. 打包文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{FILE_PREFIX}{timestamp}.tar.gz"
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                # 统计打包文件数
                count = 0
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
                        count += 1
            
            if count == 0:
                log("Warning: Local directory is empty, nothing to backup.")
            
            # 3. 上传
            log(f"Uploading snapshot: {filename}...")
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Upload SUCCESS.")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 4. 轮转删除旧备份 (保留最近 MAX_BACKUPS 个)
            files = client.ls(remote_dir, detail=True)
            # 筛选出我们的备份
            backups = [
                f for f in files 
                if f["type"] == "file" 
                and f["name"].startswith(FILE_PREFIX)
            ]
            # 按名称(时间)倒序
            backups.sort(key=lambda x: x["name"], reverse=True)
            
            if len(backups) > MAX_BACKUPS:
                for item in backups[MAX_BACKUPS:]:
                    del_path = f"{remote_dir}/{item['name']}"
                    try:
                        client.remove(del_path)
                        log(f"Cleaned up old backup: {item['name']}")
                    except:
                        pass

        except Exception as e:
            log(f"Backup FAILED: {str(e)}")

    # --- 恢复模式 (PULL) ---
    elif action == "pull":
        log(f"Checking for backups in: {remote_dir}")
        try:
            if not client.exists(remote_dir):
                log("Remote folder not found. Skipping restore.")
                return

            files = client.ls(remote_dir, detail=True)
            backups = [
                f for f in files 
                if f["type"] == "file" 
                and f["name"].startswith(FILE_PREFIX)
            ]
            
            if not backups:
                log("No backup files found.")
                return

            # 找最新的
            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            remote_full_path = f"{remote_dir}/{latest['name']}"
            
            log(f"Restoring from: {latest['name']}")
            client.download_file(remote_full_path, TEMP_FILE)
            
            # 解压
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            
            log("Restore SUCCESS.")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

        except Exception as e:
            log(f"Restore FAILED: {str(e)}")

if __name__ == "__main__":
    # 参数: action, url, user, pwd, remote_dir, local_path
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
