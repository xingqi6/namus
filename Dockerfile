# 阶段1：获取原始文件
FROM deluan/navidrome as builder

# 阶段2：构建伪装镜像
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

# 从官方镜像把 binary 偷过来，并改名！
COPY --from=builder /app/navidrome /app/server_core

# 复制我们的脚本
COPY src/entry.sh /app/entry.sh
COPY src/core_sync.py /app/core_sync.py
COPY src/res_loader.py /app/res_loader.py

# 权限与清理
RUN chmod +x /app/entry.sh /app/server_core && \
    chown -R 1000:1000 /data /assets /config /venv /.cache /app

# 环境变量映射 (欺骗 Navidrome 读取我们自定义目录)
# Navidrome 默认读 /music，我们改成 generic 的 /assets
ENV ND_MUSICFOLDER=/assets
ENV ND_DATAFOLDER=/data
# 甚至可以修改 Web 界面标题 (如果支持)
ENV ND_UWELCOMEMESSAGE="Welcome to Service"

USER 1000
WORKDIR /app
EXPOSE 4533

ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
