#!/usr/bin/env python3
import os, sys, tarfile, requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from webdav4.client import Client

# --- 配置 ---
MAX_BACKUPS = 5
CURRENT_PREFIX = "sys_dat_"
# 包含 navidrome_backup_ 以兼容旧备份
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
        # 301 也是连接成功的一种（说明路径存在但格式不对），予以放行
        return response.status_code not in [401, 403, 404]
    except Exception as e:
        log(f"Connection check failed: {str(e)}")
        return False

def get_client(url, user, password):
    """创建 WebDAV 客户端"""
    return Client(url, auth=(user, password), timeout=30)

def recursive_mkdir(client, remote_path):
    """递归创建远程目录 (修复版)"""
    # 移除首尾斜杠方便处理
    clean_path = remote_path.strip('/')
    if not clean_path:
        return

    parts = clean_path.split('/')
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        try:
            # 这里的 exists 检查如果遇到 301 可能会误报
            # 所以我们直接尝试 mkdir，如果报错且不是"已存在"，则忽略
            client.mkdir(current)
        except:
            # 大多数情况下报错是因为目录已存在，直接忽略
            pass

def run_sync(action, url, user, pwd, remote_dir, local_path):
    """执行同步操作"""
    if not url: 
        log("No WebDAV URL provided, skipping sync.")
        return False
    
    # === 关键修复：URL 处理 ===
    # 确保 WebDAV URL 以 / 结尾 (InfiniCLOUD 必需)
    if not url.endswith('/'):
        url = url + '/'
    
    # === 关键修复：远程目录处理 ===
    # 1. remote_dir (用于拼接文件路径): 确保开头有/，结尾没有/
    if not remote_dir.startswith("/"): 
        remote_dir = "/" + remote_dir
    remote_dir = remote_dir.rstrip('/')
    
    # 2. dir_for_ops (用于目录操作): 确保结尾有/，解决 301 问题
    # 例如: /namus1/
    dir_for_ops = remote_dir + "/"
    
    # 3. relative_path (用于相对路径操作): 开头没/，结尾有/
    # 例如: namus1/
    relative_path = dir_for_ops.lstrip('/')
    
    # 检查连接
    if not check_connection(url, user, pwd):
        log("WebDAV connection failed (Check URL/Auth).")
        return False

    try:
        # 创建客户端
        client = get_client(url, user, pwd)
    except Exception as e:
        log(f"Failed to create WebDAV client: {str(e)}")
        return False

    # ========================================
    # PUSH 操作：备份数据
    # ========================================
    if action == "push":
        # log("Starting backup (PUSH)...") # 保持安静，只在成功时说话
        
        # 确保远程目录存在
        # 使用 recursive_mkdir 自动处理每一级
        recursive_mkdir(client, remote_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{CURRENT_PREFIX}{timestamp}.tar.gz"
        # 上传文件路径不需要末尾斜杠
        remote_full_path = f"{remote_dir}/{filename}"

        try:
            # 1. 打包本地数据
            with tarfile.open(TEMP_FILE, "w:gz") as tar:
                count = 0
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    if "hf_cache" in dirs: dirs.remove("hf_cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
                        count += 1
            
            if count == 0:
                if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
                return False
            
            # 2. 上传到 WebDAV
            client.upload_file(TEMP_FILE, remote_full_path, overwrite=True)
            log(f"✓ Backup uploaded: {filename}")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

            # 3. 清理旧备份 (关键修复：使用带斜杠的目录路径)
            try:
                # 使用 relative_path (namus1/) 列出文件，避免 301
                if client.exists(relative_path):
                    files = client.ls(relative_path, detail=True)
                    
                    # 筛选所有备份文件
                    backups = [
                        f for f in files 
                        if f["type"] == "file" 
                        and f["name"].endswith(".tar.gz")
                        and any(f["name"].startswith(prefix) for prefix in TARGET_PREFIXES)
                    ]
                    
                    backups.sort(key=lambda x: x["name"], reverse=True)
                    total = len(backups)
                    
                    if total > MAX_BACKUPS:
                        delete_list = backups[MAX_BACKUPS:]
                        log(f"Cleanup: Found {total} files. Deleting {len(delete_list)} old backups...")
                        
                        for item in delete_list:
                            try:
                                # 删除时使用完整路径
                                delete_path = f"{remote_dir}/{item['name']}"
                                client.remove(delete_path)
                                log(f"Deleted: {item['name']}")
                            except Exception as e:
                                log(f"Del error ({item['name']}): {str(e)}")
            except Exception as e:
                # 即使清理失败也不影响备份成功
                log(f"Cleanup error: {str(e)}")

        except Exception as e:
            log(f"Backup failed: {str(e)}")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
            return False
        
        return True

    # ========================================
    # PULL 操作：恢复数据
    # ========================================
    elif action == "pull":
        log("Starting data recovery...")
        
        try:
            # 检查目录是否存在 (使用带斜杠的路径)
            if not client.exists(relative_path):
                log("Remote directory not found. Starting fresh.")
                return False
            
            files = client.ls(relative_path, detail=True)
            
            backups = [
                f for f in files 
                if f["type"] == "file" 
                and f["name"].endswith(".tar.gz")
                and any(f["name"].startswith(prefix) for prefix in TARGET_PREFIXES)
            ]
            
            if not backups:
                log("No backup files found. Starting fresh.")
                return False

            backups.sort(key=lambda x: x["name"], reverse=True)
            latest = backups[0]
            
            log(f"Restoring from: {latest['name']}")
            
            # 下载
            download_path = f"{remote_dir}/{latest['name']}"
            client.download_file(download_path, TEMP_FILE)
            
            # 解压
            with tarfile.open(TEMP_FILE, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(local_path))
            
            log(f"✓ Data restored successfully.")
            
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
            return True
                
        except Exception as e:
            log(f"Recovery failed: {str(e)}")
            if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
            return False

if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("Usage: sync_tool.py <push|pull> <url> <user> <password> <remote_dir> <local_path>")
        sys.exit(1)
    
    run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
