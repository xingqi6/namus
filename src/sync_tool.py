#!/usr/bin/env python3
import os, sys, tarfile, requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
CURRENT_PREFIX = "sys_dat_"
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
    
    # === 关键修复：路径处理 ===
    # 1. 标准化 base URL（移除尾部斜杠）
    url = url.rstrip('/')
    
    # 2. 标准化远程目录路径
    if not remote_dir.startswith("/"): 
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')
    
    # 3. 计算相对路径（用于 ls/exists/remove/download）
    relative_path = remote_dir.lstrip('/')
    
    # 调试日志
    log(f"WebDAV Base URL: {url}")
    log(f"Remote Directory (absolute): {remote_dir}")
    log(f"Remote Directory (relative): {relative_path}")

    # 检查连接（使用带斜杠的 URL）
    if not check_connection(url + "/", user, pwd):
        log("WebDAV connection failed or not configured.")
        return False

    try:
        # 创建客户端（必须以斜杠结尾）
        client = get_client(url + "/", user, pwd)
    except Exception as e:
        log(f"Failed to create WebDAV client: {str(e)}")
        return False

    # ========================================
    # PUSH 操作：备份数据
    # ========================================
    if action == "push":
        log("Starting backup (PUSH)...")
        
        # 确保远程目录存在（使用相对路径检查）
        try:
            if not client.exists(relative_path):
                log(f"Creating remote directory: {relative_path}")
                recursive_mkdir(client, remote_dir)
        except Exception as e:
            log(f"Directory check/create info: {str(e)}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{CURRENT_PREFIX}{timestamp}.tar.gz"
        # 上传时使用绝对路径
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
                return False
            
            # 2. 上传到 WebDAV（使用绝对路径）
            log(f"Uploading backup ({count} files) to: {remote_full_path}")
            try:
                client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
                log(f"✓ Backup uploaded: {filename}")
            except Exception as upload_err:
                log(f"Upload failed: {str(upload_err)}")
                # 尝试确保目录存在后重试
                try:
                    recursive_mkdir(client, remote_dir)
                    client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
                    log(f"✓ Backup uploaded (retry): {filename}")
                except Exception as retry_err:
                    log(f"Upload retry failed: {str(retry_err)}")
                    if os.path.exists(TEMP_FILE): 
                        os.remove(TEMP_FILE)
                    return False
            
            # 清理临时文件
            if os.path.exists(TEMP_FILE): 
                os.remove(TEMP_FILE)

            # 3. 清理旧备份（使用相对路径）
            log("Checking for old backups to clean up...")
            try:
                # 使用相对路径列出文件
                if not client.exists(relative_path):
                    log(f"Remote directory not found, skipping cleanup.")
                    return True
                
                log(f"Listing files in: {relative_path}")
                files = client.ls(relative_path, detail=True)
                
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
                            # 删除时使用相对路径
                            delete_path = f"{relative_path}/{item['name']}"
                            log(f"Deleting: {delete_path}")
                            client.remove(delete_path)
                            log(f"✓ Deleted: {item['name']}")
                        except Exception as e:
                            log(f"✗ Failed to delete {item['name']}: {str(e)}")
                else:
                    log(f"No cleanup needed (keeping {total}/{MAX_BACKUPS}).")
                    
            except Exception as e:
                log(f"Cleanup error: {str(e)}")
                # 清理错误不影响备份成功状态

        except Exception as e:
            log(f"Backup failed: {str(e)}")
            if os.path.exists(TEMP_FILE): 
                os.remove(TEMP_FILE)
            return False
        
        return True

    # ========================================
    # PULL 操作：恢复数据
    # ========================================
    elif action == "pull":
        log("Starting data recovery (PULL)...")
        
        try:
            # 使用相对路径检查目录
            if not client.exists(relative_path):
                log("Remote backup directory does not exist. Starting fresh.")
                return False
            
            log(f"Listing backups in: {relative_path}")
            files = client.ls(relative_path, detail=True)
            
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
            
            # 下载备份文件（使用相对路径）
            download_path = f"{relative_path}/{latest['name']}"
            log(f"Download path: {download_path}")
            client.download_file(download_path, TEMP_FILE)
            
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
