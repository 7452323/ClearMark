"""抖音解析器 - 签名算法模式，Cookie缓存"""
import asyncio, time, re
from urllib.parse import urlencode, quote
from playwright.async_api import async_playwright
from _dy_signer import DouyinSigner
import httpx


class DouyinParser:
    """抖音解析器 - 签名算法 + Cookie缓存"""
    
    _cookies = None
    _last_refresh = 0
    
    async def _get_cookies(self) -> dict:
        now = time.time()
        if self._cookies and now - self._last_refresh < 300:
            return self._cookies
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14) Chrome/130.0.6728.40 Mobile',
                viewport={'width':390,'height':844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()
            await page.goto("https://v.douyin.com/LfY3xT6vNKU/", timeout=8000, wait_until='commit')
            await page.wait_for_timeout(1500)
            self._cookies = {c['name']: c['value'] for c in await ctx.cookies()}
            self._last_refresh = time.time()
            await browser.close()
        return self._cookies
    
    async def parse(self, url: str) -> dict:
        """解析抖音链接，返回最高画质无水印视频"""
        r = {'success': False, 'title': '', 'video_url': None,
             'images': [], 'cover_url': None, 'error': ''}
        start = time.time()
        
        try:
            cookies = await self._get_cookies()
            t1 = time.time()
            
            # 提取aweme_id
            m = re.search(r'video/(\d+)', url) or re.search(r'modal_id=(\d+)', url)
            if not m:
                async with httpx.AsyncClient(timeout=5, follow_redirects=True) as c:
                    resp = await c.get(url)
                    m = re.search(r'video/(\d+)', str(resp.url))
            if not m:
                raise ValueError("无法提取视频ID")
            aweme_id = m.group(1)
            t2 = time.time()
            
            # A-Bogus签名
            params = {'device_platform': 'webapp', 'aid': '6383', 'aweme_id': aweme_id}
            signer = DouyinSigner()
            bogus = signer.sign(params)
            
            api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{urlencode(params)}&a_bogus={quote(bogus, safe='')}"
            
            # ⚠️ Cookie必须用httpx的cookies=参数，不能用Cookie头
            async with httpx.AsyncClient(timeout=10, cookies=cookies) as c:
                resp = await c.get(api_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0',
                    'Referer': 'https://www.douyin.com/',
                })
                data = resp.json()
                detail = data.get('aweme_detail', data)
            
            t3 = time.time()
            
            r['title'] = detail.get('desc', '')[:200]
            r['success'] = True
            
            video = detail.get('video', {})
            brs = video.get('bit_rate', [])
            if brs:
                best = max(brs, key=lambda x:
                    x.get('play_addr',{}).get('width',0)*x.get('play_addr',{}).get('height',0))
                urls = best.get('play_addr',{}).get('url_list',[])
                if urls:
                    r['video_url'] = urls[0].replace('playwm', 'play')
            
            cover = video.get('cover',{}).get('url_list',[])
            if cover: r['cover_url'] = cover[-1]
            
        except Exception as e:
            r['error'] = str(e)
        
        return r
