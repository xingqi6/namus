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
# 统一前缀：请确保以后都用这个，不要改了
FILE_PREFIX = "sys_dat_" 
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

    # 路径规范化
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
        filename = f"{FILE_PREFIX}{timestamp}.tar.gz"
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

            # 3. 清理旧文件 (增强版)
            try:
                # 获取列表
                files = client.ls(remote_dir, detail=True)
                
                # 筛选出符合当前前缀的备份文件
                backups = [
                    f for f in files 
                    if f["type"] == "file" 
                    and f["name"].startswith(FILE_PREFIX)
                ]
                
                # 按文件名倒序排列 (时间新的在前: 2025... 2024...)
                backups.sort(key=lambda x: x["name"], reverse=True)
                
                # 检查数量
                if len(backups) > MAX_BACKUPS:
                    # 只要超过5个，多出来的全部删掉
                    files_to_delete = backups[MAX_BACKUPS:]
                    
                    for item in files_to_delete:
                        file_name = item['name']
                        # 拼接删除路径
                        del_path = f"{remote_dir}/{file_name}"
                        
                        try:
                            client.remove(del_path)
                            # 打印日志让你知道删除了
                            log(f"Auto-cleanup: Removed old file {file_name}")
                        except Exception as e:
                            log(f"Cleanup failed for {file_name}: {str(e)}")
                            
            except Exception as e:
                log(f"Cleanup process error: {str(e)}")

        except Exception as e:
            log(f"Sync warning: {str(e)}")

    elif action == "pull":
        log("Initializing data recovery...")
        try:
            if not client.exists(remote_dir): return

            files = client.ls(remote_dir, detail=True)
            backups = [f for f in files if f["type"] == "file" and f["name"].startswith(FILE_PREFIX)]
            
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
