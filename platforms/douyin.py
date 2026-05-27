"""抖音解析器 - 纯浏览器模式，100%原创"""
from playwright.async_api import async_playwright
import re


class DouyinParser:
    """抖音解析器：浏览器加载页面→提取video元素→playwm→play去水印
    
    原理：抖音分享页的video元素src含playwm参数，
    改为play就是无水印版本。无需任何签名算法。
    """
    
    async def parse(self, url: str) -> dict:
        result = {
            'success': False, 'title': '', 'video_url': None,
            'images': [], 'cover_url': None, 'error': ''
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 Chrome/130.0.6728.40 Mobile Safari/537.36',
                viewport={'width': 390, 'height': 844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()
            
            # 监听封面图片
            def capture_cover(resp):
                ct = resp.headers.get('content-type', '')
                u = resp.url
                if 'image' in ct and 'cover' in u.lower() and not result['cover_url']:
                    result['cover_url'] = u
            page.on('response', capture_cover)
            
            await page.goto(url, timeout=20000, wait_until='commit')
            await page.wait_for_timeout(5000)
            
            # 提取标题
            try:
                el = await page.query_selector('title')
                if el: result['title'] = (await el.inner_text())[:200]
            except: pass
            
            # 提取视频URL - 从video元素的src
            videos = await page.query_selector_all('video')
            for v in videos:
                src = await v.get_attribute('src')
                if src and 'playwm' in src:
                    # 相对路径转绝对
                    if src.startswith('/'):
                        src = f'https://www.douyin.com{src}'
                    # playwm → play 去水印
                    result['video_url'] = src.replace('playwm', 'play')
                    result['success'] = True
                    break
            
            if not result['video_url']:
                # 尝试从页面内嵌数据提取
                content = await page.content()
                # 搜索 video_id
                vid_match = re.search(r'video_id["\':]\s*["\']([^"\']+)', content)
                if vid_match:
                    vid = vid_match.group(1)
                    result['video_url'] = f'https://www.douyin.com/aweme/v1/play/?video_id={vid}&ratio=720p&line=0'
                    result['success'] = True
            
            await browser.close()
        
        return result
