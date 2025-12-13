# 阶段1：从官方 Navidrome 镜像中提取二进制文件
FROM deluan/navidrome:latest as builder

# 阶段2：构建去特征化的伪装镜像
FROM alpine:3.19

# 安装运行所需的依赖
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

# 配置 Python 虚拟环境
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
# 安装备份脚本需要的库 (huggingface_hub用于下音乐, webdav4用于备份数据)
RUN pip install --no-cache-dir huggingface_hub webdav4

# 创建目录结构
# /assets: 伪装后的音乐目录 (原 /music)
# /data: 数据库目录
# /app: 应用程序目录
RUN mkdir -p /data/cache /assets /config /.cache /app

# --- 关键伪装步骤 ---
# 从官方镜像把 navidrome 二进制文件复制过来，并重命名为 server_core
COPY --from=builder /app/navidrome /app/server_core

# 复制 Python 脚本和启动脚本
COPY src/entry.sh /app/entry.sh
COPY src/sync_tool.py /app/sync_tool.py
COPY src/res_loader.py /app/res_loader.py

# 设置权限
# 赋予脚本执行权限，并修正所有目录的所有者为 1000 (非 root 用户)
RUN chmod +x /app/entry.sh /app/server_core && \
    chown -R 1000:1000 /data /assets /config /venv /.cache /app

# --- 环境变量配置 (用于欺骗程序) ---
# 强制 Navidrome 读取 /assets 目录作为音乐库
ENV ND_MUSICFOLDER=/assets
# 强制 Navidrome 将数据库存放在 /data
ENV ND_DATAFOLDER=/data
# 设置日志级别为 error，隐藏启动时的 ASCII Logo 和详细日志
ENV ND_LOGLEVEL=error
# 清空欢迎信息
ENV ND_UWELCOMEMESSAGE=""

# 使用非 root 用户运行
USER 1000
WORKDIR /app
EXPOSE 4533

# 容器启动入口：指向我们的伪装脚本
ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
