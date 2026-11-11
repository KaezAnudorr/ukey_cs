#!/usr/bin/env python3
"""Owned-process local resilience checks, with explicitly reported unresolved security gaps."""
from pathlib import Path
import datetime
import json
import os
import shutil
import socket
import subprocess
import sys
import time

import manage


class Suite:
    def __init__(self, directory):
        self.directory = directory
        self.logs = directory / 'acceptance-logs'
        self.logs.mkdir()
        self.children = []
        self.sequence = 0
        self.cases = []
        self.samples = []
        self.report = {'version': manage.VERSION, 'mode': 'DEMO', 'physical_ukey': False,
                       'production_ready': False, 'environment': {'platform': sys.platform, 'same_machine': True,
                       'network_isolation_tested': False, 'gui_tested': False},
                       'known_limitations': ['Software certificate identity only; no real UKey, SKF or GM channel.',
                                            'All processes run on one host over loopback; no firewall isolation or cross-OS validation.',
                                            'Only the bundled sample account/framing protocol is covered.',
                                            'No kernel-level packet loss, network blackhole or multi-hour endurance claim.'],
                       'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'cases': self.cases}

    def start(self, role, config=None, port=None, extra=()):
        self.sequence += 1
        label = f'{self.sequence:02d}-{role}'
        command, env = manage.java_command(role, config or self.directory / (role + '.properties'))
        command.extend(map(str, extra))
        log = (self.logs / (label + '.log')).open('w')
        child = subprocess.Popen(command, env=env, stdin=subprocess.PIPE if role == 'agent' else subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT)
        child._acceptance_log = self.logs / (label + '.log')
        self.children.append((child, log, role))
        if port:
            deadline = time.monotonic() + 20
            while not manage.occupied(port):
                if child.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Startup failed: ' + label)
                time.sleep(.05)
        return child

    def stop(self, child, hard=False):
        if child.poll() is None:
            child.kill() if hard else child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)

    def disconnect(self, child):
        if child.poll() is not None:
            raise RuntimeError('Agent exited before disconnect command')
        child.stdin.write(b'disconnect\n')
        child.stdin.flush()
        if child.wait(timeout=10) != 0:
            raise RuntimeError('Agent disconnect failed')

    def probe_start(self, config, scenario='exercise', **options):
        self.sequence += 1
        output = self.logs / f'probe-{self.sequence:02d}.json'
        extra = ['--scenario', scenario, '--report', output]
        for key, value in options.items():
            extra.append('--' + key.replace('_', '-'))
            if value is not True:
                extra.append(str(value))
        child = self.start('probe', config, extra=extra)
        return child, output

    def collect(self, probe, timeout=25):
        child, output = probe
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.stop(child, hard=True)
            raise RuntimeError('Probe timed out')
        data = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
        if code != 0 or not data.get('success'):
            raise RuntimeError(f'Probe failed; see {child._acceptance_log.name} / {output.name}')
        return data

    def probe(self, config, scenario='exercise', **options):
        return self.collect(self.probe_start(config, scenario, **options))

    def watch(self, config):
        probe = self.probe_start(config, 'watch')
        deadline = time.monotonic() + 10
        while 'READY' not in probe[0]._acceptance_log.read_text():
            if probe[0].poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Watch probe did not authenticate')
            time.sleep(.05)
        return probe

    def case(self, name, function, gap=False):
        print('CHECK:', name, flush=True)
        begin = time.monotonic()
        record = {'name': name, 'outcome': 'RUNNING'}
        self.cases.append(record)
        try:
            record['evidence'] = function()
            record['outcome'] = 'OBSERVED_GAP' if gap else 'PASS'
        except Exception as error:
            record['outcome'] = 'FAIL'
            record['error'] = str(error)
            raise
        finally:
            record['elapsed_seconds'] = round(time.monotonic() - begin, 3)
            self.save()

    def sample(self):
        sample = {'elapsed_seconds': round(time.monotonic() - self.begin, 1), 'processes': []}
        for child, _, role in self.children:
            if role == 'probe' or child.poll() is not None:
                continue
            entry = {'role': role, 'pid': child.pid}
            if os.name == 'posix' and shutil.which('ps'):
                result = subprocess.run(['ps', '-o', 'rss=', '-p', str(child.pid)], capture_output=True, text=True, timeout=3)
                if result.returncode == 0 and result.stdout.strip().isdigit():
                    entry['rss_kib'] = int(result.stdout.strip())
            sample['processes'].append(entry)
        self.samples.append(sample)

    def save(self):
        self.report['summary'] = {status: sum(c['outcome'] == status for c in self.cases) for status in ['PASS', 'OBSERVED_GAP', 'FAIL']}
        self.report['overall_status'] = ('FAILED' if self.report['summary']['FAIL'] or self.report.get('fatal_error')
                                         else 'CHECKS_PASSED_WITH_GAPS' if self.report.get('all_implemented_checks_passed') else 'IN_PROGRESS')
        self.report['resource_samples'] = self.samples
        (self.directory / 'acceptance-result.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def close(self):
        for child, log, _ in reversed(self.children):
            self.stop(child)
            if child.stdin:
                child.stdin.close()
            log.close()


def properties(path):
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines() if line and not line.startswith('#'))


