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
FILE_PREFIX = "sys_dat_"  # 名字改得更通用一点，不叫 backup
TEMP_FILE = "/tmp/core_cache.dat"

def log(msg):
    # 只打印必要信息
    print(f"[SYSTEM] {msg}", flush=True)

def check_connection(url, user, pwd):
    """
    静默检查连接，只有出错时才报错
    """
    try:
        response = requests.request(
            "PROPFIND",
            url,
            auth=HTTPBasicAuth(user, pwd),
            headers={"Depth": "0"},
            timeout=15
        )
        
        # 针对 InfiniCLOUD 的特殊检测
        if response.status_code == 200 and "html" in response.headers.get("Content-Type", ""):
            log("Connection Error: Endpoint returned HTML (Check Apps Connection/Password)")
            return False
        if response.status_code in [401, 403]:
            log("Auth Error: Access denied")
            return False
        if response.status_code == 404:
            log("Net Error: Endpoint not found")
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
    if not url:
        return

    # URL 和路径修正
    if not url.endswith("/"):
        url = url + "/"
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    # 静默检查
    if not check_connection(url, user, pwd):
        log("Sync skipped: Connection unstable")
        return

    try:
        client = get_client(url, user, pwd)
    except:
        return

    if action == "push":
        # 只有在真正开始传输时才打印一行，平时保持安静
        # log("Syncing data...") 
        
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
                return

            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Data synced: {filename}") # 只在成功时说一句话
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 静默清理旧文件
            try:
                files = client.ls(remote_dir, detail=True)
                backups = [f for f in files if f["type"] == "file" and f["name"].startswith(FILE_PREFIX)]
                backups.sort(key=lambda x: x["name"], reverse=True)
                if len(backups) > MAX_BACKUPS:
                    for item in backups[MAX_BACKUPS:]:
                        client.remove(f"{remote_dir}/{item['name']}")
            except:
                pass

        except Exception as e:
            log(f"Sync warning: {str(e)}")

    elif action == "pull":
        # 恢复时的日志可以稍微详细一点点，因为只会发生一次
        log("Initializing data recovery...")
        try:
            if not client.exists(remote_dir):
                log("New instance initialized.")
                return

            files = client.ls(remote_dir, detail=True)
            backups = [f for f in files if f["type"] == "file" and f["name"].startswith(FILE_PREFIX)]
            
            if not backups:
                return

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
