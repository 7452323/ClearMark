"""抖音解析器 - 签名算法(快) + 浏览器兜底"""
from playwright.async_api import async_playwright
import re, asyncio, httpx, time
from urllib.parse import urlencode, quote
import sys, os

# 引入签名引擎
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'our_parser'))
try:
    from signer import ABogusSigner
    HAS_SIGNER = True
except:
    HAS_SIGNER = False


class DouyinParser:
    """
    抖音解析器 - 双模式
    
    模式A (签名算法): 浏览器拿Cookie → 自研A-Bogus签名 → 直调API → 1-2秒
    模式B (浏览器兜底): 纯浏览器加载页面 → 提取video元素 → 5-8秒
    """
    
    _cookies = None
    
    async def _get_cookies(self) -> dict:
        if self._cookies:
            return self._cookies
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36',
                viewport={'width':1920,'height':1080})
            page = await ctx.new_page()
            await page.goto("https://www.douyin.com", timeout=10000, wait_until='commit')
            await page.wait_for_timeout(2000)
            cookies = await ctx.cookies()
            await browser.close()
        
        self._cookies = {c['name']: c['value'] for c in cookies}
        return self._cookies
    
    async def _extract_aweme_id(self, url: str) -> str | None:
        """从分享链接提取aweme_id"""
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            r = await c.get(url)
            url_str = str(r.url)
        
        for p in [r'video/(\d+)', r'modal_id=(\d+)']:
            m = re.search(p, url_str)
            if m: return m.group(1)
        return None
    
    async def parse_mode_a(self, url: str) -> dict | None:
        """模式A: 签名算法直调API"""
        if not HAS_SIGNER:
            return None
        
        aweme_id = await self._extract_aweme_id(url)
        if not aweme_id:
            return None
        
        params = {
            'device_platform': 'webapp', 'aid': '6383',
            'channel': 'channel_pc_web', 'pc_client_type': '1',
            'version_code': '290100', 'version_name': '29.1.0',
            'cookie_enabled': 'true', 'screen_width': '1920',
            'screen_height': '1080', 'browser_language': 'zh-CN',
            'browser_platform': 'Win32', 'browser_name': 'Chrome',
            'browser_version': '130.0.0.0', 'browser_online': 'true',
            'engine_name': 'Blink', 'engine_version': '130.0.0.0',
            'os_name': 'Windows', 'os_version': '10',
            'cpu_core_num': '12', 'device_memory': '8',
            'platform': 'PC', 'downlink': '10', 'effective_type': '4g',
            'aweme_id': aweme_id,
        }
        
        cookies = await self._get_cookies()
        if not cookies:
            return None
        
        cookie_str = '***'.join(f'{k}={v}' for k, v in cookies.items())
        signer = ABogusSigner()
        bogus = signer.sign(params)
        
        api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{urlencode(params)}&a_bogus={quote(bogus, safe='')}"
        
        headers = {
            'User-Agent': signer.user_agent,
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://www.douyin.com/',
            'Cookie': cookie_str,
        }
        
        async with httpx.AsyncClient(headers=headers, timeout=15) as c:
            r = await c.get(api_url)
            if r.status_code != 200:
                return None
            try:
                data = r.json()
            except:
                return None
            
            detail = data.get('aweme_detail')
            if not detail:
                return None
            
            result = {
                'success': True,
                'title': detail.get('desc', ''),
                'video_url': None,
                'images': [],
                'cover_url': None,
                'method': 'algorithm',
            }
            
            video = detail.get('video', {})
            brs = video.get('bit_rate', [])
            if brs:
                best = max(brs, key=lambda x:
                    x.get('play_addr', {}).get('width', 0) * x.get('play_addr', {}).get('height', 0))
                urls = best.get('play_addr', {}).get('url_list', [])
                if urls:
                    result['video_url'] = urls[0].replace('playwm', 'play')
            
            cover = video.get('cover', {}).get('url_list', [])
            if cover:
                result['cover_url'] = cover[-1]
            
            return result
        
        return None
    
    async def parse_mode_b(self, url: str) -> dict:
        """模式B: 浏览器兜底"""
        result = {'success': False, 'title': '', 'video_url': None,
                  'images': [], 'cover_url': None, 'method': 'browser'}
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox',
                '--blink-settings=imagesEnabled=false'])
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0.6728.40 Mobile',
                viewport={'width': 390, 'height': 844}, is_mobile=True, locale='zh-CN')
            page = await ctx.new_page()
            
            async def block(r):
                ext = r.request.url.rsplit('.', 1)[-1].split('?')[0]
                if ext in ('css', 'woff', 'woff2', 'ttf', 'otf', 'ico', 'svg'):
                    await r.abort()
                else:
                    await r.continue_()
            await page.route('**/*', block)
            
            await page.goto(url, timeout=15000, wait_until='domcontentloaded')
            
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
            
            if not result['video_url']:
                content = await page.content()
                vid = re.search(r'video_id[\'":]\s*[\'"](\w+)', content)
                if vid:
                    result['video_url'] = (
                        f'https://www.douyin.com/aweme/v1/play/?video_id={vid.group(1)}&ratio=720p&line=0')
                    result['success'] = True
            
            try:
                el = await page.query_selector('title')
                if el:
                    result['title'] = (await el.inner_text())[:200]
            except:
                pass
            
            await browser.close()
        
        return result
    
    async def parse(self, url: str) -> dict:
        """解析入口: 模式A → 模式B"""
        # 先试试签名算法模式 (1-2秒)
        result = await self.parse_mode_a(url)
        if result and result['success']:
            return result
        
        # 不行就浏览器兜底 (5-8秒)
        return await self.parse_mode_b(url)
