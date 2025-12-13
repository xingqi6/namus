#!/usr/bin/env python3
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time
import json
from datetime import datetime

def log(msg):
    print(f"[RESOURCE] {msg}")

def check_and_load(repo_id, token, target_dir, force=False):
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
    # repo token dir interval force
    while True:
        try:
            check_and_load(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[5].lower() == "true")
        except:
            pass
        time.sleep(int(sys.argv[4]))
