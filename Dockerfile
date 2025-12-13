# 阶段1：从官方镜像提取文件
FROM deluan/navidrome as builder

# 阶段2：构建我们自己的伪装镜像
FROM alpine:3.19

# 安装必要依赖
RUN apk update && apk add --no-cache \
    bash \
    curl \
    python3 \
    py3-pip \
    tar \
    gzip \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# 环境配置
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub webdav4

# 目录结构
RUN mkdir -p /data/cache /assets /config /.cache /app

# 关键步骤：从官方镜像复制 Navidrome 但改名为 server_core
COPY --from=builder /app/navidrome /app/server_core

# 复制脚本
COPY src/entry.sh /app/entry.sh
COPY src/core_sync.py /app/core_sync.py
COPY src/res_loader.py /app/res_loader.py

# 权限设置
RUN chmod +x /app/entry.sh /app/server_core && \
    chown -R 1000:1000 /data /assets /config /venv /.cache /app

# --- 欺骗 Navidrome 的配置 ---
# Navidrome 默认去读 /music，我们告诉它去读 /assets
ENV ND_MUSICFOLDER=/assets
# 告诉它数据在 /data
ENV ND_DATAFOLDER=/data
# 关闭一些可能暴露特征的日志（可选）
ENV ND_LOGLEVEL=error

USER 1000
WORKDIR /app
EXPOSE 4533

ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
