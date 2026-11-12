"""只拥有本次实验创建的监听服务；不修改旧项目、不抢占固定端口。"""
import secrets
import datetime
import json
from pathlib import Path

from adapters import MockPlatform, NmrPlatform, UkeyHelper
from service import Api, Broker, Business, serve, stop
from workflow import Workflow


class Runtime:
    def __init__(self, mode, nmr_url=None, helper_url='http://127.0.0.1:38080', app_id=None, jar=None, java_home=None):
        if mode not in ('mock', 'nmr', 'hardware-local'):
            raise ValueError('模式必须为 mock、nmr 或 hardware-local')
        if mode == 'nmr' and (not nmr_url or not app_id):
            raise ValueError('真实适配需要明确指定 --nmr-url 和 --app-id，不使用默认应用')
        self.mode = mode
        self.app_id = app_id or ('hardware-local-test' if mode == 'hardware-local' else 'mock-app')
        self.services = []
        self.helper_server = None
        if mode == 'mock':
            from mock_helper import MockHelper
            key = secrets.token_bytes(32)
            platform = MockPlatform(key)
            self.helper_server = serve(MockHelper(key))
            self.services.append(self.helper_server)
            helper_url = 'http://127.0.0.1:%d' % self.helper_server.server_port
        elif mode == 'nmr':
            platform = NmrPlatform(nmr_url)
        self.helper = UkeyHelper(helper_url)
        if mode == 'hardware-local':
            from hardware import LocalHardwarePlatform
            platform = LocalHardwarePlatform(self.helper, jar, java_home)
        self.platform = platform
        # 所有模式都只连接新建的本机样例业务，不连接任何现网业务。
        self.business = serve(Business('demo-password'))
        self.services.append(self.business)
        self.broker = Broker(platform, self.app_id, self.business.server_address)
        self.api = serve(Api(self.broker))
        self.services.append(self.api)
        self.workflow = Workflow('http://127.0.0.1:%d' % self.api.server_port, self.helper, self.app_id)
        self.record_result('waiting_for_user_pin')

    def record_result(self, outcome):
        if self.mode == 'hardware-local':
            report = self.platform.summary()
            report.update({'outcome': outcome, 'business_attempts': self.business.attempts,
                           'checked_at': datetime.datetime.now().astimezone().isoformat()})
            path = Path(__file__).resolve().parents[1] / '.runtime/hardware/result.json'
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def close(self):
        for server in reversed(self.services):
            stop(server)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
