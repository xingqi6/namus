# 阶段1：提取
FROM deluan/navidrome:latest as builder

# 阶段2：构建
FROM alpine:3.19

# 安装依赖
RUN apk update && apk add --no-cache \
    bash \
    curl \
    python3 \
    py3-pip \
    tar \
    gzip \
    ffmpeg \
    && rm -rf /var/cache/apk/*
RUN pip install --no-cache-dir huggingface_hub webdav4 requests

# 环境配置
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub webdav4

# 目录结构
# 增加 /data/hf_cache 用于解决下载权限问题
RUN mkdir -p /data/cache /data/hf_cache /assets /config /.cache /app

# 复制程序
COPY --from=builder /app/navidrome /app/server_core
COPY src/entry.sh /app/entry.sh
COPY src/sync_tool.py /app/sync_tool.py
COPY src/res_loader.py /app/res_loader.py

# 权限设置
RUN chmod +x /app/entry.sh /app/server_core && \
    chown -R 1000:1000 /data /assets /config /venv /.cache /app

# --- 环境变量伪装 ---
ENV ND_MUSICFOLDER=/assets
ENV ND_DATAFOLDER=/data
# 改为 fatal 级别，彻底禁止输出 Logo 和普通日志
ENV ND_LOGLEVEL=fatal 
ENV ND_UWELCOMEMESSAGE=""
# 指定 HuggingFace 下载缓存目录到我们可以写入的地方
ENV HF_HOME=/data/hf_cache

USER 1000
WORKDIR /app
EXPOSE 4533

ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
