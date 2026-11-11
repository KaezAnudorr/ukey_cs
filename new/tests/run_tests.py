"""生成脱敏摘要；不保存 PIN、口令、签名或授权令牌。"""
import datetime
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {
    'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
    'successful': result.wasSuccessful(), 'physical_ukey_signing_tested': False,
    'management_mode': 'simulated; real NMR adapter tested against a local contract fixture',
    'gui_tested_by_this_runner': False,
    'known_gaps': ['Original sample business port remains directly reachable.',
                   'Local HTTP endpoints do not identify the OS process or user.',
                   'Mock HMAC is not SM2 and does not prove real UKey interoperability.'],
}
output = ROOT / '.runtime' / 'login-tests.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Report:', output)
sys.exit(0 if result.wasSuccessful() else 1)
