"""仅模拟模式启动的助手替身；真实模式不会导入或启动此监听服务。"""
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


class MockHelper(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, key, pin='123456'):
        self.key = key
        self.pin = pin
        self.serial = 'MOCK-KEY-001'
        self.present = True
        self.unlocked = False
        super().__init__(('127.0.0.1', 0), MockHandler)


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        data = parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode())
        s = self.server
        result = {'code': 500}
        if s.present:
            if self.path == '/sys/getDevInfo':
                result = {'code': 200, 'SerialNumber': s.serial, 'Label': '模拟设备（不是 HaiKey）'}
            elif self.path == '/sys/verifyPin':
                s.unlocked = hmac.compare_digest(data.get('pin', [''])[0].encode(), s.pin.encode())
                result = {'code': 200 if s.unlocked else 500}
            elif self.path == '/sys/signwithpid' and s.unlocked:
                plain = data.get('plainData', [''])[0]
                length = data.get('plainDataLen', [''])[0]
                if length == str(len(plain.encode('utf-16-le')) // 2):
                    result = {'code': 200, 'signData': hmac.new(s.key, plain.encode(), hashlib.sha256).hexdigest()}
                s.unlocked = False
        payload = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
