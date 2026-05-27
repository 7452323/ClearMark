
```
  ╔══════════════════════════════════════════╗
  ║         🐣 ClearMark v1.0               ║
  ║     全平台去水印解析引擎                  ║
  ╚══════════════════════════════════════════╝
```

自动解析抖音、小红书、Twitter、Instagram 等平台的视频/图文，返回**无水印+最高画质**原文件，支持自动发送到 Telegram。

---

## 📋 功能

| 平台 | 视频 | 图文 | 去水印 | 最高画质 | 模式 |
|------|:----:|:----:|:------:|:--------:|:----:|
| **抖音** | ✅ | ✅ | ✅ | ✅ | 签名算法 + 浏览器回退 |
| **小红书** | ✅ | ✅ | ✅ | ✅ | 浏览器模式 |
| **Twitter/X** | ✅ | ✅ | ✅ | ✅ | GraphQL API |
| **Instagram** | ✅ | ✅ | ✅ | ✅ | Instaloader API |

---

## 🚀 快速开始

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/7452323/ClearMark.git
cd ClearMark

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装浏览器（用于抖音/小红书解析）
playwright install chromium

# 4. 搞定！
```

### 命令行使用

```bash
# 解析抖音（输出无水印链接）
python clearmark.py "https://v.douyin.com/xxxxx/"

# 解析小红书
python clearmark.py "http://xhslink.com/xxxxx"

# 解析Twitter
python clearmark.py "https://x.com/xxx/status/xxxxx"

# 解析Instagram
python clearmark.py "https://www.instagram.com/reel/xxxxx/"
```

### 自动发送到 Telegram

```bash
# 设置 Bot Token
export BOT_TOKEN="123456…abc"
export CHAT_ID="你的ChatID"

# 解析并自动下载发送
python clearmark.py "https://v.douyin.com/xxxxx/"
```

---

## 🤖 接入 Telegram Bot（详细教程）

### 第一步：创建 Bot

1. 打开 Telegram，搜索 **@BotFather**
2. 发送 `/newbot`
3. 输入 bot 名字（如 `ClearMark Bot`）
4. 输入 bot 用户名（如 `clearmark_bot`）
5. BotFather 会返回一个 **Token**，格式如：
   ```
   1234567890:ABCDefghIJKlmnopQRStuvWXyz
   ```
   保存好这个 Token。

### 第二步：获取你的 Chat ID

有两种方式：

**方式A：直接发消息给机器人**
1. 搜索你刚创建的 bot，点 **Start**
2. 发送任意消息
3. 访问以下链接（替换 Token）：
   ```
   https://api.telegram.org/bot<你的Token>/getUpdates
   ```
4. 在返回的 JSON 中找到 `"chat":{"id":123456789}` → 这就是你的 Chat ID

**方式B：创建群聊（多人使用）**
1. 把 bot 拉入群 → 设为管理员
2. 在群里发消息
3. 调用 `getUpdates` 获取群 Chat ID

### 第三步：配置文件

创建 `.env` 文件（或用环境变量）：

```bash
# Telegram 配置
BOT_TOKEN=1234567890:ABCDefghIJKlmnopQRStuvWXyz
CHAT_ID=123456789

# Cookie 存储路径（可选，默认 ./cookies/）
COOKIE_DIR=./cookies
```

### 第四步：运行 Bot 模式

```bash
# 方式1：解析 + 自动下载 + 发送到TG
python clearmark.py "https://v.douyin.com/xxxxx/"
# 环境变量已配好 → 自动发送

# 方式2：强制发送（即使没有BOT_TOKEN环境变量）
python clearmark.py "https://.../" --send
```

---

## 🏠 部署方案

### 方案一：服务器部署（推荐）

**最低配置：** 1核 1G RAM 10G 磁盘

```bash
# Ubuntu/Debian
apt update && apt install -y python3 python3-pip git
pip install -r requirements.txt
playwright install chromium

# CentOS/RHEL
yum install -y python3 python3-pip git
pip3 install -r requirements.txt
python3 -m playwright install chromium

# 运行
python clearmark.py "链接"
```

**作为服务长期运行：**

```bash
# 创建 systemd 服务
cat > /etc/systemd/system/clearmark.service << 'EOF'
[Unit]
Description=ClearMark 去水印服务
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ClearMark
Environment=BOT_TOKEN=你的Token
Environment=CHAT_ID=你的ChatID
ExecStart=/usr/bin/python3 /opt/ClearMark/clearmark.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable clearmark
systemctl start clearmark
```

### 方案二：Docker 部署

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && \
    pip install playwright && \
    playwright install chromium && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "clearmark.py"]
```

