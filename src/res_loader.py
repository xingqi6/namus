#!/usr/bin/env python3
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time
from datetime import datetime

def log(msg):
    print(f"[RESOURCE] {msg}")

def check_and_load(repo_id, token, target_dir, force=False):
    if not repo_id or not token:
        return

    log("Checking resource updates...")
    info_file = os.path.join(target_dir, ".meta_info")
    
    try:
        api = HfApi(token=token)
        remote = api.repo_info(repo_id=repo_id, repo_type="dataset")
        remote_sha = remote.sha
        
        local_sha = None
        if os.path.exists(info_file):
            with open(info_file, "r") as f:
                local_sha = f.read().strip()

        if not force and local_sha == remote_sha:
            log("Resources are up to date.")
            return

        log("Update detected. Downloading assets...")
        snapshot_download(repo_id=repo_id, repo_type="dataset", local_dir=target_dir, token=token)
        
        with open(info_file, "w") as f:
            f.write(remote_sha)
        log("Assets loaded successfully.")
        
    except Exception as e:
        log(f"Loader exception: {str(e)}")

if __name__ == "__main__":
    # 参数：repo_id, token, target_dir, interval, force_first_run
    repo_id = sys.argv[1]
    token = sys.argv[2]
    target_dir = sys.argv[3]
    interval = int(sys.argv[4])
    force = sys.argv[5].lower() == "true"

    # 首次运行
    check_and_load(repo_id, token, target_dir, force)

    # 循环检测
    while True:
        time.sleep(interval)
        try:
            check_and_load(repo_id, token, target_dir, False)
        except:
            pass
