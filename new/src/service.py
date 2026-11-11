"""本机登录绑定实验：一次性挑战、一次性业务授权、独立 TCP 样例业务。"""
import hmac
import json
import secrets
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from adapters import LoginError


class Business(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, password):
        self.password = password
        self.attempts = 0
        self.guard = threading.Lock()
        super().__init__(('127.0.0.1', 0), BusinessHandler)


class BusinessHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        data = json.loads(self.rfile.readline(8192))
        with self.server.guard:
            self.server.attempts += 1
        good = data.get('username') in ('alice', 'bob') and hmac.compare_digest(
            str(data.get('password', '')).encode(), self.server.password.encode())
        result = {'ok': good, 'user': data.get('username') if good else None}
        self.wfile.write(json.dumps(result).encode() + b'\n')


class Broker:
    def __init__(self, platform, app_id, business_address, ttl=60, clock=time.monotonic):
        self.platform = platform
        self.app_id = app_id
        self.business_address = business_address
        self.ttl = ttl
        self.clock = clock
        self.pending = {}
        self.grants = {}
        self.lock = threading.Lock()

    def _expire(self):
        now = self.clock()
        self.pending = {k: v for k, v in self.pending.items() if v['deadline'] > now}
        self.grants = {k: v for k, v in self.grants.items() if v['deadline'] > now}

    def begin(self, app_id, username, serial_number):
        if app_id != self.app_id:
            raise LoginError('应用不匹配')
        original = self.platform.challenge(username, serial_number)
        attempt_id = secrets.token_urlsafe(24)
        attempt = {'attempt_id': attempt_id, 'app_id': app_id, 'username': username,
                   'serial_number': serial_number, 'original_text': original,
                   'deadline': self.clock() + self.ttl}
        with self.lock:
            self._expire()
            self.pending[attempt_id] = attempt
        return {k: v for k, v in attempt.items() if k != 'deadline'} | {'expires_in': self.ttl}

    def prove(self, attempt_id, signature):
        # 锁内取出，一次证明只允许一次尝试；验签失败或上游不可用也不会放回。
        with self.lock:
            self._expire()
            attempt = self.pending.pop(attempt_id, None)
            if attempt is None:
                raise LoginError('认证已取消、过期或使用，请重新登录')
            if not self.platform.verify(attempt['username'], attempt['serial_number'],
                                        attempt['original_text'], signature):
                raise LoginError('服务端验签失败')
            if attempt['deadline'] <= self.clock():
                raise LoginError('认证已过期')
            token = secrets.token_urlsafe(32)
            self.grants[token] = attempt
        return {'grant': token}

    def cancel(self, attempt_id):
        with self.lock:
            self.pending.pop(attempt_id, None)
            self.grants = {k: v for k, v in self.grants.items() if v['attempt_id'] != attempt_id}
        return {'cancelled': True}

    def login(self, app_id, username, password, grant):
        with self.lock:
            self._expire()
            attempt = self.grants.pop(grant, None)
        if attempt is None or attempt['app_id'] != app_id or attempt['username'] != username:
            raise LoginError('缺少有效的本次业务登录授权')
        with socket.create_connection(self.business_address, timeout=5) as connection:
            connection.sendall(json.dumps({'username': username, 'password': password}).encode() + b'\n')
            with connection.makefile('rb') as stream:
                result = json.loads(stream.readline(8192))
        if not result['ok']:
            raise LoginError('UKey 认证通过，但原业务账号密码验证失败')
        return result


class Api(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, broker):
        self.broker = broker
        super().__init__(('127.0.0.1', 0), ApiHandler)


class ApiHandler(BaseHTTPRequestHandler):
    # 此接口用于本机桌面实验；不返回 CORS 放行头，不记录请求体或认证凭据。
    def log_message(self, *_):
        pass

    def do_POST(self):
        routes = {'/login/begin': (self.server.broker.begin, ('app_id', 'username', 'serial_number')),
                  '/login/prove': (self.server.broker.prove, ('attempt_id', 'signature')),
                  '/login/cancel': (self.server.broker.cancel, ('attempt_id',)),
                  '/business/login': (self.server.broker.login, ('app_id', 'username', 'password', 'grant'))}
        status = 200
        try:
            if self.path not in routes:
                raise ValueError('未知接口')
            size = int(self.headers.get('Content-Length', '0'))
            if self.headers.get_content_type() != 'application/json' or not 0 < size <= 16384:
                raise ValueError('需要 JSON 请求体，最大 16 KiB')
            data = json.loads(self.rfile.read(size))
            function, names = routes[self.path]
            if not isinstance(data, dict) or set(data) != set(names) or any(
                    not isinstance(data[n], str) or not 0 < len(data[n]) <= 8192 for n in names):
                raise ValueError('请求字段无效')
            result = function(**data)
        except (ValueError, UnicodeError):
            status, result = 400, {'error': '请求格式或字段无效'}
        except LoginError as error:
            status, result = 403, {'error': str(error)}
        except (OSError, KeyError, TypeError):
            status, result = 503, {'error': '上游服务异常；本次登录已阻止'}
        payload = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop(server):
    server.shutdown()
    server.server_close()
