#!/usr/bin/env python3
"""Portable DEMO build, local PKI generation, launch, diagnosis and packaging."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ['common', 'access-server', 'desktop-agent', 'lab']
VERSION = '0.2.0-demo'


def toolchain():
    record = ROOT.parent / 'validation/web-ukey-local/toolchain.json'
    saved = json.loads(record.read_text()) if record.exists() else {}
    java_home = os.environ.get('JAVA_HOME') or saved.get('java_home')
    suffix = '.exe' if os.name == 'nt' else ''
    java = str(Path(java_home) / 'bin' / ('java' + suffix)) if java_home else shutil.which('java')
    keytool = str(Path(java_home) / 'bin' / ('keytool' + suffix)) if java_home else shutil.which('keytool')
    if not java or not keytool:
        raise RuntimeError('JDK 17+ is required. Set JAVA_HOME; no global installation is performed.')
    env = dict(os.environ)
    if java_home:
        env['JAVA_HOME'] = java_home
        env['PATH'] = str(Path(java_home) / 'bin') + os.pathsep + env.get('PATH', '')
    return java, keytool, env, saved


def write_properties(path, values):
    path.write_text('\n'.join(f'{k}={str(v).replace(chr(92), "/")}' for k, v in values.items()) + '\n', encoding='utf-8')


def initialize(directory):
    directory = directory.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise RuntimeError('Demo directory is not empty; choose a new directory. Existing keys are never overwritten.')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / '.demo-owned').write_text('Generated test keys. Not real UKey credentials.\n')
    _, keytool, env, _ = toolchain()
    password = secrets.token_hex(24)
    env['CS_UKEY_STORE_PASSWORD'] = password
    secret_file = directory / 'secrets.properties'
    write_properties(secret_file, {'store.password': password, 'business.password': secrets.token_hex(16)})
    secret_file.chmod(0o600)
    log = directory / 'keytool.log'

    def key(*args):
        command = [keytool, *map(str, args)]
        with log.open('a') as output:
            result = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Test certificate generation failed; see keytool.log (no real credentials involved)')

    def store(file):
        return ['-keystore', str(directory / file), '-storetype', 'PKCS12', '-storepass:env', 'CS_UKEY_STORE_PASSWORD']

    key('-genkeypair', '-alias', 'ca', '-keyalg', 'RSA', '-keysize', '2048', '-dname', 'CN=CS UKey DEMO CA',
        '-validity', '30', '-ext', 'bc:c=ca:true', '-ext', 'ku=keyCertSign,cRLSign', *store('ca.p12'), '-noprompt')
    key('-exportcert', '-alias', 'ca', '-rfc', '-file', directory / 'ca.pem', *store('ca.p12'))
    key('-importcert', '-alias', 'ca', '-file', directory / 'ca.pem', *store('trust.p12'), '-noprompt')
    fingerprints = {}
    for name in ['server', 'server-wronghost', 'alice', 'bob', 'unmapped', 'expired']:
        key('-genkeypair', '-alias', name, '-keyalg', 'RSA', '-keysize', '2048', '-dname', 'CN=DEMO ' + name,
            '-validity', '30', *store(name + '.p12'), '-noprompt')
        key('-certreq', '-alias', name, '-file', directory / (name + '.csr'), *store(name + '.p12'))
        extensions = (['-ext', 'eku=serverAuth', '-ext', 'san=' + ('dns:wrong.invalid' if name == 'server-wronghost' else 'dns:localhost,ip:127.0.0.1')]
                      if name.startswith('server') else ['-ext', 'eku=clientAuth'])
        validity = ['-startdate', '-10d', '-validity', '1'] if name == 'expired' else ['-validity', '20']
        key('-gencert', '-alias', 'ca', '-infile', directory / (name + '.csr'), '-outfile', directory / (name + '.cer'),
            *validity, '-ext', 'ku=digitalSignature,keyEncipherment', *extensions, *store('ca.p12'))
        key('-importcert', '-alias', 'ca', '-file', directory / 'ca.pem', *store(name + '.p12'), '-noprompt')
        key('-importcert', '-alias', name, '-file', directory / (name + '.cer'), *store(name + '.p12'), '-noprompt')
        fingerprints[name] = hashlib.sha256((directory / (name + '.cer')).read_bytes()).hexdigest()
    key('-genkeypair', '-alias', 'untrusted', '-keyalg', 'RSA', '-keysize', '2048', '-dname', 'CN=Untrusted DEMO',
        '-validity', '20', '-ext', 'eku=clientAuth', *store('untrusted.p12'), '-noprompt')
    for keyfile in directory.glob('*.p12'):
        keyfile.chmod(0o600)
    server = {'mode': 'DEMO', 'server.host': '127.0.0.1', 'api.port': 19443, 'gateway.port': 19444,
              'session.ttl.seconds': 60, 'tls.keystore': 'server.p12', 'tls.truststore': 'trust.p12',
              'secrets.file': 'secrets.properties', 'audit.file': 'audit.jsonl', 'identity.ids': 'alice,bob', 'resource.ids': 'sample',
              'resource.sample.authority': 'sample-business:443', 'resource.sample.host': '127.0.0.1',
              'resource.sample.port': 19510, 'resource.sample.adapter': 'sample-line-login'}
    for name in ['alice', 'bob']:
        server.update({f'identity.{name}.fingerprint': fingerprints[name], f'identity.{name}.resources': 'sample', f'identity.{name}.accounts': name})
    write_properties(directory / 'server.properties', server)
    for name in ['alice', 'bob', 'unmapped', 'untrusted', 'expired']:
        write_properties(directory / (name + '-agent.properties'), {
            'mode': 'DEMO', 'identity.provider': 'demo-software-pkcs12', 'server.host': 'localhost',
            'api.port': 19443, 'gateway.port': 19444, 'agent.host': '127.0.0.1', 'agent.port': 19500 if name == 'alice' else 19501,
            'resource.id': 'sample', 'resource.authority': 'sample-business:443', 'tls.keystore': name + '.p12',
            'tls.truststore': 'trust.p12', 'secrets.file': 'secrets.properties'})
    write_properties(directory / 'business.properties', {'mode': 'DEMO', 'business.host': '127.0.0.1', 'business.port': 19510,
                                                        'business.accounts': 'alice,bob', 'secrets.file': 'secrets.properties'})
    write_properties(directory / 'client.properties', {'mode': 'DEMO', 'client.host': '127.0.0.1', 'client.port': 19500,
                                                      'business.user': 'alice', 'secrets.file': 'secrets.properties'})
    write_properties(directory / 'real-pilot.properties', {'mode': 'REAL-PILOT'})
    (directory / 'manifest.json').write_text(json.dumps({'mode': 'DEMO', 'physical_ukey': False, 'gm_sm2': False,
                                                        'certificate_fingerprints': fingerprints}, indent=2) + '\n')
    print('Generated local DEMO keys/configuration:', directory)


def maven(skip_tests=False):
    _, _, env, saved = toolchain()
    executable = shutil.which('mvn', path=env['PATH'])
    if not executable and saved.get('maven_home'):
        executable = str(Path(saved['maven_home']) / 'bin' / ('mvn.cmd' if os.name == 'nt' else 'mvn'))
    if not executable:
        raise RuntimeError('Maven 3.9+ is required for source builds. A binary bundle does not require Maven.')
    command = [executable, '-B', '-ntp']
    if saved.get('maven_repository'):
        command.append('-Dmaven.repo.local=' + saved['maven_repository'])
    if skip_tests:
        command.append('-DskipTests')
    command.append('package')
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def classpath():
    jars = sorted((ROOT / 'lib').glob('*.jar')) if (ROOT / 'lib').exists() else [ROOT / name / 'target' / (name + '-' + VERSION + '.jar') for name in MODULES]
    if not jars or not all(jar.exists() for jar in jars):
        raise RuntimeError('Build source first, or use the complete binary bundle')
    return os.pathsep.join(map(str, jars))


MAINS = {'server': 'cn.ukey.pilot.server.ServerMain', 'agent': 'cn.ukey.pilot.agent.AgentMain',
         'business': 'cn.ukey.pilot.lab.BusinessServerMain', 'client': 'cn.ukey.pilot.lab.SampleClientMain',
         'probe': 'cn.ukey.pilot.lab.ProbeMain'}


def java_command(role, config, gui=False):
    java, _, env, _ = toolchain()
    command = [java, '-cp', classpath(), MAINS[role], '--config', str(config.resolve())]
    if gui:
        command.append('--gui')
    return command, env


def occupied(port):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def smoke(directory):
    if any(occupied(port) for port in [19443, 19444, 19500, 19510]):
        raise RuntimeError('A DEMO port is already in use. Existing processes are not stopped.')
    children = []
    output = directory / 'smoke-result.json'
    try:
        for role, filename, port in [('business', 'business.properties', 19510), ('server', 'server.properties', 19443), ('agent', 'alice-agent.properties', 19500)]:
            command, env = java_command(role, directory / filename)
            log = (directory / (role + '.log')).open('w')
            child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            children.append((child, log))
            end = time.monotonic() + 20
            while not occupied(port):
                if child.poll() is not None or time.monotonic() > end:
                    raise RuntimeError(role + ' failed to start; inspect its log')
                time.sleep(.1)
        command, env = java_command('client', directory / 'client.properties')
        result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=15)
        success = result.returncode == 0 and 'USER alice' in result.stdout and 'Native C/S flow completed' in result.stdout
        data = {'mode': 'DEMO', 'success': success, 'client_stdout': result.stdout, 'client_stderr': result.stderr,
                'physical_ukey': False, 'standard_tls': 'TLSv1.3 with mutual software-certificate authentication'}
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        print(result.stdout)
        if not success:
            raise RuntimeError('Native C/S smoke failed')
    finally:
        for child, _ in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child, log in reversed(children):
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
            log.close()
        print('Owned DEMO processes stopped; result:', output)


def package():
    dest = ROOT / 'dist' / ('cs-ukey-pilot-' + VERSION)
    if dest.exists():
        shutil.rmtree(dest)
    (dest / 'lib').mkdir(parents=True)
    for name in MODULES:
        shutil.copy2(ROOT / name / 'target' / (name + '-' + VERSION + '.jar'), dest / 'lib')
    for name in ['README.md', 'ARCHITECTURE.md', 'PROVENANCE.md', 'TESTING.md']:
        shutil.copy2(ROOT / name, dest / name)
    shutil.copytree(ROOT / 'tools', dest / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / 'config', dest / 'config')
    manifest = {}
    for file in sorted(dest.rglob('*')):
        if file.is_file():
            manifest[str(file.relative_to(dest)).replace(os.sep, '/')] = hashlib.sha256(file.read_bytes()).hexdigest()
    (dest / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = Path(shutil.make_archive(str(dest), 'zip', dest))
    with zipfile.ZipFile(archive) as zip_:
        if any(name.endswith(('.p12', '.key')) or 'secrets.properties' in name for name in zip_.namelist()):
            raise RuntimeError('Generated credentials must not enter the release')
    Path(str(archive) + '.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    source_archive = ROOT / 'dist' / ('cs-ukey-pilot-' + VERSION + '-source.zip')
    with zipfile.ZipFile(source_archive, 'w', zipfile.ZIP_DEFLATED) as out:
        for file in sorted(ROOT.rglob('*')):
            relative = file.relative_to(ROOT)
            if not file.is_file() or any(part in {'.runtime', 'target', 'dist', '__pycache__'} for part in relative.parts):
                continue
            out.write(file, str(relative).replace(os.sep, '/'))
    Path(str(source_archive) + '.sha256').write_text(hashlib.sha256(source_archive.read_bytes()).hexdigest() + '  ' + source_archive.name + '\n')
    print('Portable DEMO bundle:', archive)
    print('Source project bundle:', source_archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'demo-init', 'smoke', 'acceptance', 'server', 'agent', 'business', 'client', 'package', 'diagnose'])
    parser.add_argument('--dir', type=Path, default=ROOT / '.runtime/demo')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--skip-tests', action='store_true')
    parser.add_argument('--seconds', type=int, default=60, help='Acceptance mixed workload duration, 5..1800 seconds')
    args = parser.parse_args()
    directory = args.dir.resolve()
    if args.action == 'demo-init':
        initialize(directory)
    elif args.action == 'build':
        maven(args.skip_tests)
    elif args.action == 'package':
        package()
    elif args.action == 'smoke':
        smoke(directory)
    elif args.action == 'acceptance':
        from acceptance import run
        run(args.dir if any(arg == '--dir' or arg.startswith('--dir=') for arg in sys.argv[1:]) else None, args.seconds)
    elif args.action == 'diagnose':
        java, _, env, _ = toolchain()
        result = subprocess.run([java, '-version'], env=env, text=True, capture_output=True)
        print(json.dumps({'java': result.stderr.strip(), 'classpath': classpath(), 'demo_directory_exists': directory.exists(),
                          'ports_listening': {port: occupied(port) for port in [19443, 19444, 19500, 19510]},
                          'real_pilot_supported': False}, ensure_ascii=False, indent=2))
    else:
        defaults = {'server': 'server.properties', 'agent': 'alice-agent.properties', 'business': 'business.properties', 'client': 'client.properties'}
        command, env = java_command(args.action, args.config or directory / defaults[args.action], args.gui)
        raise SystemExit(subprocess.call(command, env=env))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('REFUSED:', str(error), file=sys.stderr)
        raise SystemExit(2)
