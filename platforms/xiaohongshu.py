"""小红书解析器 - 浏览器模式"""
from playwright.async_api import async_playwright
import logging

log = logging.getLogger('clearmark')


class XiaohongshuParser:
    """小红书解析器：浏览器加载笔记→提取视频/图片"""

    async def parse(self, url: str) -> dict:
        result = {
            'success': False, 'title': '', 'video_url': None,
            'images': [], 'cover_url': None, 'error': ''
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
                viewport={'width': 390, 'height': 844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()

            # 监听媒体响应
            video_urls, image_urls = [], []
            def capture_media(resp):
                ct = resp.headers.get('content-type', '')
                u = resp.url
                if 'video' in ct and 'xhscdn' in u:
                    video_urls.append(u)
                elif 'image' in ct and 'xhscdn' in u:
                    image_urls.append(u)
            page.on('response', capture_media)

            await page.goto(url, timeout=20000, wait_until='commit')
            try:
                await page.wait_for_selector('#note-container', timeout=10000)
            except Exception:
                await page.wait_for_timeout(6000)

            # 标题
            try:
                el = await page.query_selector('title')
                if el:
                    result['title'] = (await el.inner_text())[:200]
            except Exception:
                pass

            # video元素
            videos = await page.query_selector_all('video')
            for v in videos:
                src = await v.get_attribute('src')
                if src:
                    result['video_url'] = src
                    result['success'] = True
                    break

            # 封面
            if not result['cover_url']:
                try:
                    for m in await page.query_selector_all('meta[property="og:image"]'):
                        c = await m.get_attribute('content')
                        if c:
                            result['cover_url'] = c
                            break
                except Exception:
                    pass

            # 捕获的媒体
            if not result['video_url'] and video_urls:
                result['video_url'] = video_urls[-1]
                result['success'] = True
            if not result['images'] and image_urls:
                result['images'] = image_urls[:9]
                if not result['cover_url']:
                    result['cover_url'] = image_urls[0]
            if not result['success']:
                result['success'] = bool(result['video_url'] or result['images'])

            await browser.close()

        return result
