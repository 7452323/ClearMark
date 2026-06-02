"""Twitter/X 解析器"""
from playwright.async_api import async_playwright
import re, logging

log = logging.getLogger('clearmark')


class TwitterParser:
    """Twitter解析器：优先 API，回退浏览器

    1. 有 Cookie → 浏览器模式加载推文解析
    2. 无 Cookie → 先尝试 Tweety API，失败则仍走浏览器（公开推文可读）
    """

    async def parse(self, url: str) -> dict:
        result = {
            'success': False, 'title': '', 'video_url': None,
            'images': [], 'cover_url': None, 'error': ''
        }

        cookies = {}
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cookies'))
            from secure_manager import SecureCookieManager
            cookies = SecureCookieManager().get('twitter')
        except Exception:
            pass

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
                viewport={'width': 390, 'height': 844}, is_mobile=True,
                locale='en-US')

            # 注入Cookie
            for name, value in cookies.items():
                if name in ('auth_token', 'ct0', 'twid', 'guest_id'):
                    for domain in ('.twitter.com', '.x.com'):
                        try:
                            await ctx.add_cookies([{
                                'name': name, 'value': value,
                                'domain': domain, 'path': '/'
                            }])
                        except Exception:
                            pass

            page = await ctx.new_page()

            # 监听视频响应
            video_urls = []
            def capture_video(resp):
                ct = resp.headers.get('content-type', '')
                u = resp.url
                if 'video' in ct and ('twimg' in u):
                    video_urls.append(u)
            page.on('response', capture_video)

            # 访问推文 - 用 domcontentloaded + 等待关键元素
            await page.goto(url, timeout=20000, wait_until='commit')
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            except Exception:
                await page.wait_for_timeout(6000)

            # 提取标题
            try:
                el = await page.query_selector('title')
                if el:
                    result['title'] = (await el.inner_text())[:200]
            except Exception:
                pass

            # 从页面video元素提取
            videos = await page.query_selector_all('video')
            for v in videos:
                src = await v.get_attribute('src')
                poster = await v.get_attribute('poster')
                if src and 'twimg' in src:
                    result['video_url'] = src
                    result['success'] = True
                if poster and not result['cover_url']:
                    result['cover_url'] = poster

            # 或从meta标签提取
            if not result['video_url']:
                metas = await page.query_selector_all('meta[property="og:video"]')
                for m in metas:
                    content = await m.get_attribute('content')
                    if content:
                        result['video_url'] = content
                        result['success'] = True
                        break

            # 或从捕获的响应中取
            if not result['video_url'] and video_urls:
                result['video_url'] = video_urls[-1]
                result['success'] = True

            # 提取封面
            if not result['cover_url']:
                try:
                    for m in await page.query_selector_all('meta[property="og:image"]'):
                        c = await m.get_attribute('content')
                        if c:
                            result['cover_url'] = c
                            break
                except Exception:
                    pass

            await browser.close()

        return result
