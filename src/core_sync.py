#!/usr/bin/env python3
import os
import sys
import tarfile
from datetime import datetime
from webdav4.client import Client

# 配置
MAX_BACKUPS = 5
FILE_PREFIX = "sys_data_"
TEMP_FILE = "/tmp/temp_pkg.tar.gz"

def log(msg):
    print(f"[SYSTEM] {msg}", flush=True)

def get_client(url, user, password):
    options = {}
    if user and password:
        options = {"auth": (user, password)}
    return Client(url, **options)

def run_sync(action, url, user, pwd, remote_dir, local_path):
    if not url:
        log("Error: WEBDAV_URL missing")
        return

    # 规范化路径：开头加/，结尾去/
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    try:
        client = get_client(url, user, pwd)
    except Exception as e:
        log(f"Connection Error: {str(e)}")
        return

    # --- PUSH 逻辑 (立即执行) ---
    if action == "push":
        # 1. 强制检查并创建目录
        try:
            if not client.exists(remote_dir):
                log(f"Remote dir '{remote_dir}' not found. Creating...")
                client.mkdir(remote_dir)
                log(f"Created directory: {remote_dir}")
            else:
                log(f"Remote directory '{remote_dir}' exists.")
        except Exception as e:
            log(f"Make directory FAILED: {str(e)}")
            log("Attempting to upload to root as fallback...")
            # 如果创建失败，尝试把路径回退到根目录 (可选，防止彻底失败)
            # remote_dir = "" 

        # 2. 打包
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{FILE_PREFIX}{timestamp}.tar.gz"
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
            
            # 3. 上传
            log(f"Uploading to: {remote_full_path}")
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Upload SUCCESS: {filename}")

            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 4. 删除旧备份
            try:
                files = client.ls(remote_dir, detail=True)
                backups = [f for f in files if f["name"].startswith(FILE_PREFIX) and f["name"].endswith(".tar.gz")]
                backups.sort(key=lambda x: x["name"], reverse=True)
                
                if len(backups) > MAX_BACKUPS:
                    for item in backups[MAX_BACKUPS:]:
                        del_path = os.path.join(remote_dir, item["name"])
                        client.remove(del_path)
                        log(f"Deleted old backup: {item['name']}")
            except Exception as e:
                log(f"Cleanup warning: {str(e)}")

        except Exception as e:
            log(f"Push FAILED: {str(e)}")

    # --- PULL 逻辑 ---
    elif action == "pull":
        try:
            if not client.exists(remote_dir):
                log(f"Backup dir {remote_dir} not found. Skip restore.")
                return

            files = client.ls(remote_dir, detail=True)
            backups = [f for f in files if f["name"].startswith(FILE_PREFIX) and f["name"].endswith(".tar.gz")]
            
            if not backups:
                log("No backups found.")
                return

            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            remote_path = os.path.join(remote_dir, latest["name"])
            
            log(f"Restoring from: {latest['name']}")
            client.download_file(remote_path, TEMP_FILE)
            
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
            log("Restore Done.")

        except Exception as e:
            log(f"Pull FAILED: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
