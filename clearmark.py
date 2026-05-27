#!/usr/bin/env python3
"""
🐣 ClearMark - 全平台去水印解析引擎
支持: 抖音 / 小红书 / Twitter / Instagram
自动下载并发送到 Telegram
"""
import asyncio, json, os, re, sys, time, importlib, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('clearmark')

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / 'platforms'))

# ─── 平台路由 ───────────────────────────────────────────

ROUTES = {
    'douyin':     [r'douyin\.com', r'iesdouyin', r'v\.douyin'],
    'xiaohongshu': [r'xiaohongshu\.com', r'xhslink\.com'],
    'twitter':    [r'twitter\.com', r'x\.com/'],
    'instagram':  [r'instagram\.com'],
    'tiktok':     [r'tiktok\.com'],
    'bilibili':   [r'bilibili\.com', r'b23\.tv'],
    'kuaishou':   [r'kuaishou\.com'],
    'weibo':      [r'weibo\.com', r'weibo\.cn'],
}


def detect(text: str) -> tuple | None:
    """检测平台，返回 (平台名, URL)"""
    for platform, patterns in ROUTES.items():
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                start = max(0, m.start() - 50)
                url_m = re.search(r'https?://[^\s<>"\']+', text[start:])
                if url_m:
                    return platform, url_m.group(0).rstrip('/?&')
    return None


# ─── Telegram 发送 ──────────────────────────────────────

class TelegramBot:
    """Telegram Bot 集成"""
    
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get('BOT_TOKEN', '')
        self.chat_id = chat_id or os.environ.get('CHAT_ID', '')
    
    def _api_url(self, method: str) -> str:
        return f'https://api.telegram.org/bot{self.token}/{method}'
    
    async def send_text(self, text: str) -> bool:
        """发送文字消息"""
        if not self.token: return False
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(self._api_url('sendMessage'),
                data={'chat_id': self.chat_id, 'text': text, 'parse_mode': 'Markdown'})
            return r.json().get('ok', False)
    
    async def download_and_send(self, url: str, caption: str = '',
                                  extra_headers: dict = None) -> bool:
        """下载文件并发送到Telegram"""
        if not self.token: return False
        import httpx
        
        ext = '.mp4' if 'video' in url.lower() else '.jpg'
        path = f'/tmp/clearmark_{int(time.time())}{ext}'
        
        headers = {'User-Agent': 'Mozilla/5.0', **(extra_headers or {})}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            r = await c.get(url, headers=headers)
            if r.status_code != 200:
                log.error(f"下载失败: {r.status_code}")
                return False
            with open(path, 'wb') as f:
                f.write(r.content)
        
        size_mb = os.path.getsize(path) / 1024 / 1024
        if size_mb > 50:
            log.warning(f"视频 {size_mb:.0f}MB 超过TG限制(50MB)，仅发送链接")
            await self.send_text(f"📎 {caption}\n{url}")
            os.remove(path)
            return True
        
        is_video = ext == '.mp4'
        endpoint = 'sendVideo' if is_video else 'sendPhoto'
        
        async with httpx.AsyncClient(timeout=60) as c:
            with open(path, 'rb') as f:
                r = await c.post(self._api_url(endpoint),
                    data={'chat_id': self.chat_id, 'caption': caption[:200]},
                    files={'video' if is_video else 'photo': f})
        
        os.remove(path)
        return r.json().get('ok', False)


# ─── 主入口 ─────────────────────────────────────────────

def import_parser(platform: str):
    """动态导入平台解析器"""
    mod = importlib.import_module(platform)
    cls_name = f'{platform.capitalize()}Parser' if platform != 'xiaohongshu' else 'XiaohongshuParser'
    return getattr(mod, cls_name)()


async def main():
    if len(sys.argv) < 2:
        print("🐣 ClearMark v1.0 - 全平台去水印")
        print()
        print("用法:")
        print("  python clearmark.py '<链接或文本>'")
        print("  python clearmark.py '<链接>' --send   # 自动发送到Telegram")
        print()
        print("支持平台:", ', '.join(ROUTES.keys()))
        print()
        print("环境变量 (用于Telegram):")
        print("  BOT_TOKEN=你的机器人Token")
        print("  CHAT_ID=接收消息的ChatID")
        sys.exit(1)
    
    text = ' '.join(sys.argv[1:])
    auto_send = '--send' in sys.argv
    
    detected = detect(text)
    if not detected:
        log.error("❌ 未识别到支持的平台链接")
        sys.exit(1)
    
    platform, url = detected
    log.info(f"🔍 {platform.upper()} | {url}")
    
    parser = import_parser(platform)
    result = await parser.parse(url)
    
    if not result.get('success'):
        log.error(f"❌ 解析失败: {result.get('error', '未知错误')[:200]}")
        sys.exit(1)
    
    log.info(f"📝 {result.get('title', '(无标题)')}")
    
    if auto_send or 'BOT_TOKEN' in os.environ:
        bot = TelegramBot()
        caption = f"{result.get('title', '')[:100]}\n🐣 ClearMark"
        
        if result.get('video_url'):
            log.info("📥 下载并发送视频...")
            ok = await bot.download_and_send(result['video_url'], caption,
                {'Referer': f'https://www.{platform}.com/'})
            log.info("✅ 已发送到Telegram" if ok else "❌ 发送失败")
        
        if result.get('images'):
            for i, img_url in enumerate(result['images'][:5]):
                log.info(f"📥 发送图片 {i+1}...")
                await bot.download_and_send(img_url, caption)
    else:
        if result.get('video_url'): print(f"🎬 视频: {result['video_url']}")
        if result.get('images'):    print(f"📸 图片({len(result['images'])}张)")
        if result.get('cover_url'): print(f"🖼️ 封面: {result['cover_url']}")


if __name__ == '__main__':
    asyncio.run(main())
