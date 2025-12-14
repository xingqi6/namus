# 阶段1：从官方 Navidrome 镜像中提取二进制文件
FROM deluan/navidrome:latest as builder

# 阶段2：构建去特征化的伪装镜像
FROM alpine:3.19

# 1. 安装系统依赖
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
# 创建虚拟环境
RUN python3 -m venv /venv
# 将虚拟环境的 bin 目录加入系统 PATH
# 这样后续的 pip 和 python 命令都会自动使用虚拟环境，避开 PEP 668 错误
ENV PATH="/venv/bin:$PATH"

# 3. 安装 Python 依赖 (现在可以正常安装了)
# 增加了 requests 用于调试连接
RUN pip install --no-cache-dir huggingface_hub webdav4 requests

# 4. 创建目录结构
RUN mkdir -p /data/cache /data/hf_cache /assets /config /.cache /app

# 5. 复制文件
COPY --from=builder /app/navidrome /app/server_core
COPY src/entry.sh /app/entry.sh
COPY src/sync_tool.py /app/sync_tool.py
COPY src/res_loader.py /app/res_loader.py

# 6. 设置权限
RUN chmod +x /app/entry.sh /app/server_core && \
    chown -R 1000:1000 /data /assets /config /venv /.cache /app

# 7. 环境变量伪装
ENV ND_MUSICFOLDER=/assets
ENV ND_DATAFOLDER=/data
ENV ND_LOGLEVEL=fatal
ENV ND_UWELCOMEMESSAGE=""
ENV HF_HOME=/data/hf_cache

USER 1000
WORKDIR /app
EXPOSE 4533

ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
