#!/usr/bin/env python3
"""Convert the legacy exact account/certificate mapping into reviewable policy fragments."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import ssl
import tempfile
import subprocess
from manage import toolchain


def convert(file, resource):
    config = json.loads(file.read_text(encoding='utf-8'))
    for rule in config.get('ruleDefineConfigs', []):
        if rule.get('ruleCode') == 'account_reg' and str(rule.get('ruleValue')) != '0':
            raise ValueError('Only explicit exact account mappings may be imported; review prefix/suffix rules manually.')
    if not resource or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in resource):
        raise ValueError('Invalid resource ID')
    grouped = {}
    _, keytool, env, _ = toolchain()
    for user in config.get('ukeyUsers', []):
        account = str(user.get('originUserKey', ''))
        if not account or any(c in account for c in ',\r\n=\\'):
            raise ValueError('Invalid or ambiguous business account')
        encoded = user.get('ukeyCert') or ''
        der = ssl.PEM_cert_to_DER_cert(encoded) if 'BEGIN CERTIFICATE' in encoded else base64.b64decode(encoded, validate=True)
        with tempfile.TemporaryDirectory(prefix='cs-ukey-cert-import-') as temp:
            cert = Path(temp) / 'public.cer'; cert.write_bytes(der)
            result = subprocess.run([keytool, '-printcert', '-file', str(cert)], env=env, capture_output=True)
            if result.returncode:
                raise ValueError('Invalid X.509 certificate; no policy written')
        fingerprint = hashlib.sha256(der).hexdigest()
        grouped.setdefault(fingerprint, set()).add(account)
    if not grouped:
        raise ValueError('No explicit UKey user certificates found')
    lines = ['# Review only. This does not establish CA trust or activate REAL-PILOT.']
    ids = []
    for index, (fingerprint, accounts) in enumerate(sorted(grouped.items()), 1):
        name = 'imported-' + str(index); ids.append(name)
        lines.extend([f'identity.{name}.fingerprint={fingerprint}', f'identity.{name}.resources={resource}',
                      f'identity.{name}.accounts={",".join(sorted(accounts))}'])
    return 'identity.ids=' + ','.join(ids) + '\n' + '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json_file', type=Path)
    parser.add_argument('--resource', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists; no file overwritten.')
    try:
        text = convert(args.json_file, args.resource)
        args.output.write_text(text, encoding='utf-8')
    except Exception as error:
        raise SystemExit('IMPORT REFUSED: ' + str(error))
    print('Reviewable policy fragment written; credentials and password-service settings were not imported.')
