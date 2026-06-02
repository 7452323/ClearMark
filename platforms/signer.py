"""
抖音 A-Bogus 签名算法

基于对字节跳动webmssdk的反向分析独立编写。
算法流程: URL参数 → SM3双重哈希 → 构建特征buffer → RC4加密 → 自定义Base64

依赖: gmssl (pip install gmssl)
"""
import random, time
from urllib.parse import urlencode


class DouyinSigner:
    """
    A-Bogus 签名生成器

    用于抖音网页版API请求的数字签名。
    """

    # 自定义Base64字符表 (s4)
    BASE64 = "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe"

    # 固定编码常量
    K_44, K_239, K_3, K_1, K_14, K_24 = 44, 239, 3, 1, 14, 24

    # UA指纹码 (从Chrome 130 UA预计算)
    UA_FP = [76, 98, 15, 131, 97, 245, 224, 133, 122, 199, 241, 166, 79, 34, 90, 191,
             128, 126, 122, 98, 66, 11, 14, 40, 49, 110, 110, 173, 67, 96, 138, 252]

    # 固定浏览器规格
    DEFAULT_BROWSER = '1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel'

    def __init__(self, user_agent: str | None = None):
        self.ua = user_agent or (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
        self._salt = 'cus'
        self._browser = self.DEFAULT_BROWSER
        self._browser_len = len(self._browser)
        self._browser_codes = [ord(c) for c in self._browser]

    def _sm3_double(self, data: str) -> list:
        """SM3双重哈希: sm3(sm3(data)) → 32字节数组"""
        from gmssl import func, sm3
        h1 = sm3.sm3_hash(func.bytes_to_list(data.encode('utf-8')))
        b2 = bytes(int(h1[i:i+2], 16) for i in range(0, 64, 2))
        h2 = sm3.sm3_hash(func.bytes_to_list(b2))
        return [int(h2[i:i+2], 16) for i in range(0, 64, 2)]

    def _make_buffer(self, url_fp: list, method_fp: list, st: int, et: int) -> list:
        """构建44字节特征buffer (对应list_4)"""
        return [
            self.K_44,
            (et >> 24) & 0xFF, 0, 0, 0, 0,
            self.K_24,
            url_fp[21],
            method_fp[21], 0,
            self.UA_FP[23],
            (et >> 16) & 0xFF,
            0, 0, 0,
            self.K_1, 0,
            self.K_239,
            url_fp[22],
            method_fp[22],
            self.UA_FP[24],
            (et >> 8) & 0xFF,
            0, 0, 0, 0,
            et & 0xFF,
            0, 0,
            self.K_14,
            (st >> 24) & 0xFF,
            (st >> 16) & 0xFF, 0,
            (st >> 8) & 0xFF,
            st & 0xFF,
            self.K_3,
            (et >> 32) & 0xFF,
            self.K_1,
            (st >> 32) & 0xFF,
            self.K_1,
            self._browser_len,
            0, 0, 0,
        ]

    @staticmethod
    def _xor_sum(data: list) -> int:
        r = 0
        for x in data:
            r ^= x
        return r

    @staticmethod
    def _rc4(data: list, key: str = 'y') -> list:
        """RC4加密"""
        s = list(range(256))
        j = 0
        for i in range(256):
            j = (j + s[i] + ord(key[i % len(key)])) & 0xFF
            s[i], s[j] = s[j], s[i]
        i = j = 0
        out = []
        for byte in data:
            i = (i + 1) & 0xFF
            j = (j + s[i]) & 0xFF
            s[i], s[j] = s[j], s[i]
            out.append(byte ^ s[(s[i] + s[j]) & 0xFF])
        return out

    @staticmethod
    def _rl(r=None, a=170, b=85, d=0, e=0, f=0, g=0):
        """随机数列表生成 (对应list_1/list_2/list_3)"""
        if r is None:
            # 加 1e-9 避免 random() 返回 0.0 时 r or (...) 重算
            r = random.random() * 10000 + 1e-9
        v = [r, int(r) & 255, int(r) >> 8]
        v.append(v[1] & a | d)
        v.append(v[1] & b | e)
        v.append(v[2] & a | f)
        v.append(v[2] & b | g)
        return v[-4:]

    def _random_prefix(self) -> list:
        """12字节随机前缀"""
        return (self._rl(d=1, e=2, f=5, g=40) +  # list_1
                self._rl(d=1, e=0, f=0, g=0) +    # list_2
                self._rl(d=1, e=0, f=5, g=0))      # list_3

    def _b64_encode(self, data: list) -> str:
        """自定义Base64编码 (s4字符表)"""
        result = []
        for i in range(0, len(data), 3):
            chunk = (data[i] << 16)
            if i + 1 < len(data):
                chunk |= (data[i + 1] << 8)
            if i + 2 < len(data):
                chunk |= data[i + 2]
            result.append(self.BASE64[(chunk >> 18) & 0x3F])
            result.append(self.BASE64[(chunk >> 12) & 0x3F])
            result.append(self.BASE64[(chunk >> 6) & 0x3F] if i + 1 < len(data) else '=')
            result.append(self.BASE64[chunk & 0x3F] if i + 2 < len(data) else '=')
        return ''.join(result)

    def sign(self, params: dict, method: str = 'GET') -> str:
        """生成 A-Bogus 签名

        ⚠️ 随机数生成顺序必须固定：先 _random_prefix()（消耗3个），再用时间
        """
        prefix = self._random_prefix()
        now = int(time.time() * 1000)
        then = now + random.randint(4, 8)

        # 1. SM3双重哈希
        query = urlencode(sorted(params.items()))
        url_fp = self._sm3_double(query + self._salt)
        method_fp = self._sm3_double(method + self._salt)

        # 2. 构建44字节特征buffer
        buf = self._make_buffer(url_fp, method_fp, now, then)

        # 3. XOR校验
        buf.append(self._xor_sum(buf))

        # 4. 追加浏览器指纹
        buf.extend(self._browser_codes)

        # 5. RC4加密
        encrypted = self._rc4(buf, 'y')

        # 6. 拼接随机前缀 + Base64编码
        return self._b64_encode(prefix + encrypted)
