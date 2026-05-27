"""抖音解析器 - 常驻浏览器 + 签名算法，极致优化"""
import asyncio, time, re
from urllib.parse import urlencode, quote, urlparse
from playwright.async_api import async_playwright
from _dy_signer import DouyinSigner
import httpx


class DouyinParser:
    """
    抖音解析器 - 常驻浏览器模式（最快体验）
    
    浏览器进程只启动一次，之后常驻后台：
    - Cookie 缓存30分钟
    - 新标签页提取aweme_id（0.5-2秒）
    - A-Bogus签名直调API（1秒）
    - 总计：首次~6s 后续~2-3秒
    """
    
    _pw = None
    _browser = None
    _ctx = None
    _cookies = {}
    _cookie_time = 0
    _aweme_cache = {}  # short_code → aweme_id 映射
    
    async def _ensure_browser(self):
        """确保浏览器进程常驻"""
        if not self._browser:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True, args=['--no-sandbox', '--blink-settings=imagesEnabled=false'])
            self._ctx = await self._browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14) Chrome/130.0.6728.40 Mobile',
                viewport={'width':390,'height':844}, is_mobile=True, locale='zh-CN')
    
    async def _ensure_cookies(self, url: str = None):
        """获取或刷新Cookie"""
        now = time.time()
        if self._cookies and now - self._cookie_time < 1800:  # 30分钟
            return True
        
        await self._ensure_browser()
        
        # 用提供的URL或默认URL获取Cookie
        target = url or "https://v.douyin.com/LfY3xT6vNKU/"
        page = await self._ctx.new_page()
        await page.goto(target, timeout=10000, wait_until='domcontentloaded')
        await page.wait_for_timeout(1000)
        self._cookies = {c['name']: c['value'] for c in await self._ctx.cookies()}
        self._cookie_time = time.time()
        await page.close()
        
        return 'ttwid' in self._cookies
    
    async def _resolve_short_code(self, url: str) -> str | None:
        """从短链接提取aweme_id"""
        # 1. 如果URL已经包含aweme_id
        m = re.search(r'video/(\d+)', url)
        if m: return m.group(1)
        
        # 2. 缓存查找
        m = re.search(r'v\.douyin\.com/(\w+)', url)
        short_code = m.group(1) if m else None
        if short_code and short_code in self._aweme_cache:
            return self._aweme_cache[short_code]
        
        # 3. 浏览器解析（最快方式：捕获request URL）
        await self._ensure_browser()
        page = await self._ctx.new_page()
        
        target_url = None
        def capture(req):
            nonlocal target_url
            if 'iesdouyin.com/share/video/' in req.url:
                target_url = req.url
        page.on('request', capture)
        
        await page.goto(url, timeout=8000, wait_until='commit')
        await page.wait_for_timeout(300)
        await page.close()
        
        if target_url:
            m = re.search(r'video/(\d+)', target_url)
            if m:
                aweme_id = m.group(1)
                if short_code:
                    self._aweme_cache[short_code] = aweme_id
                return aweme_id
        
        return None
    
    async def parse(self, url: str) -> dict:
        """解析抖音链接，返回最高画质无水印视频"""
        r = {'success': False, 'title': '', 'video_url': None,
             'images': [], 'cover_url': None, 'error': ''}
        
        try:
            # 1. Cookie
            await self._ensure_cookies(url)
            if 'ttwid' not in self._cookies:
                raise ValueError("Cookie获取失败")
            
            # 2. aweme_id
            aweme_id = await self._resolve_short_code(url)
            if not aweme_id:
                raise ValueError("无法提取视频ID")
            
            # 3. 签名+API
            params = {'device_platform': 'webapp', 'aid': '6383', 'aweme_id': aweme_id}
            signer = DouyinSigner()
            bogus = signer.sign(params)
            
            api_url = (
                f"https://www.douyin.com/aweme/v1/web/aweme/detail/"
                f"?{urlencode(params)}&a_bogus={quote(bogus, safe='')}"
            )
            
            async with httpx.AsyncClient(timeout=10, cookies=self._cookies) as c:
                resp = await c.get(api_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0',
                    'Referer': 'https://www.douyin.com/',
                })
                data = resp.json()
                detail = data.get('aweme_detail', data)
            
            # 4. 提取最高画质
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
