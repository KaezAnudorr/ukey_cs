"""网页插件接口的桌面适配；模拟与真实模式由启动参数显式选择。"""
import base64
import binascii
import hashlib
import hmac
import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, ProxyHandler


class LoginError(Exception):
    pass


class Http:
    def __init__(self, base_url, report_errors=False):
        url = urlsplit(base_url)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise ValueError('服务地址必须是无内嵌凭据的 HTTP/HTTPS 地址')
        self.base = base_url.rstrip('/')
        self.report_errors = report_errors
        # 内网与本地助手直连，不将 PIN 发给环境中的 HTTP 代理。
        self.opener = build_opener(ProxyHandler({}))

    def request(self, method, path, data=None, form=False):
        body = None
        headers = {}
        if data is not None:
            body = (urlencode(data) if form else json.dumps(data)).encode('utf-8')
            headers['Content-Type'] = ('application/x-www-form-urlencoded' if form else 'application/json')
        req = Request(self.base + path, body, headers, method=method)
        try:
            with self.opener.open(req, timeout=5) as response:
                return response.read().decode('utf-8')
        except HTTPError as error:
            # 不把上游响应、请求头或包含 PIN 的请求体写入错误和日志。
            if self.report_errors:
                try:
                    message = json.loads(error.read().decode('utf-8')).get('error')
                except (ValueError, UnicodeError):
                    message = None
                if isinstance(message, str):
                    raise LoginError(message) from None
            raise LoginError('服务拒绝请求（HTTP %s）' % error.code) from None
        except (URLError, TimeoutError, OSError):
            raise LoginError('服务连接失败；本次登录已阻止，不切换模拟模式') from None

    def json(self, method, path, data=None, form=False):
        try:
            return json.loads(self.request(method, path, data, form))
        except (ValueError, UnicodeError):
            raise LoginError('服务返回了无效 JSON；本次登录已阻止') from None


class UkeyHelper:
    """严格沿用现有网页 JS 的助手路径、表单字段及响应字段。"""
    def __init__(self, base_url):
        if urlsplit(base_url).hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('PIN 只能发送到本机 UKey 助手')
        self.http = Http(base_url)

    def device(self):
        info = self.http.json('POST', '/sys/getDevInfo', {}, form=True)
        if not isinstance(info, dict) or info.get('code') != 200 or not info.get('SerialNumber'):
            raise LoginError('未识别到 UKey，请插入设备并检查助手')
        return info['SerialNumber']

    def certificate(self):
        # 此只读路径已从当前助手可执行文件的路由字符串及实际响应核实。
        info = self.http.json('POST', '/sys/getCertinfo', {}, form=True)
        if not isinstance(info, dict) or info.get('code') != 200 or not isinstance(info.get('Certinfo'), str):
            raise LoginError('无法从助手读取签名证书')
        try:
            return base64.b64decode(info['Certinfo'], validate=True)
        except (ValueError, binascii.Error):
            raise LoginError('助手返回的证书不是有效 Base64') from None

    def sign(self, pin, original_text, serial_number):
        result = self.http.json('POST', '/sys/verifyPin', {'pin': pin}, form=True)
        if not isinstance(result, dict) or result.get('code') != 200:
            raise LoginError('PIN 验证失败；已停止，不自动重试')
        if self.device() != serial_number:
            raise LoginError('设备已改变，请重新发起登录')
        # 对齐 JavaScript String.length（UTF-16 code units），而不是 UTF-8 字节数。
        result = self.http.json('POST', '/sys/signwithpid', {
            'plainData': original_text,
            'plainDataLen': len(original_text.encode('utf-16-le')) // 2,
        }, form=True)
        if not isinstance(result, dict) or result.get('code') != 200 or not result.get('signData'):
            raise LoginError('UKey 签名失败；本次登录已阻止')
        return result['signData']


class MockPlatform:
    """管理配置和验签替身；HMAC 仅用于模拟完整性，不是硬件 SM2。"""
    def __init__(self, key):
        self.key = key
        self.bindings = {'alice': 'MOCK-KEY-001', 'bob': 'MOCK-KEY-002'}

    def challenge(self, username, serial):
        if self.bindings.get(username) != serial:
            raise LoginError('模拟平台：业务账号与设备未绑定')
        return secrets.token_urlsafe(32)

    def verify(self, username, serial, original_text, signature):
        expected = hmac.new(self.key, original_text.encode(), hashlib.sha256).hexdigest()
        return self.bindings.get(username) == serial and hmac.compare_digest(expected, signature)


class NmrPlatform:
    """适配已发布的 NMR 实例；不伪造管理平台发布成功。"""
    def __init__(self, base_url):
        self.http = Http(base_url)

    def challenge(self, username, serial):
        rule = self.http.json('GET', '/verifyUser?' + urlencode({'username': username}))
        # 这里仅实验强制 UKey 登录；false 不能区分豁免和缺配置，不作为放行依据。
        if rule is not True:
            raise LoginError('NMR 未确认账号需要 UKey；请检查发布配置与绑定，不予放行')
        text = self.http.request('GET', '/genRandom?' + urlencode({'serialNumber': serial}))
        if not text.strip() or text.strip() in ('null', 'false'):
            raise LoginError('NMR 未返回有效随机原文')
        return text

    def verify(self, username, serial, original_text, signature):
        result = self.http.request('POST', '/verifySign', {
            'plainText': original_text, 'signResult': signature,
            'originalText': original_text, 'signature': signature,
            'serialNumber': serial, 'username': username,
        })
        return result.strip() == 'true'
