#!/usr/bin/env python3
"""ClearMark v2 - 全平台去水印，基于 ParseHub 引擎"""
import os, sys, asyncio, time, re
from pathlib import Path

from parsehub import ParseHub
from parsehub.types import PostType

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
API_BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'


def detect_url(text: str) -> str | None:
    m = re.search(r'https?://[^\s<>"\'\\]+', text)
    return m.group(0).rstrip('/?&') if m else None


async def tg_send_text(text: str):
    if not BOT_TOKEN: return
    import httpx
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f'{API_BASE}/sendMessage',
                     data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})


async def tg_send_file(file_path: str, caption: str = ''):
    if not BOT_TOKEN: return
    import httpx
    ext = Path(file_path).suffix.lower()
    size_mb = os.path.getsize(file_path) / 1024 / 1024
    if size_mb > 50:
        await tg_send_text(f'📎 文件过大({size_mb:.0f}MB)，仅发送链接')
        return
    is_video = ext in ('.mp4', '.mov', '.avi', '.mkv')
    is_photo = ext in ('.jpg', '.jpeg', '.png', '.webp', '.heic')
    if not is_video and not is_photo:
        is_photo = True
    endpoint = 'sendVideo' if is_video else 'sendMediaGroup' if not is_video else 'sendPhoto'
    async with httpx.AsyncClient(timeout=120) as c:
        with open(file_path, 'rb') as f:
            if is_video:
                await c.post(f'{API_BASE}/sendVideo',
                             data={'chat_id': CHAT_ID, 'caption': caption[:200]},
                             files={'video': f})
            else:
                await c.post(f'{API_BASE}/sendPhoto',
                             data={'chat_id': CHAT_ID, 'caption': caption[:200]},
                             files={'photo': f})


async def main():
    if len(sys.argv) < 2:
        print('🐣 ClearMark v2 - 基于 ParseHub 的全平台去水印')
        print()
        print('用法:')
        print('  python clearmark.py "<链接或分享文本>"')
        print()
        print('环境变量:')
        print('  BOT_TOKEN      - Telegram Bot Token（可选，有则自动发送）')
        print('  CHAT_ID        - 接收消息的 Chat ID')
        sys.exit(1)

    text = ' '.join(sys.argv[1:])
    url = detect_url(text)
    if not url:
        print('❌ 未识别到链接')
        sys.exit(1)

    print(f'🔍 解析: {url}')
    hub = ParseHub()

    try:
        result = await hub.parse(url)
    except Exception as e:
        msg = f'❌ 解析失败: {e}'
        print(msg)
        if BOT_TOKEN:
            await tg_send_text(msg)
        sys.exit(1)

    title = result.title or result.content or '(无标题)'
    print(f'📝 {title}')

    # 直接下载并发送
    if BOT_TOKEN:
        dl = await result.download('/tmp/clearmark_v2')
        for m in dl.media:
            await tg_send_file(str(m.path), title[:100])
        print('✅ 已发送到 Telegram')
    else:
        print()
        from parsehub.types import VideoRef, ImageRef, LivePhotoRef
        media_list = []
        if isinstance(result.media, (VideoRef, ImageRef, LivePhotoRef)):
            media_list = [result.media]
        elif result.media:
            media_list = list(result.media)

        if result.type == PostType.VIDEO:
            print(f'🎬 视频')
            for m in media_list:
                print(f'   {m.url}')
        elif result.type == PostType.IMAGE:
            print(f'📸 图片({len(media_list)}张)')
            for m in media_list:
                print(f'   {m.url}')
        else:
            print(f'📎 链接')
            for m in media_list:
                print(f'   {m.url}')
        print()
        print('💡 设置 BOT_TOKEN + CHAT_ID 即可自动发送到 Telegram')


if __name__ == '__main__':
    asyncio.run(main())
