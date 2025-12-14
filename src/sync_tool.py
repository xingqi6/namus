#!/usr/bin/env python3
import os, sys, tarfile, requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
CURRENT_PREFIX = "sys_dat_"
# 支持识别所有历史备份前缀
TARGET_PREFIXES = ("sys_dat_", "sys_data_", "sys_backup_", "navidrome_backup_") 
TEMP_FILE = "/tmp/core_cache.dat"

def log(msg): 
    print(f"[SYSTEM] {msg}", flush=True)

def check_connection(url, user, pwd):
    """检查 WebDAV 连接是否可用"""
    try:
        response = requests.request(
            "PROPFIND", 
            url, 
            auth=HTTPBasicAuth(user, pwd), 
            headers={"Depth": "0"}, 
            timeout=15
        )
        return response.status_code not in [401, 403, 404]
    except Exception as e:
        log(f"Connection check failed: {str(e)}")
        return False

def get_client(url, user, password):
    """创建 WebDAV 客户端"""
    return Client(url, auth=(user, password), timeout=30)

def recursive_mkdir(client, remote_path):
    """递归创建远程目录"""
    parts = [p for p in remote_path.split('/') if p]
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        try:
            if not client.exists(current):
                client.mkdir(current)
        except:
            pass

def run_sync(action, url, user, pwd, remote_dir, local_path):
    """执行同步操作"""
    if not url: 
        log("No WebDAV URL provided, skipping sync.")
        return False
    
    # 规范化 URL 和路径
    if not url.endswith("/"): 
        url = url + "/"
    if not remote_dir.startswith("/"): 
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')

    # 检查连接
    if not check_connection(url, user, pwd):
        log("WebDAV connection failed or not configured.")
        return False

    try:
        client = get_client(url, user, pwd)
    except Exception as e:
        log(f"Failed to create WebDAV client: {str(e)}")
        return False

    if action == "push":
        log("Starting backup (PUSH)...")
        
        # 确保远程目录存在
        try:
            recursive_mkdir(client, remote_dir)
        except Exception as e:
            log(f"Failed to create remote directory: {str(e)}")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{CURRENT_PREFIX}{timestamp}.tar.gz"
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            # 1. 打包本地数据
            log(f"Creating backup archive: {filename}")
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                count = 0
                for root, dirs, files in os.walk(local_path):
                    # 排除缓存目录
                    if "cache" in dirs: 
                        dirs.remove("cache")
                    if "hf_cache" in dirs:
                        dirs.remove("hf_cache")
                    
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
                        count += 1
            
            if count == 0:
                log("No files to backup.")
                if os.path.exists(TEMP_FILE): 
                    os.remove(TEMP_FILE)
                return
            
            # 2. 上传到 WebDAV
            log(f"Uploading backup ({count} files)...")
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"✓ Backup uploaded: {filename}")
            
            # 清理临时文件
            if os.path.exists(TEMP_FILE): 
                os.remove(TEMP_FILE)

            # 3. 清理旧备份（保留最新的 MAX_BACKUPS 个）
            log("Checking for old backups to clean up...")
            try:
                files = client.ls(remote_dir, detail=True)
                
                # 筛选所有备份文件
                backups = [
                    f for f in files 
                    if f["type"] == "file" 
                    and f["name"].endswith(".tar.gz")
                    and any(f["name"].startswith(prefix) for prefix in TARGET_PREFIXES)
                ]
                
                # 按名称排序（时间戳在文件名中）
                backups.sort(key=lambda x: x["name"], reverse=True)
                
                total = len(backups)
                log(f"Found {total} backup file(s) in remote.")
                
                if total > MAX_BACKUPS:
                    delete_list = backups[MAX_BACKUPS:]
                    log(f"Removing {len(delete_list)} old backup(s)...")
                    
                    for item in delete_list:
                        try:
                            client.remove(f"{remote_dir}/{item['name']}")
                            log(f"✓ Deleted: {item['name']}")
                        except Exception as e:
                            log(f"✗ Failed to delete {item['name']}: {str(e)}")
                else:
                    log(f"No cleanup needed (keeping {total}/{MAX_BACKUPS}).")
                    
            except Exception as e:
                log(f"Cleanup error: {str(e)}")

        except Exception as e:
            log(f"Backup failed: {str(e)}")
            if os.path.exists(TEMP_FILE): 
                os.remove(TEMP_FILE)

    elif action == "pull":
        log("Starting data recovery (PULL)...")
        
        try:
            # 检查远程目录是否存在
            if not client.exists(remote_dir):
                log("Remote backup directory does not exist. Starting fresh.")
                return False
            
            files = client.ls(remote_dir, detail=True)
            
            # 查找所有备份文件
            backups = [
                f for f in files 
                if f["type"] == "file" 
                and f["name"].endswith(".tar.gz")
                and any(f["name"].startswith(prefix) for prefix in TARGET_PREFIXES)
            ]
            
            if not backups:
                log("No backup files found. Starting fresh.")
                return False

            # 获取最新的备份
            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            
            log(f"Found latest backup: {latest['name']}")
            log("Downloading backup...")
            
            # 下载备份文件
            client.download_file(f"{remote_dir}/{latest['name']}", TEMP_FILE)
            
            log("Extracting backup...")
            # 解压到目标目录
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            
            log(f"✓ Data restored from: {latest['name']}")
            
            # 清理临时文件
            if os.path.exists(TEMP_FILE): 
                os.remove(TEMP_FILE)
            
            return True
                
        except Exception as e:
            log(f"Recovery failed: {str(e)}")
            if os.path.exists(TEMP_FILE): 
                os.remove(TEMP_FILE)
            return False

if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("Usage: sync_tool.py <push|pull> <url> <user> <password> <remote_dir> <local_path>")
        sys.exit(1)
    
    run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
