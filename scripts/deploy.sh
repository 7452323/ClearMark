#!/bin/bash
set -e

echo "🐣 ClearMark 部署脚本"
echo "========================"

echo "1. 安装 Python 依赖..."
pip install -r requirements.txt

echo "2. 安装浏览器（用于抖音/小红书）..."
playwright install chromium

echo "3. 验证..."
python -c "import httpx, instaloader; print('✅ 依赖正常')"

echo ""
echo "✅ 部署完成!"
echo "运行: python clearmark.py '链接'"
