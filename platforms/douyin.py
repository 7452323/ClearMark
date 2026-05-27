"""抖音解析器 - 零浏览器模式（默认）+ 浏览器刷新（兜底）"""
import asyncio, time, re, httpx
from urllib.parse import urlencode, quote
from _dy_signer import DouyinSigner


class DouyinParser:
    """
    抖音解析器
    
    默认模式: 零浏览器（2-3秒）
    - 加密存储加载Cookie → httpx解析短链 → A-Bogus签名 → API
    - 浏览器只用于Cookie过期时刷新一次
    
    兜底模式: 浏览器（仅Cookie过期时触发）
    """
    
    _cookies = {}
    _aweme_cache = {}
    
    async def _load_cookies(self) -> dict:
        """从加密存储加载Cookie"""
        if self._cookies:
            return self._cookies
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cookies'))
            from secure_manager import SecureCookieManager
            self._cookies = SecureCookieManager().get('douyin')
        except:
            pass
        return self._cookies
    
    async def _save_cookies(self, cookies: dict):
        """保存Cookie到加密存储"""
        if not cookies:
            return
        self._cookies = cookies
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cookies'))
            from secure_manager import SecureCookieManager
            cm = SecureCookieManager()
            # 合并已有cookie
            existing = cm.get('douyin')
            if existing and '_placeholder' in existing:
                existing = {}
            existing.update(cookies)
            cm.set('douyin', existing)
        except:
            pass
    
    async def _refresh_cookies(self) -> dict:
        """浏览器刷新Cookie（仅当过期时调用）"""
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14) Chrome/130.0.6728.40 Mobile',
                viewport={'width':390,'height':844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()
            await page.goto("https://v.douyin.com/LfY3xT6vNKU/", timeout=10000, wait_until='domcontentloaded')
            await page.wait_for_timeout(1000)
            cookies = {c['name']: c['value'] for c in await ctx.cookies()}
            await browser.close()
        
        if 'ttwid' in cookies:
            await self._save_cookies(cookies)
        return cookies
    
    async def _get_aweme_id(self, url: str) -> str | None:
        """从链接提取aweme_id"""
        # 1. 直取（如URL已含ID）
        m = re.search(r'video/(\d+)', url)
        if m: return m.group(1)
        
        # 2. 短链接缓存
        m = re.search(r'v\.douyin\.com/(\w+)', url)
        short = m.group(1) if m else None
        if short and short in self._aweme_cache:
            return self._aweme_cache[short]
        
        # 3. HTTP 302 重定向提取（无需浏览器）
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(url, follow_redirects=False)
            loc = r.headers.get('location', '')
            m = re.search(r'video/(\d+)', loc)
            if m:
                if short: self._aweme_cache[short] = m.group(1)
                return m.group(1)
        
        return None
    
    async def _call_api(self, aweme_id: str) -> dict | None:
        """A-Bogus签名 + 调API"""
        cookies = await self._load_cookies()
        if not cookies:
            return None
        
        signer = DouyinSigner()
        params = {'device_platform': 'webapp', 'aid': '6383', 'aweme_id': aweme_id}
        bogus = signer.sign(params)
        
        url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{urlencode(params)}&a_bogus={quote(bogus, safe='')}"
        
        async with httpx.AsyncClient(timeout=10, cookies=cookies) as c:
            resp = await c.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0',
                'Referer': 'https://www.douyin.com/',
            })
            if resp.status_code == 200 and len(resp.text) > 100:
                return resp.json() or resp.text
        return None
    
    async def parse(self, url: str) -> dict:
        """解析抖音链接"""
        r = {'success': False, 'title': '', 'video_url': None,
             'images': [], 'cover_url': None, 'error': ''}
        
        try:
            # 1. aweme_id（零浏览器）
            aweme_id = await self._get_aweme_id(url)
            if not aweme_id:
                raise ValueError("无法提取视频ID")
            
            # 2. 加载Cookie + API（零浏览器 或 过期后自动刷新）
            data = await self._call_api(aweme_id)
            if not data:
                # Cookie可能过期了，刷新一次
                print("🔄 Cookie过期，浏览器刷新...")
                cookies = await self._refresh_cookies()
                if 'ttwid' in cookies:
                    data = await self._call_api(aweme_id)
            
            if not data:
                raise RuntimeError("API调用失败")
            
            # 3. 解析返回
            if isinstance(data, str):
                import json
                data = json.loads(data)
            detail = data.get('aweme_detail', data)
            
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
