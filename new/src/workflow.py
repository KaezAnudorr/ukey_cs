"""桌面触发器与 UI 共用的登录流程；PIN 不发送到 Broker/NMR。"""
from adapters import Http, LoginError


class Workflow:
    def __init__(self, api_url, helper, app_id):
        self.api = Http(api_url, report_errors=True)
        self.helper = helper
        self.app_id = app_id

    def prepare(self, username):
        serial = self.helper.device()
        return self.api.json('POST', '/login/begin', {
            'app_id': self.app_id, 'username': username, 'serial_number': serial})

    def cancel(self, attempt):
        self.api.json('POST', '/login/cancel', {'attempt_id': attempt['attempt_id']})

    def finish(self, attempt, pin, password):
        if pin is None:
            self.cancel(attempt)
            return {'ok': False, 'cancelled': True}
        try:
            signature = self.helper.sign(pin, attempt['original_text'], attempt['serial_number'])
            proof = self.api.json('POST', '/login/prove', {
                'attempt_id': attempt['attempt_id'], 'signature': signature})
            return self.api.json('POST', '/business/login', {
                'app_id': self.app_id, 'username': attempt['username'],
                'password': password, 'grant': proof['grant']})
        except LoginError:
            # 清理本次未完成认证；清理失败不覆盖原错误，也不恢复业务请求。
            try:
                self.cancel(attempt)
            except LoginError:
                pass
            raise
