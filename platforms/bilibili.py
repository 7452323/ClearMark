"""B站解析器 - 零浏览器，官方API直取最高画质"""
import re, httpx


class BilibiliParser:
    """B站解析器"""
    
    async def parse(self, url: str) -> dict:
        r = {'success': False, 'title': '', 'video_url': None,
             'images': [], 'cover_url': None, 'error': ''}
        
        try:
            m = re.search(r'(BV[\w]+)', url)
            if not m:
                raise ValueError("不支持的B站链接格式")
            bvid = m.group(1)
            
            async with httpx.AsyncClient(timeout=10) as c:
                headers = {'Referer': 'https://www.bilibili.com/',
                           'User-Agent': 'Mozilla/5.0'}
                
                # 视频信息
                resp = await c.get(
                    f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',
                    headers=headers)
                data = resp.json()
                if data.get('code') != 0:
                    raise RuntimeError(data.get('message', 'B站API错误'))
                
                v = data['data']
                r['title'] = v.get('title', '')[:200]
                r['cover_url'] = v.get('pic', '')
                
                # 播放地址（qn=120 最高画质）
                aid, cid = v.get('aid'), v.get('cid')
                if aid and cid:
                    pr = await c.get(
                        f'https://api.bilibili.com/x/player/playurl?avid={aid}&cid={cid}&qn=120',
                        headers=headers)
                    if pr.status_code == 200:
                        pd = pr.json()
                        durl = pd.get('data', {}).get('durl', [])
                        if durl:
                            r['video_url'] = durl[0].get('url')
                            r['success'] = True
        except Exception as e:
            r['error'] = str(e)
        return r