```bash
# 构建
docker build -t clearmark .

# 运行
docker run -e BOT_TOKEN=xxx -e CHAT_ID=xxx clearmark
```

### 方案三：GitHub Actions 定时运行

```yaml
# .github/workflows/parse.yml
name: ClearMark Parser
on:
  workflow_dispatch:
    inputs:
      url:
        description: '要解析的链接'
        required: true

jobs:
  parse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: |
          pip install -r requirements.txt
          playwright install chromium
      - run: python clearmark.py "${{ github.event.inputs.url }}"
        env:
          BOT_TOKEN: ${{ secrets.BOT_TOKEN }}
          CHAT_ID: ${{ secrets.CHAT_ID }}
```

### 方案四：VPS + Nginx 反向代理（Web API）

```python
# server.py - Web API 服务器
from fastapi import FastAPI, Query
import subprocess, json

app = FastAPI()

@app.get("/parse")
async def parse(url: str = Query(...)):
    result = subprocess.run(
        ["python", "clearmark.py", url],
        capture_output=True, text=True
    )
    return {"result": result.stdout}
```

```bash
pip install fastapi uvicorn
uvicorn server:app --host 0.0.0.0 --port 8080

# 访问: http://你的IP:8080/parse?url=https://v.douyin.com/xxx/
```

### 方案五：手机 Termux 运行（无服务器）

```bash
# 安装 Termux 后：
pkg install python git
git clone https://github.com/7452323/ClearMark.git
cd ClearMark
pip install -r requirements.txt
pkg install chromium
python clearmark.py "链接"
```

---

## 🔐 Cookie 配置

Twitter 和 Instagram 的受限内容需要 Cookie。

### 获取 Cookie

**方式一：浏览器**
1. 登录 twitter.com / instagram.com
2. F12 → Application → Cookies
3. 复制 `auth_token`（Twitter）或 `sessionid`（Instagram）

**方式二：手机**
1. 登录后安装 Cookie Manager 扩展
2. 导出 Cookie 字符串

### 设置 Cookie（加密存储）

```bash
# Twitter
python cookies/set_cookie.py twitter auth_token=xxx ct0=yyy

# Instagram
python cookies/set_cookie.py instagram sessionid=xxx

# 查看状态
python cookies/set_cookie.py status

# 手动刷新
python cookies/set_cookie.py refresh
```

Cookie 会被 AES-256 加密存储，密钥权限 600，不会提交到 Git。

### 自动刷新

部署后每 6 小时自动续期 Cookie，保证不过期：

```bash
# 手动运行续期
python scripts/refresh_cookies.py

# 或通过 cron 设置
crontab -e
# 添加：0 */6 * * * cd /opt/ClearMark && python scripts/refresh_cookies.py
```

---

## 🏗️ 项目结构

```
ClearMark/
├── clearmark.py              # 主入口
├── requirements.txt          # Python依赖
├── README.md                 # 本文件
├── platforms/
│   ├── __init__.py
│   ├── douyin.py             # 抖音解析器
│   ├── xiaohongshu.py        # 小红书解析器
│   ├── twitter.py            # Twitter解析器
│   ├── twitter_engine.py     # Twitter API引擎
│   ├── instagram.py          # Instagram解析器
│   ├── _douyin_engine.py     # 抖音签名算法引擎
│   └── _errors.py            # 错误类型
├── cookies/
│   ├── secure_manager.py     # Cookie加密管理器
│   ├── set_cookie.py         # Cookie设置工具
│   └── .gitignore            # 排除敏感文件
└── scripts/
    ├── deploy.sh             # 部署脚本
    └── refresh_cookies.py    # Cookie续期脚本
```

## 🔧 排除故障

**Q: 抖音解析失败？**
A: 可能 Cookie 过期了，程序会自动重试浏览器模式。如果还不行，重新分享链接。

**Q: Twitter 提示"推文受限"？**
A: 需要配置 Cookie（见上方 Cookie 配置章节）

**Q: 视频超过 Telegram 50MB 限制？**
A: 程序会自动发送下载链接而非原文件

**Q: 提示 `ModuleNotFoundError`？**
A: 运行 `pip install -r requirements.txt` 安装缺失依赖

**Q: 浏览器模式太慢？**
A: 首次运行需下载 Chromium，之后会缓存。签名算法模式比浏览器快 5-10 倍。

---

## ⚖️ 免责声明

本工具仅用于学习研究，不得用于非法用途。使用本工具需遵守各平台用户协议。Cookie 仅存储于本地，加密保护，不提交到 Git，不传输到第三方。

---

## 📝 更新日志

- v1.0 (2026-05-27) - 首发：支持抖音/小红书/Twitter/Instagram，Cookie加密存储，自动续期，Telegram发送
