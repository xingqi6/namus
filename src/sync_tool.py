#!/usr/bin/env python3
import os, sys, tarfile, requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
CURRENT_PREFIX = "sys_dat_"
# 【修正】加入了 navidrome_backup_，确保能识别并删除最早期的备份
TARGET_PREFIXES = ("sys_dat_", "sys_data_", "sys_backup_", "navidrome_backup_") 
TEMP_FILE = "/tmp/core_cache.dat"

def log(msg): print(f"[SYSTEM] {msg}", flush=True)

# ... (check_connection, get_client, recursive_mkdir 函数保持不变，直接复制之前的即可) ...
# 为了节省篇幅，这里只写变动的部分，请保留上面的辅助函数

def check_connection(url, user, pwd):
    # ... (保持不变) ...
    try:
        response = requests.request("PROPFIND", url, auth=HTTPBasicAuth(user, pwd), headers={"Depth": "0"}, timeout=15)
        return response.status_code not in [401, 403, 404]
    except: return False

def get_client(url, user, password):
    return Client(url, auth=(user, password), timeout=30)

def recursive_mkdir(client, remote_path):
    # ... (保持不变) ...
    pass

def run_sync(action, url, user, pwd, remote_dir, local_path):
    if not url: return
    if not url.endswith("/"): url = url + "/"
    if not remote_dir.startswith("/"): remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    if not check_connection(url, user, pwd):
        log("Connection skipped.")
        return

    try:
        client = get_client(url, user, pwd)
    except: return

    if action == "push":
        # recursive_mkdir(client, remote_dir) # 如果目录已存在可省略
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{CURRENT_PREFIX}{timestamp}.tar.gz"
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            # 1. 打包
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                count = 0
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
                        count += 1
            
            if count > 0:
                client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
                log(f"Data synced: {filename}")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 2. 清理旧文件 (关键修正部分)
            try:
                files = client.ls(remote_dir, detail=True)
                # 筛选所有相关的备份文件
                backups = [
                    f for f in files 
                    if f["type"] == "file" 
                    and f["name"].endswith(".tar.gz")
                    and f["name"].startswith(TARGET_PREFIXES)
                ]
                backups.sort(key=lambda x: x["name"], reverse=True)
                
                total = len(backups)
                if total > MAX_BACKUPS:
                    delete_list = backups[MAX_BACKUPS:]
                    # 打印出来让我们看到它在工作
                    log(f"Cleanup: Found {total} files. Deleting {len(delete_list)} old backups...")
                    for item in delete_list:
                        try:
                            client.remove(f"{remote_dir}/{item['name']}")
                            log(f"Deleted: {item['name']}")
                        except: pass
            except Exception as e:
                log(f"Cleanup error: {str(e)}")

        except Exception as e:
            log(f"Sync error: {str(e)}")

    elif action == "pull":
        log("Initializing recovery...")
        try:
            if not client.exists(remote_dir): return
            files = client.ls(remote_dir, detail=True)
            # 恢复时也识别旧名字
            backups = [
                f for f in files 
                if f["type"] == "file" 
                and f["name"].endswith(".tar.gz")
                and f["name"].startswith(TARGET_PREFIXES)
            ]
            if not backups: return

            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            
            client.download_file(f"{remote_dir}/{latest['name']}", TEMP_FILE)
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            log(f"Restored from {latest['name']}")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
        except: pass

if __name__ == "__main__":
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
