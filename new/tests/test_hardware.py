"""真实硬件路径的边界测试；不尝试设备 PIN，不替代实际硬件验收。"""
import base64
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from adapters import LoginError, UkeyHelper
from hardware import LocalHardwarePlatform


class CertificateAdapterTests(unittest.TestCase):
    def test_read_only_certificate_contract(self):
        helper = UkeyHelper('http://127.0.0.1:38080')
        helper.http = Mock()
        helper.http.json.return_value = {'code': 200, 'Certinfo': base64.b64encode(b'certificate-fixture').decode()}
        self.assertEqual(helper.certificate(), b'certificate-fixture')
        helper.http.json.assert_called_once_with('POST', '/sys/getCertinfo', {}, form=True)

    def test_certificate_error_is_rejected(self):
        helper = UkeyHelper('http://127.0.0.1:38080')
        helper.http = Mock()
        helper.http.json.return_value = {'code': 500}
        with self.assertRaises(LoginError):
            helper.certificate()

    def test_invalid_certificate_encoding_is_rejected(self):
        helper = UkeyHelper('http://127.0.0.1:38080')
        helper.http = Mock()
        helper.http.json.return_value = {'code': 200, 'Certinfo': 'not base64!'}
        with self.assertRaises(LoginError):
            helper.certificate()


class HardwareBindingTests(unittest.TestCase):
    def setUp(self):
        self.helper = Mock()
        self.helper.device.return_value = 'fixture-real-device'
        self.helper.certificate.return_value = b'fixture-certificate'
        with patch('hardware.HardwareVerifier') as verifier:
            self.platform = LocalHardwarePlatform(self.helper)
        self.verifier = self.platform.verifier
        self.verifier.metadata = {'certificate_valid_now': True}

    def test_local_rule_binds_user_to_real_device(self):
        self.assertTrue(self.platform.challenge('alice', 'fixture-real-device'))
        with self.assertRaises(LoginError):
            self.platform.challenge('bob', 'fixture-real-device')
        with self.assertRaises(LoginError):
            self.platform.challenge('alice', 'different-device')

    def test_changed_certificate_never_reaches_verifier(self):
        self.helper.certificate.return_value = b'changed-certificate'
        with self.assertRaises(LoginError):
            self.platform.verify('alice', 'fixture-real-device', 'challenge', 'fixture-signature')
        self.verifier.verify.assert_not_called()

    def test_invalid_signature_is_not_promoted_to_success(self):
        self.verifier.verify.return_value = False
        self.assertFalse(self.platform.verify('alice', 'fixture-real-device', 'challenge', 'fixture-signature'))
        self.assertFalse(self.platform.last_verification)
        self.assertIsNone(self.platform.negative_checks)

    def test_valid_signature_also_requires_tamper_rejection(self):
        self.verifier.verify.side_effect = [True, False]
        self.assertTrue(self.platform.verify('alice', 'fixture-real-device', 'challenge', 'fixture-signature'))
        self.assertTrue(self.platform.negative_checks['changed_original_rejected'])
        self.assertEqual(self.verifier.verify.call_count, 2)

    def test_verifier_failure_does_not_fall_back_to_mock(self):
        self.verifier.verify.side_effect = LoginError('verifier unavailable')
        with self.assertRaises(LoginError):
            self.platform.verify('alice', 'fixture-real-device', 'challenge', 'fixture-signature')
        self.assertIsNone(self.platform.last_verification)

    def test_summary_distinguishes_real_crypto_from_local_rule(self):
        report = self.platform.summary()
        self.assertEqual(report['management_configuration'], 'local-test-rule')
        self.assertIsNone(report['real_signature_verified'])
        self.assertFalse(report['nmr_publication_complete'])
        self.assertNotIn('fixture-real-device', str(report))
        self.assertNotIn('fixture-certificate', str(report))


if __name__ == '__main__':
    unittest.main()
