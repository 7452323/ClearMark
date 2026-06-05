# 🐣 ClearMark v2

全平台去水印解析引擎，基于 **ParseHub** 引擎，一行代码解析 17+ 平台（抖音、小红书、Twitter、TikTok、YouTube、Bilibili、快手、微博等）。

自动选择最高画质无水印原文件，支持自动发送到 Telegram。

---

## 快速开始

### 安装

```bash
# 需要 Python >= 3.12
pip install -r requirements.txt
```

### 命令行使用

```bash
# 解析链接（输出无水印下载链接）
python clearmark.py "https://v.douyin.com/xxxxx/"
python clearmark.py "http://xhslink.com/xxxxx"
```

### 自动发送到 Telegram

```bash
export BOT_TOKEN="1234567890:ABCdef..."
export CHAT_ID="你的ChatID"

# 解析 + 下载 + 自动发送
python clearmark.py "https://v.douyin.com/xxxxx/"
```

---

## Cookie 配置

`data/config/platform_config.yaml`：

```yaml
platforms:
  douyin:
    cookies:
      - "your_cookie_string"
```

---

## 依赖

- Python >= 3.12
- parsehub >= 2.0.17
- httpx >= 0.27.0, < 0.28

---

## 结构

```
ClearMark/
├── clearmark.py                       # 主入口（83行）
├── data/config/platform_config.yaml  # Cookie配置
├── requirements.txt                  # Python依赖
└── README.md                         # 本文件
```

---

## 声明

本工具仅用于学习研究，不得用于非法用途。
