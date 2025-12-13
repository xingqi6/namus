#!/usr/bin/env python3
import os
import sys
import tarfile
from datetime import datetime
from webdav4.client import Client

def log(msg):
    print(f"[SYSTEM] {msg}")

def get_client(url, user, password):
    options = {}
    if user and password:
        options = {"auth": (user, password)}
    return Client(url, **options)

def extract_tar(tar_file, dest_dir):
    try:
        with tarfile.open(tar_file, "r:gz") as tar:
            # 这里的逻辑假设打包时包含路径结构，直接解压到目标父目录
            tar.extractall(path=os.path.dirname(dest_dir))
        return True
    except Exception:
        return False

def run_sync(action, url, user, pwd, remote_path, local_path):
    if not url:
        return

    client = get_client(url, user, pwd)
    
    if action == "pull":
        temp_file = "/tmp/data_sync.tmp"
        log("Initializing data retrieval...")
        try:
            if not client.exists(remote_path):
                log("Remote data not found. Starting fresh.")
                return
            client.download_file(remote_path, temp_file)
            extract_tar(temp_file, local_path)
            log("Data synchronization complete.")
            if os.path.exists(temp_file): os.remove(temp_file)
        except Exception as e:
            log(f"Sync error: {str(e)}")

    elif action == "push":
        temp_file = "/tmp/data_package.tmp"
        try:
            # 排除 cache 目录进行打包
            with tarfile.open(temp_file, "w:gz") as tar:
                for root, dirs, files in os.walk(local_path):
                    if "cache" in dirs: dirs.remove("cache")
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                        tar.add(full_path, arcname=rel_path)
            
            # 确保存储目录存在
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and not client.exists(remote_dir):
                client.mkdir(remote_dir)
            
            client.upload_file(temp_file, remote_path, overwrite=True)
            log(f"Data upload success. Timestamp: {datetime.now().strftime('%H:%M:%S')}")
            if os.path.exists(temp_file): os.remove(temp_file)
        except Exception as e:
            log(f"Upload failed: {str(e)}")

if __name__ == "__main__":
    # 参数顺序：action, url, user, pwd, remote_path, local_path
    if len(sys.argv) >= 7:
        run_sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
