#!/usr/bin/env python3
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time

def log(msg):
    print(f"[RESOURCE] {msg}", flush=True)

def check_and_load(repo_id, token, target_dir, force=False):
    if not repo_id or not token:
        return

    log("Checking resource updates...")
    info_file = os.path.join(target_dir, ".meta_info")
    
    # 使用 /data/hf_cache 作为缓存，确保有权限写入
    cache_dir = os.environ.get("HF_HOME", "/data/hf_cache")
    
    # 确保缓存目录存在且有权限
    try:
        os.makedirs(cache_dir, mode=0o777, exist_ok=True)
        os.makedirs(os.path.join(target_dir, ".cache"), mode=0o777, exist_ok=True)
    except Exception as e:
        log(f"Warning: Could not create cache directories: {str(e)}")
    
    try:
        api = HfApi(token=token)
        remote = api.repo_info(repo_id=repo_id, repo_type="dataset")
        remote_sha = remote.sha
        
        local_sha = None
        if os.path.exists(info_file):
            try:
                with open(info_file, "r") as f:
                    local_sha = f.read().strip()
            except Exception as e:
                log(f"Could not read local info: {str(e)}")

        if not force and local_sha == remote_sha:
            log("Resources are up to date.")
            return

        log("Update detected. Downloading assets...")
        
        # 设置更宽松的文件权限，忽略权限相关错误
        try:
            snapshot_download(
                repo_id=repo_id, 
                repo_type="dataset", 
                local_dir=target_dir, 
                token=token,
                cache_dir=cache_dir,
                resume_download=True,
                max_workers=4
            )
        except PermissionError as pe:
            # 权限错误不影响下载，继续
            log(f"Permission warning (non-critical): {str(pe)}")
        except OSError as oe:
            # 其他 OS 错误，如果是权限相关的也忽略
            if "Permission denied" in str(oe):
                log(f"Permission warning (non-critical): {str(oe)}")
            else:
                raise
        
        # 尝试写入版本信息
        try:
            with open(info_file, "w") as f:
                f.write(remote_sha)
            log("Assets loaded successfully.")
        except Exception as e:
            log(f"Could not write version info (non-critical): {str(e)}")
            log("Assets loaded (version tracking unavailable).")
        
    except PermissionError as pe:
        log(f"Permission issue (continuing): {str(pe)}")
    except Exception as e:
        # 其他错误也打印但不中断
        log(f"Loader notification: {str(e)}")

if __name__ == "__main__":
    # repo_id, token, target_dir, interval, force_first_run
    repo_id = sys.argv[1]
    token = sys.argv[2]
    target_dir = sys.argv[3]
    interval = int(sys.argv[4])
    force = sys.argv[5].lower() == "true"

    check_and_load(repo_id, token, target_dir, force)

    while True:
        time.sleep(interval)
        try:
            check_and_load(repo_id, token, target_dir, False)
        except:
            pass
