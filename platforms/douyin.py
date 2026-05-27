"""抖音解析器 - 零浏览器 + 持久连接池"""
import asyncio, re, httpx
from urllib.parse import urlencode, quote
from _dy_signer import DouyinSigner


class DouyinParser:
    """
    抖音解析器 - 零浏览器模式
    
    日常运行完全无需浏览器：
    1. 加密存储加载Cookie
    2. HTTP 302 提取视频ID（持久连接）
    3. A-Bogus签名直调API
    
    浏览器仅用于Cookie过期时刷新一次。
    """

    _http = None
    _cookies = {}
    _aweme_cache = {}

    async def _get_http(self) -> httpx.AsyncClient:
        if not self._http:
            self._http = httpx.AsyncClient(timeout=5)
        return self._http

    async def _load_cookies(self) -> dict:
        if self._cookies:
            return self._cookies
        try:
            import os, sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cookies'))
            from secure_manager import SecureCookieManager
            self._cookies = SecureCookieManager().get('douyin')
        except:
            pass
        return self._cookies

    async def _save_cookies(self, cookies: dict):
        if not cookies:
            return
        self._cookies = cookies
        try:
            import os, sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cookies'))
            from secure_manager import SecureCookieManager
            cm = SecureCookieManager()
            existing = cm.get('douyin') or {}
            if '_placeholder' in existing:
                existing = {}
            existing.update(cookies)
            cm.set('douyin', existing)
        except:
            pass

    async def _get_aweme_id(self, url: str) -> str | None:
        """提取aweme_id - 零浏览器"""
        # 1. URL直取
        m = re.search(r'video/(\d+)', url)
        if m: return m.group(1)

        # 2. 缓存
        m = re.search(r'v\.douyin\.com/(\w+)', url)
        short = m.group(1) if m else None
        if short and short in self._aweme_cache:
            return self._aweme_cache[short]

        # 3. HTTP 302 重定向（持久连接，0.7-1.2s）
        http = await self._get_http()
        r = await http.get(url, follow_redirects=False)
        loc = r.headers.get('location', '')
        m = re.search(r'video/(\d+)', loc)
        if m:
            if short:
                self._aweme_cache[short] = m.group(1)
            return m.group(1)
        return None

    async def _call_api(self, aweme_id: str) -> dict | None:
        """A-Bogus签名 + API调用"""
        cookies = await self._load_cookies()
        if not cookies:
            return None

        signer = DouyinSigner()
        params = {'device_platform': 'webapp', 'aid': '6383', 'aweme_id': aweme_id}
        bogus = signer.sign(params)
        url = (f"https://www.douyin.com/aweme/v1/web/aweme/detail/"
               f"?{urlencode(params)}&a_bogus={quote(bogus, safe='')}")

        async with httpx.AsyncClient(timeout=10, cookies=cookies) as c:
            resp = await c.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0',
                'Referer': 'https://www.douyin.com/',
            })
            if resp.status_code == 200 and len(resp.text) > 100:
                try:
                    return resp.json()
                except:
                    return resp.text
        return None

    async def _refresh_cookies_browser(self) -> dict:
        """浏览器刷新Cookie（过期后兜底）"""
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14) Chrome/130.0.6728.40 Mobile',
                viewport={'width': 390, 'height': 844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()
            await page.goto("https://v.douyin.com/LfY3xT6vNKU/", timeout=10000,
                            wait_until='domcontentloaded')
            await page.wait_for_timeout(1000)
            cookies = {c['name']: c['value'] for c in await ctx.cookies()}
            await browser.close()
        if 'ttwid' in cookies:
            await self._save_cookies(cookies)
        return cookies

    async def parse(self, url: str) -> dict:
        """解析入口"""
        r = {'success': False, 'title': '', 'video_url': None,
             'images': [], 'cover_url': None, 'error': ''}
        try:
            aweme_id = await self._get_aweme_id(url)
            if not aweme_id:
                raise ValueError("无法提取视频ID")

            data = await self._call_api(aweme_id)
            if not data:
                print("🔄 Cookie过期，浏览器刷新...")
                await self._refresh_cookies_browser()
                data = await self._call_api(aweme_id)
            if not data:
                raise RuntimeError("API调用失败")

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
                    x.get('play_addr', {}).get('width', 0) * x.get('play_addr', {}).get('height', 0))
                urls = best.get('play_addr', {}).get('url_list', [])
                if urls:
                    r['video_url'] = urls[0].replace('playwm', 'play')

            cover = video.get('cover', {}).get('url_list', [])
            if cover:
                r['cover_url'] = cover[-1]

        except Exception as e:
            r['error'] = str(e)

        return r
