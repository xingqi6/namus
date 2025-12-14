# 阶段1：从官方 Navidrome 镜像中提取二进制文件
FROM deluan/navidrome:latest as builder

# 阶段2：构建去特征化的伪装镜像
FROM alpine:3.19

# 1. 安装系统依赖
# ffmpeg: 音频转码
# python3/pip: 运行备份脚本
# bash/curl: 系统基础工具
RUN apk update && apk add --no-cache \
    bash \
    curl \
    python3 \
    py3-pip \
    tar \
    gzip \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# 2. 配置 Python 虚拟环境 (关键步骤！必须在 pip install 之前)
# 创建虚拟环境，避免 Alpine 的 PEP 668 错误
RUN python3 -m venv /venv
# 将虚拟环境的 bin 目录加入系统 PATH
ENV PATH="/venv/bin:$PATH"

# 3. 安装 Python 依赖
# requests: 用于 WebDAV 连接检测
# huggingface_hub: 用于下载 Dataset 音乐
# webdav4: 用于备份数据
RUN pip install --no-cache-dir huggingface_hub webdav4 requests

# 4. 创建目录结构
# /assets: 伪装后的音乐目录 (原 /music)
# /data/hf_cache: 专门用于存放 HF 下载缓存，防止权限报错
# /assets/.cache: HF 下载临时文件目录
RUN mkdir -p /data/cache /data/hf_cache /assets /assets/.cache /config /.cache /app

# 5. 复制文件
# 将 navidrome 改名为 server_core 以隐藏进程特征
COPY --from=builder /app/navidrome /app/server_core
COPY src/entry.sh /app/entry.sh
COPY src/sync_tool.py /app/sync_tool.py
COPY src/res_loader.py /app/res_loader.py

# 6. 设置权限（关键修复）
# 先修改所有目录的所有者为 1000:1000
# 然后设置正确的权限，确保用户可以读写
RUN chmod +x /app/entry.sh /app/server_core && \
    chown -R 1000:1000 /data /assets /config /venv /.cache /app && \
    chmod -R 755 /data /assets /config && \
    chmod -R 777 /assets/.cache /data/hf_cache

# --- 环境变量配置 (关键伪装与修复) ---
# 强制 Navidrome 读取 /assets 目录
ENV ND_MUSICFOLDER=/assets
# 强制 Navidrome 将数据库存放在 /data
ENV ND_DATAFOLDER=/data
# 日志级别设为 fatal，屏蔽常规日志
ENV ND_LOGLEVEL=fatal
# 【新增】强制静音模式，彻底关闭启动时的 ASCII Logo
ENV ND_QUIET=true
# 清空欢迎信息
ENV ND_UWELCOMEMESSAGE=""
# 【新增】指定 HF 下载缓存路径到我们有权限的目录
ENV HF_HOME=/data/hf_cache
# 【新增】HF 下载临时文件路径
ENV TMPDIR=/assets/.cache

# 使用非 root 用户运行
USER 1000
WORKDIR /app
EXPOSE 4533

# 容器启动入口
ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
