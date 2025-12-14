#!/usr/bin/env python3
import os
import sys
import tarfile
import time
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
FILE_PREFIX = "sys_backup_"
TEMP_FILE = "/tmp/pkg_cache.dat"

def log(msg):
    print(f"[SYSTEM] {msg}", flush=True)

def debug_connection(url, user, pwd):
    """
    暴力调试函数：直接发送底层请求，看服务器到底回了什么
    """
    log(f"--- DEBUG START ---")
    log(f"Target: {url}")
    log(f"User: {user}")
    log(f"Pwd Length: {len(pwd)} chars")
    
    try:
        # 发送标准的 WebDAV PROPFIND 请求
        response = requests.request(
            "PROPFIND",
            url,
            auth=HTTPBasicAuth(user, pwd),
            headers={"Depth": "0"},
            timeout=15
        )
        
        log(f"Server Response Code: {response.status_code}")
        
        if response.status_code == 401:
            log("❌ ERROR: 401 Unauthorized. 密码或用户名绝对错了！")
            log("请检查：1. 是否开启了 Apps Connection? 2. 是否使用了 User ID? 3. 是否使用了 Apps Password?")
            return False
        elif response.status_code == 404:
            log("❌ ERROR: 404 Not Found. URL 地址不对！")
            log("InfiniCLOUD 的地址通常是: https://你的服务器.infini-cloud.net/dav/")
            return False
        elif response.status_code == 200 and "html" in response.headers.get("Content-Type", ""):
            log("❌ ERROR: Server returned HTML (Login Page).")
            log("这通常意味着 URL 写错了，或者 Apps Connection 没开。")
            # 打印前200个字符看看是什么网页
            log(f"Page Content: {response.text[:200]}...")
            return False
        elif response.status_code == 207:
            log("✅ Connection Check Passed! (Status 207 Multi-Status)")
            return True
        else:
            log(f"⚠️ Unknown Status: {response.status_code}")
            return False
            
    except Exception as e:
        log(f"❌ Network Error: {str(e)}")
        return False
    finally:
        log(f"--- DEBUG END ---")

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

    # 强制 URL 修正
    if not url.endswith("/"):
        url = url + "/"

    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    # --- 第一步：先运行诊断 ---
    if not debug_connection(url, user, pwd):
        log("🚨 Diagnostics failed. Aborting sync to prevent crash.")
        return

    # 如果诊断通过，继续常规流程
    try:
        client = get_client(url, user, pwd)
    except Exception as e:
        log(f"Client Init Error: {str(e)}")
        return

    if action == "push":
        log(f"Starting Backup to: {remote_dir}")
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
                log("Local data empty.")
                return

            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"Upload SUCCESS: {filename}")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # Cleanup
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
            log(f"Backup FAILED: {str(e)}")

    elif action == "pull":
        # ... (Pull 逻辑保持不变，为节省篇幅省略，因为目前主要卡在连接上) ...
        # 如果你需要 Pull 代码，请保留之前的 Pull 逻辑
        pass

if __name__ == "__main__":
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
