#!/usr/bin/env python3
import os
import sys
import tarfile
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
# 新生成的文件用这个前缀
CURRENT_PREFIX = "sys_dat_"
# 清理时，识别这些前缀的文件（涵盖了我们之前的所有版本）
TARGET_PREFIXES = ("sys_dat_", "sys_data_", "sys_backup_")
TEMP_FILE = "/tmp/core_cache.dat"

def log(msg):
    print(f"[SYSTEM] {msg}", flush=True)

def check_connection(url, user, pwd):
    try:
        response = requests.request(
            "PROPFIND",
            url,
            auth=HTTPBasicAuth(user, pwd),
            headers={"Depth": "0"},
            timeout=15
        )
        if response.status_code == 200 and "html" in response.headers.get("Content-Type", ""):
            log("Error: Endpoint returned HTML")
            return False
        if response.status_code in [401, 403]:
            log("Error: Access denied")
            return False
        if response.status_code == 404:
            log("Error: Endpoint not found")
            return False
        return True
    except:
        return False

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
                client.mkdir(current_path)
        except:
            pass

def run_sync(action, url, user, pwd, remote_dir, local_path):
    if not url: return

    # 路径规范化：确保 remote_dir 开头有 / 结尾没有 /
    if not url.endswith("/"): url = url + "/"
    if not remote_dir.startswith("/"): remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    if not check_connection(url, user, pwd):
        log("Connection unstable, sync skipped.")
        return

    try:
        client = get_client(url, user, pwd)
    except:
        return

    if action == "push":
        recursive_mkdir(client, remote_dir)
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
            
            if count == 0: return

            # 2. 上传
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Data synced: {filename}")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 3. 强力清理旧文件
            try:
                # 获取目录下所有文件
                files = client.ls(remote_dir, detail=True)
                
                # 筛选：只要是 tar.gz 且前缀匹配我们用过的任何一种
                backups = [
                    f for f in files 
                    if f["type"] == "file" 
                    and f["name"].endswith(".tar.gz")
                    and f["name"].startswith(TARGET_PREFIXES)
                ]
                
                # 按文件名倒序 (最新的在前)
                backups.sort(key=lambda x: x["name"], reverse=True)
                
                total_count = len(backups)
                
                if total_count > MAX_BACKUPS:
                    # 保留前5个，剩下的都要删
                    files_to_keep = backups[:MAX_BACKUPS]
                    files_to_delete = backups[MAX_BACKUPS:]
                    
                    log(f"Cleanup: Found {total_count} backups. Keeping {len(files_to_keep)}, Deleting {len(files_to_delete)}.")
                    
                    for item in files_to_delete:
                        file_name = item['name']
                        # 拼接完整路径，处理斜杠
                        del_path = f"{remote_dir}/{file_name}".replace("//", "/")
                        
                        try:
                            client.remove(del_path)
                            log(f"Deleted old backup: {file_name}")
                        except Exception as e:
                            log(f"Failed to delete {file_name}: {str(e)}")
                else:
                    # 如果数量没超标，就不输出日志，保持安静
                    pass
                            
            except Exception as e:
                log(f"Cleanup error: {str(e)}")

        except Exception as e:
            log(f"Sync warning: {str(e)}")

    elif action == "pull":
        log("Initializing data recovery...")
        try:
            if not client.exists(remote_dir): return

            files = client.ls(remote_dir, detail=True)
            # 恢复时也识别所有前缀
            backups = [
                f for f in files 
                if f["type"] == "file" 
                and f["name"].endswith(".tar.gz")
                and f["name"].startswith(TARGET_PREFIXES)
            ]
            
            if not backups: return

            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            remote_full_path = f"{remote_dir}/{latest['name']}"
            
            client.download_file(remote_full_path, TEMP_FILE)
            
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            
            log("Data restored successfully.")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

        except:
            log("Recovery skipped.")

if __name__ == "__main__":
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
