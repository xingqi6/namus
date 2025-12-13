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
TEMP_FILE = "/tmp/pkg_cache.dat"

def log(msg):
    print(f"[SYSTEM] {msg}", flush=True)

def get_client(url, user, password):
    options = {}
    if user and password:
        options = {"auth": (user, password)}
    options["timeout"] = 30
    return Client(url, **options)

def recursive_mkdir(client, remote_path):
    if remote_path == "" or remote_path == "/":
        return
    parts = [p for p in remote_path.split("/") if p]
    current_path = ""
    for part in parts:
        current_path += "/" + part
        try:
            if not client.exists(current_path):
                log(f"Creating directory: {current_path}")
                client.mkdir(current_path)
        except Exception:
            pass

def run_sync(action, url, user, pwd, remote_dir, local_path):
    if not url:
        log("Config Error: WEBDAV_URL is empty!")
        return

    # --- 修正 1: 强制 URL 结尾加上 / ---
    if not url.endswith("/"):
        url = url + "/"

    # --- 修正 2: 规范化远程路径 ---
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    log(f"Connecting to: {url}")
    
    try:
        client = get_client(url, user, pwd)
        # 尝试列出根目录
        client.ls("/", detail=False)
    except Exception as e:
        err_msg = str(e)
        if "not a multistatus response" in err_msg:
            log(f"CRITICAL: WebDAV Error! The server returned HTML instead of XML.")
            log(f"1. Check if 'Apps Connection' is turned ON in InfiniCLOUD settings.")
            log(f"2. Check if you are using the 'Apps Password' (NOT login password).")
            log(f"3. Check if URL is correct: {url}")
        else:
            log(f"CRITICAL: Connection Failed! {err_msg}")
        return

    # --- 备份模式 (PUSH) ---
    if action == "push":
        log(f"Starting Backup to: {remote_dir}")
        
        # 递归创建目录
        recursive_mkdir(client, remote_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{FILE_PREFIX}{timestamp}.tar.gz"
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                count = 0
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
                        count += 1
            
            if count == 0:
                log("Warning: Local data empty, skipping backup.")
                return

            log(f"Uploading snapshot: {filename}...")
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Upload SUCCESS.")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 清理旧备份
            try:
                files = client.ls(remote_dir, detail=True)
                backups = [f for f in files if f["type"] == "file" and f["name"].startswith(FILE_PREFIX)]
                backups.sort(key=lambda x: x["name"], reverse=True)
                
                if len(backups) > MAX_BACKUPS:
                    for item in backups[MAX_BACKUPS:]:
                        del_path = f"{remote_dir}/{item['name']}"
                        client.remove(del_path)
                        log(f"Cleaned old backup: {item['name']}")
            except Exception:
                pass

        except Exception as e:
            log(f"Backup FAILED: {str(e)}")

    # --- 恢复模式 (PULL) ---
    elif action == "pull":
        log(f"Checking backups in: {remote_dir}")
        try:
            if not client.exists(remote_dir):
                log("Remote folder not found. Skipping restore.")
                return

            files = client.ls(remote_dir, detail=True)
            backups = [f for f in files if f["type"] == "file" and f["name"].startswith(FILE_PREFIX)]
            
            if not backups:
                log("No backup files found.")
                return

            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            remote_full_path = f"{remote_dir}/{latest['name']}"
            
            log(f"Restoring from: {latest['name']}")
            client.download_file(remote_full_path, TEMP_FILE)
            
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            
            log("Restore SUCCESS.")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

        except Exception as e:
            log(f"Restore FAILED: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
