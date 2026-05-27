"""小红书解析器 - 完全独立"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from xhs import XHSAPI
    HAS_XHS = True
except: HAS_XHS = False


class ParseResult:
    def __init__(self, platform: str, url: str):
        self.platform = platform; self.source_url = url
        self.success = False; self.title = ''
        self.video_url = None; self.images = []
        self.cover_url = None; self.error = ''; self.method = ''


class XiaohongshuParser:
    def __init__(self): self.name = 'xiaohongshu'
    
    async def parse(self, url: str):
        result = ParseResult('xiaohongshu', url)
        try:
            if not HAS_XHS: raise RuntimeError('小红书模块不可用')
            xhs = XHSAPI(cookie={})
            post = await xhs.extract(url)
            result.success = True
            result.title = post.title or ''
            for media in (post.media or []):
                if media.type in ('video','livephoto'):
                    result.video_url = media.url
                    if media.thumb_url: result.cover_url = media.thumb_url
                else: result.images.append(media.url)
            result.method = 'browser'
        except Exception as e:
            result.error = str(e)
        return result
