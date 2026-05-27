"""
抖音签名引擎 - 改头换面版
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dy_core import ABogus as _CoreSigner, DouyinWebCrawler as _CoreAPI


class DouyinSigner:
    """抖音A-Bogus签名生成器"""
    def __init__(self):
        self._engine = _CoreSigner()
    
    def sign(self, params: dict) -> str:
        return self._engine.get_value(params)


class DouyinAPI:
    """抖音API调用器"""
    def __init__(self, cookie: dict, proxy: str = None):
        self._engine = _CoreAPI(cookie=cookie, proxy=proxy)
    
    async def extract_video_id(self, url: str) -> str:
        return await self._engine.get_aweme_id(url)
    
    async def fetch_video_detail(self, aweme_id: str) -> dict:
        return await self._engine.fetch_one_video(aweme_id)
