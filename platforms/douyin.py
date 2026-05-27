"""抖音解析器 - 纯浏览器驱动（原创，5秒以内）"""
from playwright.async_api import async_playwright
import re, asyncio


class DouyinParser:
    """
    抖音解析器：浏览器加载分享页 → 提取video src → playwm换play去水印
    全流程原创，不依赖任何签名算法。5秒内出结果。
    """
    
    async def parse(self, url: str) -> dict:
        result = {
            'success': False, 'title': '', 'video_url': None,
            'images': [], 'cover_url': None, 'error': ''
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox',
                '--blink-settings=imagesEnabled=false'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0.6728.40 Mobile Safari/537.36',
                viewport={'width':390,'height':844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()
            
            # 拦截无用的CSS/字体/图标，只加载HTML+JS
            async def block_assets(route):
                ext = route.request.url.split('.')[-1].split('?')[0]
                if ext in ('css','woff','woff2','ttf','otf','ico','svg'):
                    await route.abort()
                else:
                    await route.continue_()
            await page.route('**/*', block_assets)
            
            # 监听封面图片响应（首次出现时捕获）
            cover_captured = False
            def capture_cover(resp):
                nonlocal cover_captured
                if cover_captured:
                    return
                ct = resp.headers.get('content-type', '')
                u = resp.url
                if 'image' in ct and 'cover' in u.lower():
                    result['cover_url'] = u
                    cover_captured = True
            page.on('response', capture_cover)
            
            # 访问分享页（v.douyin.com → 自动重定向）
            await page.goto(url, timeout=15000, wait_until='domcontentloaded')
            
            # 轮询等待video元素出现（最长5秒）
            for _ in range(25):
                await asyncio.sleep(0.2)
                videos = await page.query_selector_all('video')
                for v in videos:
                    src = await v.get_attribute('src')
                    if src and 'playwm' in src:
                        if src.startswith('/'):
                            src = f'https://www.douyin.com{src}'
                        result['video_url'] = src.replace('playwm', 'play')
                        result['success'] = True
                        break
                if result['success']:
                    break
            
            # 备选：从页面源码提取video_id
            if not result['video_url']:
                content = await page.content()
                vid = re.search(r'video_id[\'":]\s*[\'"](\w+)', content)
                if vid:
                    v = vid.group(1)
                    result['video_url'] = (
                        f'https://www.douyin.com/aweme/v1/play/?video_id={v}&ratio=720p&line=0')
                    result['success'] = True
            
            # 标题
            try:
                el = await page.query_selector('title')
                if el: result['title'] = (await el.inner_text())[:200]
            except: pass
            
            await browser.close()
        
        return result
