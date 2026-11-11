"""只拥有本次实验创建的监听服务；不修改旧项目、不抢占固定端口。"""
import secrets

from adapters import MockPlatform, NmrPlatform, UkeyHelper
from service import Api, Broker, Business, serve, stop
from workflow import Workflow


class Runtime:
    def __init__(self, mode, nmr_url=None, helper_url='http://127.0.0.1:38080', app_id=None):
        if mode not in ('mock', 'nmr'):
            raise ValueError('模式必须为 mock 或 nmr')
        if mode == 'nmr' and (not nmr_url or not app_id):
            raise ValueError('真实适配需要明确指定 --nmr-url 和 --app-id，不使用默认应用')
        self.mode = mode
        self.app_id = app_id or 'mock-app'
        self.services = []
        self.helper_server = None
        if mode == 'mock':
            from mock_helper import MockHelper
            key = secrets.token_bytes(32)
            platform = MockPlatform(key)
            self.helper_server = serve(MockHelper(key))
            self.services.append(self.helper_server)
            helper_url = 'http://127.0.0.1:%d' % self.helper_server.server_port
        else:
            platform = NmrPlatform(nmr_url)
        self.helper = UkeyHelper(helper_url)
        # 两种模式都只连接新建的本机样例业务，不连接任何现网业务。
        self.business = serve(Business('demo-password'))
        self.services.append(self.business)
        self.broker = Broker(platform, self.app_id, self.business.server_address)
        self.api = serve(Api(self.broker))
        self.services.append(self.api)
        self.workflow = Workflow('http://127.0.0.1:%d' % self.api.server_port, self.helper, self.app_id)

    def close(self):
        for server in reversed(self.services):
            stop(server)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
