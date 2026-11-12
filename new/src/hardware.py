"""真实设备 + 本地应用规则：复用原 JAR 的 BC 库独立验签，不伪造 NMR 发布。"""
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import zipfile

from adapters import LoginError

ROOT = Path(__file__).resolve().parents[1]


class HardwareVerifier:
    def __init__(self, certificate, jar=None, java_home=None):
        home = java_home or os.environ.get('JAVA_HOME')
        suffix = '.exe' if os.name == 'nt' else ''
        self.java = str(Path(home) / 'bin' / ('java' + suffix)) if home else shutil.which('java')
        javac = str(Path(home) / 'bin' / ('javac' + suffix)) if home else shutil.which('javac')
        if not self.java or not javac:
            raise LoginError('独立验签需要已有 JDK（支持 Java 8），请设置 JAVA_HOME')
        work = ROOT / '.runtime' / 'hardware'
        work.mkdir(parents=True, exist_ok=True)
        library = work / 'bcprov-jdk15on-1.69.jar'
        # 仅读取原厂 JAR，在 new/.runtime 中展开其中实际已有的密码库。
        source = Path(jar) if jar else ROOT.parent / 'web-plugin' / 'ym-login-plug-1.1.5.jar'
        with zipfile.ZipFile(source) as archive:
            library.write_bytes(archive.read('BOOT-INF/lib/bcprov-jdk15on-1.69.jar'))
        self.cert_file = work / 'signing-certificate.cer'
        self.cert_file.write_bytes(certificate)
        self.classpath = os.pathsep.join([str(work), str(library)])
        compile_result = subprocess.run([javac, '-encoding', 'UTF-8', '-source', '8', '-target', '8',
            '-cp', str(library), '-d', str(work), str(ROOT / 'src/java/HardwareVerifier.java')],
            capture_output=True, timeout=30)
        if compile_result.returncode:
            raise LoginError('独立验签程序编译失败，请检查 Java 工具链')
        self.metadata = json.loads(self._call('inspect').stdout)

    def _call(self, action, payload=None):
        result = subprocess.run([self.java, '-Xms16m', '-Xmx96m', '-cp', self.classpath,
            'HardwareVerifier', action, str(self.cert_file)], input=payload,
            capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise LoginError('独立 SM2 验签程序失败（可能是证书有效期、签名格式或算法不匹配）')
        return result

    def verify(self, original_text, signature):
        # 原文和公开签名从 stdin 传给子进程，不放到命令行或日志中。
        payload = base64.b64encode(original_text.encode()).decode() + '\n' + signature + '\n'
        return self._call('verify', payload).stdout.strip() == 'true'

    def self_test(self):
        return json.loads(self._call('self-test').stdout)


class LocalHardwarePlatform:
    def __init__(self, helper, jar=None, java_home=None):
        self.helper = helper
        self.serial = helper.device()
        self.certificate = helper.certificate()
        self.verifier = HardwareVerifier(self.certificate, jar, java_home)
        self.last_verification = None
        self.negative_checks = None

    def challenge(self, username, serial):
        if username != 'alice' or serial != self.serial:
            raise LoginError('本地测试规则：仅 alice 与本次读取的真实设备绑定')
        return secrets.token_urlsafe(32)

    def verify(self, username, serial, original_text, signature):
        if username != 'alice' or serial != self.serial or self.helper.certificate() != self.certificate:
            raise LoginError('账号、设备或签名证书与本次绑定不一致')
        verified = self.verifier.verify(original_text, signature)
        self.last_verification = verified
        if verified:
            # 离线负向检查不消耗设备 PIN 次数、不再次签名。
            changed = self.verifier.verify(original_text + '-tampered', signature)
            self.negative_checks = {'changed_original_rejected': not changed}
            if changed:
                raise LoginError('篡改原文未被拒绝，停止业务登录')
        return verified

    def summary(self):
        return {'mode': 'hardware-local', 'management_configuration': 'local-test-rule',
                'physical_device_detected': True, 'certificate_read_from_helper': True,
                'jar_crypto_library_used': 'bcprov-jdk15on-1.69',
                'certificate': self.verifier.metadata,
                'real_signature_verified': self.last_verification,
                'negative_checks': self.negative_checks,
                'certificate_trust': 'exact certificate pinned for this test; CA chain not validated',
                'nmr_publication_complete': False}