def update(path, **changes):
    values = properties(path)
    values.update(changes)
    manage.write_properties(path, values)


def ports(count):
    reserved = [socket.socket() for _ in range(count)]
    try:
        for sock in reserved:
            sock.bind(('127.0.0.1', 0))
        return [sock.getsockname()[1] for sock in reserved]
    finally:
        for sock in reserved:
            sock.close()


def run(directory=None, seconds=60):
    if not 5 <= seconds <= 1800:
        raise ValueError('Acceptance duration must be 5..1800 seconds')
    directory = (directory or manage.ROOT / '.runtime' / ('acceptance-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))).resolve()
    manage.classpath()  # Check build/bundle before generating keys.
    manage.initialize(directory)  # Refuses an existing nonempty directory.
    api, gateway, backend, a_port, b_port = ports(5)
    update(directory / 'server.properties', **{'api.port': api, 'gateway.port': gateway,
           'resource.sample.port': backend, 'session.ttl.seconds': min(3600, seconds + 180)})
    update(directory / 'business.properties', **{'business.port': backend})
    for name, port in [('alice', a_port), ('bob', b_port)]:
        update(directory / (name + '-agent.properties'), **{'api.port': api, 'gateway.port': gateway, 'agent.port': port})
        manage.write_properties(directory / (name + '-client.properties'), {'mode': 'DEMO', 'client.host': '127.0.0.1',
                                'client.port': port, 'business.user': name, 'secrets.file': 'secrets.properties'})
    manage.write_properties(directory / 'direct-client.properties', {'mode': 'DEMO', 'client.host': '127.0.0.1',
                            'client.port': backend, 'business.user': 'alice', 'secrets.file': 'secrets.properties'})
    suite = Suite(directory)
    suite.begin = time.monotonic()
    suite.report['ports'] = {'api': api, 'gateway': gateway, 'backend': backend, 'alice_agent': a_port, 'bob_agent': b_port}
    a_config, b_config = directory / 'alice-client.properties', directory / 'bob-client.properties'
    try:
        business = suite.start('business', port=backend)
        server = suite.start('server', port=api)
        suite.case('No Agent: local business entry is unavailable', lambda: suite.probe(a_config, 'expect-failure'))
        suite.case('KNOWN GAP: original backend permits direct business access', lambda: suite.probe(directory / 'direct-client.properties'), gap=True)
        agent = suite.start('agent', directory / 'alice-agent.properties', a_port)
        bob = suite.start('agent', directory / 'bob-agent.properties', b_port)
        suite.case('Native process: fragmented login, coalesced UTF-8 commands and 2 MiB binary round trip',
                   lambda: suite.probe(a_config, bytes=2 * 1024 * 1024, fragmented=True))
        suite.case('Native process: half-closed request still receives its complete 2 MiB response',
                   lambda: suite.probe(a_config, 'half-close', bytes=2 * 1024 * 1024))
        suite.case('KNOWN GAP: another local process can reuse an authorized Agent entry', lambda: suite.probe(a_config), gap=True)

        def load():
            probes = [suite.probe_start(config, connections=3, seconds=seconds, bytes=262144) for config in [a_config, b_config]]
            deadline = time.monotonic() + seconds + 30
            suite.sample()
            next_sample = time.monotonic() + 10
            while any(child.poll() is None for child, _ in probes):
                if time.monotonic() > deadline:
                    raise RuntimeError('Concurrent workload timed out')
                if time.monotonic() >= next_sample:
                    suite.sample()
                    print('WORKLOAD: independent Alice/Bob probes are running', flush=True)
                    next_sample = time.monotonic() + 10
                time.sleep(.2)
            result = [suite.collect(probe) for probe in probes]
            suite.sample()
            return {'users': 2, 'connections': 6, 'requested_seconds': seconds, 'probes': result,
                    'operations': sum(p['operations'] for p in result),
                    'verified_binary_bytes_both_directions': sum(p['verified_binary_bytes_both_directions'] for p in result)}
        suite.case('Two identities, six persistent connections: mixed workload and byte-for-byte verification', load)
        def churn():
            probes = [suite.probe_start(config, 'churn', connections=2, rounds=50) for config in [a_config, b_config]]
            result = [suite.collect(probe, 100) for probe in probes]
            suite.sample()
            return {'connection_cycles': sum(p['operations'] for p in result), 'probes': result}
        suite.case('Two identities: 200 connection/login/QUIT cycles release capacity', churn)
        suite.stop(bob)
        suite.stop(business, hard=True)
        suite.case('Backend crash: business access fails without fallback', lambda: suite.probe(a_config, 'expect-failure'))
        business = suite.start('business', port=backend)
        suite.case('Backend restart: existing Agent can open a fresh business connection', lambda: suite.probe(a_config))

        def crash_agent():
            watched = suite.watch(a_config)
            begin = time.monotonic()
            suite.stop(agent, hard=True)
            result = suite.collect(watched, 8)
            elapsed = time.monotonic() - begin
            if elapsed > 5 or manage.occupied(a_port):
                raise RuntimeError('Crashed Agent did not close its port/connections promptly')
            return {'closed_within_seconds': elapsed, 'probe': result,
                    'server_session_note': 'Hard crash cannot send logout; server-side session remains bounded by TTL.'}
        suite.case('Agent hard crash closes the local port and an established business socket', crash_agent)
        agent = suite.start('agent', directory / 'alice-agent.properties', a_port)
        suite.case('Agent restart: new authentication restores business access', lambda: suite.probe(a_config))

        def crash_server():
            watched = suite.watch(a_config)
            begin = time.monotonic()
            suite.stop(server, hard=True)
            result = suite.collect(watched, 8)
            elapsed = time.monotonic() - begin
            if elapsed > 5:
                raise RuntimeError('Server crash did not close the established socket promptly')
            return {'closed_within_seconds': elapsed, 'probe': result}
        suite.case('Access server hard crash closes an established business connection', crash_server)
        suite.case('Access server unavailable: running Agent cannot forward business login', lambda: suite.probe(a_config, 'expect-failure'))
        server = suite.start('server', port=api)
        suite.case('Server restart: an old Agent session is not accepted', lambda: suite.probe(a_config, 'expect-failure'))
        suite.stop(agent)
        agent = suite.start('agent', directory / 'alice-agent.properties', a_port)
        suite.case('Server restart: explicit reauthentication restores access', lambda: suite.probe(a_config))

        def logout():
            watched = suite.watch(a_config)
            audit = directory / 'audit.jsonl'
            prior = audit.read_text().count('"event":"session-revoked"')
            begin = time.monotonic()
            suite.disconnect(agent)
            result = suite.collect(watched, 8)
            elapsed = time.monotonic() - begin
            if elapsed > 5 or manage.occupied(a_port):
                raise RuntimeError('Agent exit did not close local connections promptly')
            if audit.read_text().count('"event":"session-revoked"') <= prior:
                raise RuntimeError('Agent exit did not revoke its server session')
            return {'closed_within_seconds': elapsed, 'probe': result, 'server_revocation_audited': True}
        suite.case('Explicit Agent disconnect revokes the server session and closes connections/listener', logout)
        suite.stop(server)
        update(directory / 'server.properties', **{'session.ttl.seconds': 4})
        server = suite.start('server', port=api)
        agent = suite.start('agent', directory / 'alice-agent.properties', a_port)

        def expiry():
            watched = suite.watch(a_config)
            result = suite.collect(watched, 10)
            agent.wait(timeout=5)
            if agent.returncode != 0 or manage.occupied(a_port):
                raise RuntimeError('Expired Agent did not exit cleanly')
            return {'ttl_seconds': 4, 'probe': result, 'agent_exit_code': agent.returncode}
        suite.case('Session expiry closes a native client connection and exits the Agent', expiry)
        suite.report['completed'] = True
    except BaseException as error:
        suite.report['completed'] = False
        suite.report['fatal_error'] = str(error)
        raise
    finally:
        suite.close()
        suite.report['ports_after_cleanup'] = {name: manage.occupied(port) for name, port in suite.report['ports'].items()}
        suite.report['owned_processes_remaining'] = [child.pid for child, _, _ in suite.children if child.poll() is None]
        suite.report['all_implemented_checks_passed'] = (suite.report.get('completed', False)
                and not any(c['outcome'] == 'FAIL' for c in suite.cases)
                and not any(suite.report['ports_after_cleanup'].values()) and not suite.report['owned_processes_remaining'])
        suite.report['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        suite.save()
        print('Acceptance result:', directory / 'acceptance-result.json', flush=True)
        print('Summary:', json.dumps(suite.report['summary']), '; production_ready=false', flush=True)
    if not suite.report['all_implemented_checks_passed']:
        raise RuntimeError('Acceptance checks or cleanup failed')
