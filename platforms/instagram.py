"""Instagram解析器 - 纯浏览器模式，100%原创"""
from playwright.async_api import async_playwright
import re


class InstagramParser:
    """Instagram解析器：浏览器加载页面→提取视频/图片
    
    需要提前通过Cookie系统配置sessionid。
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
            cookies = SecureCookieManager().get('instagram')
        except: pass
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
                viewport={'width': 390, 'height': 844}, is_mobile=True)
            
            for name, value in cookies.items():
                if name in ('sessionid', 'csrftoken', 'ds_user_id', 'ig_did'):
                    try:
                        await ctx.add_cookies([{
                            'name': name, 'value': value,
                            'domain': '.instagram.com', 'path': '/'
                        }])
                    except: pass
            
            page = await ctx.new_page()
            
            # 监听视频/图片响应
            media_urls = []
            def capture_media(resp):
                ct = resp.headers.get('content-type', '')
                u = resp.url
                if 'video' in ct and 'cdninstagram' in u:
                    media_urls.append(('video', u))
                elif 'image' in ct and 'cdninstagram' in u:
                    media_urls.append(('image', u))
            page.on('response', capture_media)
            
            await page.goto(url, timeout=20000, wait_until='commit')
            await page.wait_for_timeout(6000)
            
            # 标题
            try:
                el = await page.query_selector('title')
                if el: result['title'] = (await el.inner_text())[:200]
            except: pass
            
            # 从video元素提取
            videos = await page.query_selector_all('video')
            for v in videos:
                src = await v.get_attribute('src')
                if src:
                    result['video_url'] = src
                    result['success'] = True
                    break
            
            # 从捕获的响应中取
            if not result['video_url']:
                for mtype, url in media_urls:
                    if mtype == 'video':
                        result['video_url'] = url
                        result['success'] = True
                    elif mtype == 'image' and not result['cover_url']:
                        result['cover_url'] = url
                        result['images'].append(url)
            
            # meta标签封面
            if not result['cover_url']:
                for m in await page.query_selector_all('meta[property="og:image"]'):
                    c = await m.get_attribute('content')
                    if c: result['cover_url'] = c; break
            
            await browser.close()
        
        return result
