"""Twitter/X 解析器 - 完全独立"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twitter_engine import Twitter


class ParseResult:
    def __init__(self, platform: str, url: str):
        self.platform = platform; self.source_url = url
        self.success = False; self.title = ''
        self.video_url = None; self.images = []
        self.cover_url = None; self.error = ''; self.method = ''


class TwitterParser:
    def __init__(self): self.name = 'twitter'
    
    async def parse(self, url: str):
        result = ParseResult('twitter', url)
        try:
            tw = Twitter()
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cookies'))
                from secure_manager import SecureCookieManager
                tw.cookie = SecureCookieManager().get('twitter')
            except: pass
            tweet = await tw.fetch_tweet(url)
            result.success = True
            result.title = (tweet.full_text or '')[:200]
            for m in tweet.media:
                if hasattr(m, 'url') and m.url:
                    result.video_url = m.url
                elif hasattr(m, 'url') and not result.video_url:
                    result.images.append(m.url)
            result.method = 'algorithm'
        except Exception as e:
            result.error = str(e)
        return result
