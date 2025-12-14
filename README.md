# Namus - 私有音乐流媒体服务

基于 Navidrome 的私有音乐服务器，支持自动备份、远程存储和无缝数据恢复。

## ✨ 特性

- 🎵 **完整音乐流媒体服务** - 支持多种音频格式，实时转码
- ☁️ **自动 WebDAV 备份** - 定时自动备份数据到远程存储
- 🔄 **智能数据恢复** - 容器重启后自动从 WebDAV 恢复数据
- 📦 **Hugging Face 集成** - 从 HF Dataset 自动加载音乐资源
- 🔒 **版本保留策略** - 自动保留最近 5 个备份，节省存储空间
- 🚀 **轻量化部署** - 基于 Alpine Linux，镜像体积小

## 📋 前置要求

- Docker 环境
- WebDAV 服务器（可选，用于数据备份）
- Hugging Face 账号和 Token（可选，用于音乐资源加载）

## 🚀 快速开始

### 1. 使用 Hugging Face Spaces 部署

在 Hugging Face Spaces 创建新 Space：
- **Space type**: Docker
- **Visibility**: Private（建议）

配置以下环境变量：

```bash
# WebDAV 备份配置（必需）
WEBDAV_URL=https://your-webdav-server.com/dav
WEBDAV_USER=your_username
WEBDAV_PASSWORD=your_password
WEBDAV_REMOTE_PATH=/navidrome_backups

# 备份间隔（可选，默认 3600 秒 = 1 小时）
SYNC_INTERVAL=3600

# Hugging Face 音乐资源（可选）
DATASET_MUSIC_NAME=your-username/your-music-dataset
MUSIC_TOKEN=your_hf_token

# 音乐目录（可选，默认 /assets）
MUSIC_DIR=/assets
```

### 2. 使用 Docker 本地部署

```bash
# 拉取镜像
docker pull ghcr.io/your-username/namus:v6

# 运行容器
docker run -d \
  --name namus \
  -p 4533:4533 \
  -e WEBDAV_URL="https://your-webdav-server.com/dav" \
  -e WEBDAV_USER="your_username" \
  -e WEBDAV_PASSWORD="your_password" \
  -e WEBDAV_REMOTE_PATH="/navidrome_backups" \
  -e SYNC_INTERVAL="3600" \
  -v /path/to/music:/assets \
  -v /path/to/data:/data \
  ghcr.io/your-username/namus:v6
```

### 3. 访问服务

打开浏览器访问：`http://localhost:4533`

首次访问时创建管理员账号，之后就可以开始使用了。

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必需 |
|--------|------|--------|------|
| `WEBDAV_URL` | WebDAV 服务器地址 | - | 是（备份功能） |
| `WEBDAV_USER` | WebDAV 用户名 | - | 是（备份功能） |
| `WEBDAV_PASSWORD` | WebDAV 密码 | - | 是（备份功能） |
| `WEBDAV_REMOTE_PATH` | 远程备份目录 | `/navidrome_backups` | 否 |
| `SYNC_INTERVAL` | 备份间隔（秒） | `3600` (1小时) | 否 |
| `DATASET_MUSIC_NAME` | HF Dataset 仓库名 | - | 否 |
| `MUSIC_TOKEN` | Hugging Face Token | - | 否（使用 Dataset 时必需） |
| `MUSIC_DIR` | 音乐文件目录 | `/assets` | 否 |

### 备份机制

#### 自动备份流程

1. **启动时恢复** - 容器启动时自动从 WebDAV 拉取最新备份
2. **定时备份** - 按 `SYNC_INTERVAL` 设定的间隔自动备份数据
3. **智能清理** - 自动保留最近 5 个备份文件，删除更早的备份

#### 备份内容

- 用户账号和密码
- 播放列表
- 收藏和评分
- 扫描历史
- 其他配置数据

**不会备份：**
- 音乐文件本身（应通过 Dataset 或挂载卷管理）
- 缓存数据
- 临时文件

#### 备份文件命名

```
sys_dat_YYYYMMDD_HHMMSS.tar.gz
例如：sys_dat_20241215_143022.tar.gz
```

### WebDAV 服务器推荐

- **坚果云** - 国内用户友好，提供 WebDAV 支持
- **Nextcloud** - 自建 WebDAV 服务
- **Synology NAS** - 群晖 NAS 内置 WebDAV
- **4shared** - 免费 WebDAV 服务
- **Box.com** - 企业级云存储

## 📝 使用场景

### 场景 1: Hugging Face Spaces 部署

最适合没有固定服务器的用户：

