"""不访问真实管理系统或真实 PIN；通过 HTTP/TCP 验证新登录链路。"""
import json
from pathlib import Path
import socket
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from adapters import Http, LoginError, NmrPlatform, UkeyHelper
from runtime import Runtime
from service import serve, stop


class DesktopLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = Runtime('mock')

    @classmethod
    def tearDownClass(cls):
        cls.runtime.close()

    def setUp(self):
        self.r = self.runtime
        self.flow = self.r.workflow
        self.api = self.flow.api
        self.r.helper_server.present = True
        self.r.helper_server.serial = 'MOCK-KEY-001'
        self.r.helper_server.unlocked = False
        self.r.broker.pending.clear()
        self.r.broker.grants.clear()
        self.before = self.r.business.attempts

    def attempt(self):
        return self.flow.prepare('alice')

    def proof(self, attempt):
        signature = self.r.helper.sign('123456', attempt['original_text'], attempt['serial_number'])
        return self.api.json('POST', '/login/prove', {'attempt_id': attempt['attempt_id'], 'signature': signature})['grant']

    def business(self, grant, user='alice', app='mock-app', password='demo-password'):
        return self.api.json('POST', '/business/login', {'app_id': app, 'username': user, 'password': password, 'grant': grant})

    def assert_not_submitted(self):
        self.assertEqual(self.r.business.attempts, self.before)

    def test_login_is_paused_before_pin_and_proof(self):
        self.attempt()
        self.assert_not_submitted()

    def test_correct_pin_proof_and_business_password_succeed(self):
        result = self.flow.finish(self.attempt(), '123456', 'demo-password')
        self.assertEqual(result, {'ok': True, 'user': 'alice'})
        self.assertEqual(self.r.business.attempts, self.before + 1)

    def test_cancel_pin_never_submits_business_login(self):
        attempt = self.attempt()
        self.assertTrue(self.flow.finish(attempt, None, 'demo-password')['cancelled'])
        self.assertNotIn(attempt['attempt_id'], self.r.broker.pending)
        self.assert_not_submitted()

    def test_wrong_pin_never_submits_or_keeps_challenge(self):
        attempt = self.attempt()
        with self.assertRaisesRegex(LoginError, 'PIN'):
            self.flow.finish(attempt, 'wrong-mock-pin', 'demo-password')
        self.assertNotIn(attempt['attempt_id'], self.r.broker.pending)
        self.assert_not_submitted()

    def test_no_device_never_submits(self):
        self.r.helper_server.present = False
        with self.assertRaises(LoginError):
            self.attempt()
        self.assert_not_submitted()

    def test_device_change_after_challenge_never_submits(self):
        attempt = self.attempt()
        self.r.helper_server.serial = 'MOCK-KEY-002'
        with self.assertRaisesRegex(LoginError, '设备已改变'):
            self.flow.finish(attempt, '123456', 'demo-password')
        self.assert_not_submitted()

    def test_unbound_business_user_is_rejected(self):
        with self.assertRaises(LoginError):
            self.flow.prepare('bob')
        self.assert_not_submitted()

    def test_wrong_app_is_rejected(self):
        with self.assertRaises(LoginError):
            self.api.json('POST', '/login/begin', {'app_id': 'another-app', 'username': 'alice', 'serial_number': 'MOCK-KEY-001'})
        self.assert_not_submitted()

    def test_tampered_signature_is_rejected(self):
        attempt = self.attempt()
        with self.assertRaises(LoginError):
            self.api.json('POST', '/login/prove', {'attempt_id': attempt['attempt_id'], 'signature': 'tampered'})
        self.assert_not_submitted()

    def test_proof_cannot_be_replayed(self):
        attempt = self.attempt()
        self.proof(attempt)
        with self.assertRaises(LoginError):
            self.proof(attempt)
        self.assert_not_submitted()

    def test_signature_from_other_attempt_is_rejected(self):
        first, second = self.attempt(), self.attempt()
        signature = self.r.helper.sign('123456', first['original_text'], first['serial_number'])
        with self.assertRaises(LoginError):
            self.api.json('POST', '/login/prove', {'attempt_id': second['attempt_id'], 'signature': signature})
        self.assert_not_submitted()

    def test_expired_challenge_is_rejected(self):
        attempt = self.attempt()
        self.r.broker.pending[attempt['attempt_id']]['deadline'] = 0
        with self.assertRaises(LoginError):
            self.proof(attempt)
        self.assert_not_submitted()

    def test_no_grant_cannot_bypass_authentication(self):
        with self.assertRaises(LoginError):
            self.business('made-up-grant')
        self.assert_not_submitted()

    def test_grant_cannot_login_as_other_user(self):
        grant = self.proof(self.attempt())
        with self.assertRaises(LoginError):
            self.business(grant, user='bob')
        self.assert_not_submitted()

    def test_grant_cannot_be_used_for_other_app(self):
        grant = self.proof(self.attempt())
        with self.assertRaises(LoginError):
            self.business(grant, app='other')
        self.assert_not_submitted()

    def test_grant_cannot_be_used_twice(self):
        grant = self.proof(self.attempt())
        self.business(grant)
        with self.assertRaises(LoginError):
            self.business(grant)
        self.assertEqual(self.r.business.attempts, self.before + 1)

    def test_expired_grant_is_rejected(self):
        grant = self.proof(self.attempt())
        self.r.broker.grants[grant]['deadline'] = 0
        with self.assertRaises(LoginError):
            self.business(grant)
        self.assert_not_submitted()

    def test_cancellation_revokes_an_already_issued_grant(self):
        attempt = self.attempt()
        grant = self.proof(attempt)
        self.flow.cancel(attempt)
        with self.assertRaises(LoginError):
            self.business(grant)
        self.assert_not_submitted()

    def test_business_still_checks_password_after_authentication(self):
        with self.assertRaisesRegex(LoginError, '业务账号密码'):
            self.flow.finish(self.attempt(), '123456', 'wrong-business-password')
        self.assertEqual(self.r.business.attempts, self.before + 1)

    def test_utf16_length_matches_web_helper_contract(self):
        # 包含代理对的原文；签名与验签仍须使用同一原文。
        attempt = self.attempt()
        original = '中文挑战\U0001f511'
        self.r.broker.pending[attempt['attempt_id']]['original_text'] = original
        attempt['original_text'] = original
        self.assertTrue(self.flow.finish(attempt, '123456', 'demo-password')['ok'])

    def test_extra_fields_are_rejected_at_api_boundary(self):
        with self.assertRaises(LoginError):
            self.api.json('POST', '/login/prove', {'attempt_id': 'x', 'signature': 'x', 'username': 'bob'})
        self.assert_not_submitted()

    def test_pin_not_sent_to_broker_or_nmr(self):
        seen = []
        original = self.flow.api.json
        def record(method, path, data=None, form=False):
            seen.append((path, dict(data)))
            return original(method, path, data, form)
        self.flow.api.json = record
        try:
            self.flow.finish(self.attempt(), '123456', 'demo-password')
        finally:
            self.flow.api.json = original
        self.assertTrue(seen)
        self.assertNotIn('123456', json.dumps(seen))
        self.assertTrue(all('pin' not in data for _, data in seen))

    def test_known_gap_original_backend_is_directly_reachable(self):
        # 记录真实限制：这是样例入口实验，未部署操作系统级防绕行。
        with socket.create_connection(self.r.business.server_address, timeout=5) as connection:
            connection.sendall(b'{"username":"alice","password":"demo-password"}\n')
            with connection.makefile('rb') as f:
                self.assertTrue(json.loads(f.readline())['ok'])


class NmrFixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def handle_request(self):
        s = self.server
        path = urlsplit(self.path)
        body = None
        if self.command == 'POST':
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        s.calls.append((self.command, path.path, parse_qs(path.query), body))
        status = s.status
        value = {'/verifyUser': s.rule, '/genRandom': s.random_text, '/verifySign': s.proof}.get(path.path, 'invalid')
        payload = value.encode()
        self.send_response(status)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = handle_request
    do_POST = handle_request


class RealAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), NmrFixture)
        serve(cls.server)

    @classmethod
    def tearDownClass(cls):
        stop(cls.server)

    def setUp(self):
        self.server.calls = []
        self.server.status = 200
        self.server.rule = 'true'
        self.server.random_text = 'fixture-random-challenge'
        self.server.proof = 'true'
        self.platform = NmrPlatform('http://127.0.0.1:%d' % self.server.server_port)

    def test_real_adapter_paths_and_query_encoding_match_web_plugin(self):
        self.assertEqual(self.platform.challenge('a+b 用户', 'fixture-serial'), 'fixture-random-challenge')
        self.assertEqual(self.server.calls[0][:3], ('GET', '/verifyUser', {'username': ['a+b 用户']}))
        self.assertEqual(self.server.calls[1][:3], ('GET', '/genRandom', {'serialNumber': ['fixture-serial']}))

    def test_real_verify_body_matches_existing_js(self):
        self.assertTrue(self.platform.verify('alice', 'fixture-serial', 'text', 'signature'))
        self.assertEqual(self.server.calls[-1], ('POST', '/verifySign', {}, {
            'username': 'alice', 'serialNumber': 'fixture-serial',
            'plainText': 'text', 'originalText': 'text',
            'signResult': 'signature', 'signature': 'signature'}))

    def test_504_stops_login_without_mock_fallback(self):
        self.server.status = 504
        with self.assertRaisesRegex(LoginError, '504'):
            self.platform.challenge('alice', 'fixture-serial')
        self.assertEqual(len(self.server.calls), 1)

    def test_unpublished_false_does_not_bypass_ukey(self):
        self.server.rule = 'false'
        with self.assertRaises(LoginError):
            self.platform.challenge('alice', 'fixture-serial')
        self.assertEqual(len(self.server.calls), 1)

    def test_malformed_account_rule_is_not_treated_as_success(self):
        self.server.rule = '{"code":200}'
        with self.assertRaises(LoginError):
            self.platform.challenge('alice', 'fixture-serial')

    def test_empty_random_is_rejected(self):
        self.server.random_text = ''
        with self.assertRaises(LoginError):
            self.platform.challenge('alice', 'fixture-serial')

    def test_false_verify_result_is_rejected(self):
        self.server.proof = 'false'
        self.assertFalse(self.platform.verify('alice', 'fixture-serial', 'text', 'signature'))

    def test_real_nmr_failure_blocks_business_at_gateway(self):
        with Runtime('mock') as r:
            r.broker.platform = self.platform
            self.server.status = 504
            with self.assertRaises(LoginError):
                r.workflow.prepare('alice')
            self.assertEqual(r.business.attempts, 0)

    def test_nmr_mode_uses_external_contract_services_not_internal_mock(self):
        # 外部助手替身仅由测试启动；Runtime(nmr) 本身不会创建模拟助手。
        from mock_helper import MockHelper
        helper = serve(MockHelper(b'contract-fixture-key'))
        try:
            with Runtime('nmr', 'http://127.0.0.1:%d' % self.server.server_port,
                         'http://127.0.0.1:%d' % helper.server_port, 'fixture-real-app') as r:
                self.assertIsNone(r.helper_server)
                self.assertIsInstance(r.broker.platform, NmrPlatform)
                result = r.workflow.finish(r.workflow.prepare('alice'), '123456', 'demo-password')
                self.assertTrue(result['ok'])
                self.assertEqual([c[1] for c in self.server.calls], ['/verifyUser', '/genRandom', '/verifySign'])
                body = self.server.calls[-1][3]
                self.assertNotIn('pin', body)
                self.assertEqual(body['originalText'], self.server.random_text)
        finally:
            stop(helper)

    def test_nmr_proof_504_never_issues_business_grant(self):
        with Runtime('mock') as r:
            r.broker.platform = self.platform
            attempt = r.workflow.prepare('alice')
            self.server.status = 504
            with self.assertRaises(LoginError):
                r.workflow.finish(attempt, '123456', 'demo-password')
            self.assertFalse(r.broker.grants)
            self.assertEqual(r.business.attempts, 0)

    def test_nmr_false_proof_never_issues_business_grant(self):
        with Runtime('mock') as r:
            r.broker.platform = self.platform
            attempt = r.workflow.prepare('alice')
            self.server.proof = 'false'
            with self.assertRaises(LoginError):
                r.workflow.finish(attempt, '123456', 'demo-password')
            self.assertEqual(r.business.attempts, 0)

    def test_connection_refused_has_no_fallback(self):
        with socket.socket() as closed:
            closed.bind(('127.0.0.1', 0))
            port = closed.getsockname()[1]
        with self.assertRaises(LoginError):
            NmrPlatform('http://127.0.0.1:%d' % port).challenge('alice', 'fixture-serial')

    def test_real_mode_requires_explicit_published_target(self):
        with self.assertRaises(ValueError):
            Runtime('nmr')

    def test_pin_is_never_sent_to_remote_helper(self):
        with self.assertRaises(ValueError):
            UkeyHelper('http://192.0.2.1:38080')


if __name__ == '__main__':
    unittest.main()
