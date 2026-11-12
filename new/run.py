"""从项目根目录执行：python -B new/run.py --mode mock"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from adapters import UkeyHelper
from runtime import Runtime


def main():
    p = argparse.ArgumentParser(description='C/S UKey 桌面登录实验；不修改旧项目')
    p.add_argument('--mode', choices=['mock', 'nmr', 'hardware-local'], required=True)
    p.add_argument('--helper-url', default='http://127.0.0.1:38080')
    p.add_argument('--nmr-url')
    p.add_argument('--app-id')
    p.add_argument('--jar', help='只读使用原网页插件 JAR 中已有的 BC 密码库')
    p.add_argument('--java-home', help='独立验签的已有 JDK 路径，支持 Java 8')
    p.add_argument('--check-hardware', action='store_true', help='只读证书检查及独立验签自测，不输入 PIN')
    p.add_argument('--smoke', action='store_true', help='仅模拟模式自动运行，无真实 PIN')
    p.add_argument('--probe-helper', action='store_true', help='只读探测真实助手，不验证 PIN、不签名')
    args = p.parse_args()
    if args.probe_helper:
        if args.mode != 'nmr':
            p.error('真实助手探测需要 --mode nmr')
        UkeyHelper(args.helper_url).device()
        print('真实助手响应成功，设备已识别；未执行 PIN 验证或签名。')
        return
    if args.smoke and args.mode != 'mock':
        p.error('自动 smoke 只允许全模拟模式，禁止自动输入真实 PIN')
    if args.check_hardware and args.mode != 'hardware-local':
        p.error('--check-hardware 需要 --mode hardware-local')
    with Runtime(args.mode, args.nmr_url, args.helper_url, args.app_id, args.jar, args.java_home) as runtime:
        if args.check_hardware:
            print(json.dumps({'certificate': runtime.platform.verifier.metadata,
                              'verifier_self_test': runtime.platform.verifier.self_test(),
                              'hardware_signing_performed': False}, ensure_ascii=False))
        elif args.smoke:
            attempt = runtime.workflow.prepare('alice')
            result = runtime.workflow.finish(attempt, '123456', 'demo-password')
            print(json.dumps({'mode': args.mode, 'physical_ukey': False, 'business_login': result}, ensure_ascii=False))
        else:
            from desktop import Desktop
            Desktop(runtime).run()


if __name__ == '__main__':
    main()