1. 音乐存储在 HF Private Dataset
2. 用户数据自动备份到 WebDAV
3. Space 重启后自动恢复账号和播放列表
4. 完全免费（HF Spaces 免费额度）

### 场景 2: 本地 Docker 部署

适合有 NAS 或服务器的用户：

1. 音乐文件挂载到本地目录
2. 数据备份到云端 WebDAV（异地容灾）
3. 服务器故障时可快速恢复

### 场景 3: 混合部署

1. 主服务器运行容器
2. 音乐分散在 Dataset 和本地存储
3. 数据多重备份（本地 + WebDAV）

## 🛠️ 高级配置

### 自定义备份保留数量

修改 `src/sync_tool.py` 中的配置：

```python
MAX_BACKUPS = 10  # 保留最近 10 个备份
```

### 修改日志级别

```bash
# 在 Dockerfile 或环境变量中设置
ENV ND_LOGLEVEL=info  # 可选: fatal, error, warn, info, debug
```

### 手动触发备份

进入容器执行：

```bash
docker exec -it namus /bin/bash
python /app/sync_tool.py push "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$WEBDAV_REMOTE_PATH" "/data"
```

### 手动恢复数据

```bash
docker exec -it namus /bin/bash
python /app/sync_tool.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "$WEBDAV_REMOTE_PATH" "/data"
```

## 🔍 故障排查

### 1. 备份没有自动执行

检查日志：
```bash
docker logs namus | grep "bg_task"
```

确认 WebDAV 配置是否正确：
```bash
docker exec namus env | grep WEBDAV
```

### 2. WebDAV 连接失败

测试连接：
```bash
docker exec namus python /app/sync_tool.py pull "$WEBDAV_URL" "$WEBDAV_USER" "$WEBDAV_PASSWORD" "/test" "/data"
```

检查防火墙和 WebDAV 服务器状态。

### 3. 数据没有恢复

查看启动日志：
```bash
docker logs namus | grep "INIT"
```

确认远程备份目录中有备份文件。

### 4. 旧备份没有删除

检查清理日志：
```bash
docker logs namus | grep "Cleanup"
```

手动列出远程文件：
```bash
# 使用 WebDAV 客户端检查远程目录
```

## 📊 系统架构

```
┌─────────────────────────────────────────┐
│         Docker Container                │
├─────────────────────────────────────────┤
│  ┌──────────────────────────────────┐  │
│  │  entry.sh (启动脚本)              │  │
│  └──────────────────────────────────┘  │
│           │                              │
│           ├─→ pull (启动时恢复数据)      │
│           │                              │
│           ├─→ res_loader.py              │
│           │   (从 HF Dataset 加载音乐)   │
│           │                              │
│           ├─→ backup_daemon              │
│           │   (后台定时备份)              │
│           │                              │
│           └─→ server_core                │
│               (Navidrome 核心服务)        │
│                                           │
│  ┌──────────────────────────────────┐  │
│  │  sync_tool.py                     │  │
│  │  - push: 打包并上传数据           │  │
│  │  - pull: 下载并解压数据           │  │
│  │  - cleanup: 清理旧备份            │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │                    │
         │ push               │ pull
         ↓                    ↑
┌─────────────────────────────────────────┐
│       WebDAV 服务器                      │
│  /navidrome_backups/                    │
│    ├─ sys_dat_20241215_120000.tar.gz   │
│    ├─ sys_dat_20241215_130000.tar.gz   │
│    ├─ sys_dat_20241215_140000.tar.gz   │
│    ├─ sys_dat_20241215_150000.tar.gz   │
│    └─ sys_dat_20241215_160000.tar.gz   │
│       (自动保留最新 5 个)                │
└─────────────────────────────────────────┘
```

## 🔐 安全建议

1. **使用 HTTPS** - WebDAV 连接务必使用 HTTPS
2. **强密码** - 设置强 WebDAV 密码
3. **Private Space** - HF Spaces 设置为 Private
4. **定期更新** - 及时更新镜像版本
5. **备份加密** - 敏感数据建议加密后备份

## 📄 开源协议

本项目基于 MIT 协议开源。

## 🙏 致谢

- [Navidrome](https://www.navidrome.org/) - 优秀的音乐流媒体服务器
- [Hugging Face](https://huggingface.co/) - 提供免费的 Spaces 部署平台

## 📮 反馈与支持

如有问题或建议，请提交 Issue 或 Pull Request。

---

**注意**: 本项目仅供学习交流使用，请遵守相关法律法规，尊重音乐版权。
