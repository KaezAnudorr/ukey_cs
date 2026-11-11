#!/usr/bin/env python3
"""Run the C/S network scenarios in three disposable Linux network namespaces."""
import contextlib
import datetime
import importlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time

TERMINAL = "10.77.10.2"
EDGE = "10.77.10.1"
INNER = "10.77.20.1"
BACKEND = "10.77.20.2"
BUSINESS_PORT = 19510
AGENT_PORT = 19500
TLS_PORTS = (19443, 19444)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def connect(host, port):
    return socket.create_connection((host, port), timeout=3)


def line(sock):
    data = bytearray()
    while len(data) < 4096:
        part = sock.recv(1)
        if not part or part == b"\n":
            return data.decode("utf-8")
        data.extend(part)
    raise RuntimeError("Probe response exceeded the line limit")


def business_login(sock, secret_path):
    password = next(value.split("=", 1)[1] for value in Path(secret_path).read_text().splitlines()
                    if value.startswith("business.password="))
    sock.sendall(f"LOGIN alice {password}\n".encode())
    return line(sock) == "OK alice"


def child(mode, host, port, secret_path):
    try:
        sock = connect(host, int(port))
    except OSError as error:
        if mode != "direct":
            raise
        print(json.dumps({"connected": False, "error": type(error).__name__}), flush=True)
        return
    with sock:
        logged_in = business_login(sock, secret_path)
        if mode == "direct":
            print(json.dumps({"connected": True, "logged_in": logged_in}), flush=True)
            return
        require(logged_in, "Blackhole probe could not log in")
        print("READY", flush=True)
        require(sys.stdin.readline().strip() == "send", "Missing blackhole command")
        sock.sendall(b"ECHO retained-connection\n")
        try:
            line(sock)
        except socket.timeout:
            print("TIMEOUT", flush=True)
        else:
            raise RuntimeError("Business data was returned during the network blackhole")
        require(sys.stdin.readline().strip() == "restore", "Missing restore command")
        sock.settimeout(20)
        require(line(sock) == "retained-connection", "Existing connection failed after link recovery")
        print("RECOVERED", flush=True)


class Lab:
    def __init__(self, bundle, output, runtime):
        self.output = output
        self.runtime = runtime
        sys.path.insert(0, str(bundle / "tools"))
        self.manage = importlib.import_module("manage")
        self.names = {role: f"csuk{os.getpid()}-{role}" for role in ("terminal", "gateway", "business")}
        self.created = []
        self.processes = []
        self.result = {
            "mode": "DEMO",
            "product_version": self.manage.VERSION,
            "physical_ukey": False,
            "production_ready": False,
            "guest": {"kernel": os.uname().release, "architecture": os.uname().machine},
            "cases": [],
            "topology": {
                "terminal": f"{TERMINAL}/24",
                "gateway_terminal_interface": f"{EDGE}/24",
                "gateway_business_interface": f"{INNER}/24",
                "business": f"{BACKEND}/24",
                "transport": "Linux veth and IPv4 routing; TCP relays adapt the DEMO loopback listeners",
            },
        }

    def command(self, *args, zone=None, timeout=15, check=True):
        argv = ["ip", "netns", "exec", self.names[zone], *args] if zone else list(args)
        result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f"{' '.join(argv)} failed ({result.returncode}): {result.stderr.strip()}")
        return result

    def ip(self, zone, *args):
        return self.command("ip", "-n", self.names[zone], *args).stdout.strip()

    def firewall(self, *args):
        return self.command("iptables", "-w", *args, zone="gateway").stdout

    def tc(self, zone, *args):
        return self.command("tc", *args, zone=zone).stdout

    def save(self):
        target = self.output / "network-result.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.result, indent=2, ensure_ascii=False) + "\n")
        temporary.replace(target)

    def case(self, name, operation):
        print(f"CHECK {name}", flush=True)
        start = time.monotonic()
        record = {"name": name}
        self.result["cases"].append(record)
        try:
            record["evidence"] = operation()
            record["outcome"] = "PASS"
        except Exception as error:
            record["outcome"] = "FAIL"
            record["error"] = str(error)
            raise
        finally:
            record["seconds"] = round(time.monotonic() - start, 3)
            self.save()

    def topology(self):
        for name in self.names.values():
            self.command("ip", "netns", "add", name)
            self.created.append(name)
        for a, a_dev, b, b_dev in (
            ("terminal", "uplink", "gateway", "outside"),
            ("gateway", "inside", "business", "uplink"),
        ):
            self.command("ip", "link", "add", a_dev, "netns", self.names[a], "type", "veth",
                         "peer", "name", b_dev, "netns", self.names[b])
        for zone, device, address in (
            ("terminal", "uplink", TERMINAL), ("gateway", "outside", EDGE),
            ("gateway", "inside", INNER), ("business", "uplink", BACKEND),
        ):
            self.ip(zone, "link", "set", "lo", "up")
            self.ip(zone, "addr", "add", address + "/24", "dev", device)
            self.ip(zone, "link", "set", device, "up")
        self.ip("terminal", "route", "add", "10.77.20.0/24", "via", EDGE)
        self.ip("business", "route", "add", "10.77.10.0/24", "via", INNER)
        self.command("sysctl", "-q", "-w", "net.ipv4.ip_forward=1", zone="gateway")
        self.firewall("-P", "FORWARD", "DROP")
        self.firewall("-A", "FORWARD", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT")
        self.direct_rule = ("-i", "outside", "-o", "inside", "-p", "tcp",
                            "-d", BACKEND, "--dport", str(BUSINESS_PORT))
        self.firewall("-A", "FORWARD", *self.direct_rule, "-j", "REJECT", "--reject-with", "tcp-reset")
        links = {}
        for zone in self.names:
            links[zone] = {
                "namespace": self.command("readlink", "/proc/self/ns/net", zone=zone).stdout.strip(),
                "addresses": self.ip(zone, "-br", "address"),
                "routes": self.ip(zone, "route", "show"),
            }
        require(len({link["namespace"] for link in links.values()}) == 3, "Expected three distinct Linux network namespaces")
        return links

    def start(self, label, zone, argv, env=None, control=False):
        with (self.output / (label + ".log")).open("w") as log:
            process = subprocess.Popen(
                ["ip", "netns", "exec", self.names[zone], *argv],
                env=env, start_new_session=True,
                stdin=subprocess.PIPE if control else subprocess.DEVNULL,
                stdout=subprocess.PIPE if control else log,
                stderr=log, text=True,
            )
        self.processes.append(process)
        return process

    def ready(self, process, zone, host, port):
        deadline = time.monotonic() + 12
        code = "import socket,sys;socket.create_connection((sys.argv[1],int(sys.argv[2])),.3).close()"
        while time.monotonic() < deadline:
            require(process.poll() is None, f"Listener exited before {host}:{port} became ready")
            result = self.command(sys.executable, "-c", code, host, str(port), zone=zone, check=False)
            if not result.returncode:
                return
            time.sleep(.1)
        raise RuntimeError(f"Listener did not become ready: {zone} {host}:{port}")

    def service(self, role, zone, filename, port):
        argv, env = self.manage.java_command(role, self.runtime / filename)
        process = self.start(role, zone, argv, env=env)
        self.ready(process, zone, "127.0.0.1", port)
        return process

    def relay(self, label, zone, address, port, target):
        argv = ["socat", "-t", "8", f"TCP4-LISTEN:{port},bind={address},reuseaddr,fork",
                f"TCP4:{target}:{port},connect-timeout=4"]
        self.ready(self.start(label, zone, argv), zone, address, port)

    def launch_services(self):
        self.service("business", "business", "business.properties", BUSINESS_PORT)
        self.relay("business-ingress", "business", BACKEND, BUSINESS_PORT, "127.0.0.1")
        self.relay("gateway-backend", "gateway", "127.0.0.1", BUSINESS_PORT, BACKEND)
        self.service("server", "gateway", "server.properties", TLS_PORTS[0])
        for port in TLS_PORTS:
            self.relay(f"gateway-ingress-{port}", "gateway", EDGE, port, "127.0.0.1")
            self.relay(f"terminal-uplink-{port}", "terminal", "127.0.0.1", port, EDGE)

    def unauthorized(self):
        argv, _ = self.manage.java_command("agent", self.runtime / "unmapped-agent.properties")
        result = self.command(*argv, zone="terminal", check=False)
        require(result.returncode == 2 and "403" in result.stderr, "Unmapped credential was not explicitly denied")
        return {"exit_code": result.returncode, "server_status": 403}

    def probe(self, label, *options):
        file = self.runtime / (label + ".json")
        argv, _ = self.manage.java_command("probe", self.runtime / "client.properties")
        self.command(*argv, "--scenario", "exercise", "--report", str(file), *options,
                     zone="terminal", timeout=45)
        data = json.loads(file.read_text())
        require(data["success"], f"Business probe failed: {label}")
        return data

    def probe_direct(self):
        result = self.command(sys.executable, __file__, "--child", "direct", BACKEND, str(BUSINESS_PORT),
                              str(self.runtime / "secrets.properties"), zone="terminal")
        return json.loads(result.stdout)

    def direct_control(self):
        self.firewall("-I", "FORWARD", "2", *self.direct_rule, "-j", "ACCEPT")
        try:
            result = self.probe_direct()
            require(result.get("logged_in"), "Positive control did not reach the real backend listener")
            return result
        finally:
            self.firewall("-D", "FORWARD", *self.direct_rule, "-j", "ACCEPT")

    def direct_denied(self):
        def counter():
            listing = self.firewall("-L", "FORWARD", "-vnx")
            rule = next(row for row in listing.splitlines() if "REJECT" in row and "dpt:19510" in row)
            return int(rule.split()[0]), listing

        before, _ = counter()
        result = self.probe_direct()
        after, listing = counter()
        require(not result["connected"] and after > before, "Direct connection was not blocked by the gateway firewall")
        return {**result, "firewall_reject_packets": after - before, "firewall": listing}

    def weak_link(self):
        devices = (("terminal", "uplink"), ("gateway", "outside"))
        try:
            for zone, device in devices:
                self.tc(zone, "qdisc", "replace", "dev", device, "root", "netem", "delay", "35ms", "10ms", "loss", "1%")
            probe = self.probe("weak-link", "--connections", "2", "--seconds", "12", "--bytes", "32768")
            return {
                "probe": probe,
                "qdisc": {zone: self.tc(zone, "-s", "qdisc", "show", "dev", device) for zone, device in devices},
            }
        finally:
            for zone, device in devices:
                self.command("tc", "qdisc", "del", "dev", device, "root", zone=zone, check=False)

    def blackhole(self):
        process = self.start("blackhole", "terminal", [
            sys.executable, __file__, "--child", "watch", "127.0.0.1", str(AGENT_PORT),
            str(self.runtime / "secrets.properties"),
        ], control=True)

        def expect(marker, timeout):
            ready, _, _ = select.select([process.stdout], [], [], timeout)
            require(ready and process.stdout.readline().strip() == marker, f"Expected blackhole probe state {marker}")

        expect("READY", 10)
        self.tc("terminal", "qdisc", "replace", "dev", "uplink", "root", "netem", "loss", "100%")
        try:
            start = time.monotonic()
            process.stdin.write("send\n")
            process.stdin.flush()
            expect("TIMEOUT", 8)
            timeout_elapsed = time.monotonic() - start
            stats = self.tc("terminal", "-s", "qdisc", "show", "dev", "uplink")
        finally:
            self.tc("terminal", "qdisc", "del", "dev", "uplink", "root")
        process.stdin.write("restore\n")
        process.stdin.flush()
        expect("RECOVERED", 22)
        require(process.wait(3) == 0, "Blackhole probe failed after recovery")
        return {"observed_client_timeout_seconds": round(timeout_elapsed, 3),
                "same_connection_recovered": True, "qdisc": stats}

    def close(self):
        errors = []
        for process in reversed(self.processes):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        for process in reversed(self.processes):
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
        for name in reversed(self.created):
            result = self.command("ip", "netns", "delete", name, check=False)
            if result.returncode:
                errors.append(result.stderr.strip())
        remaining = self.command("ip", "netns", "list").stdout.splitlines()
        self.result["cleanup"] = {"errors": errors, "remaining_namespaces": [
            line for line in remaining if line.split()[0] in self.created
        ]}

    def run(self):
        self.result["started_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.result["passed"] = False
        try:
            self.manage.initialize(self.runtime)
            server_config = self.runtime / "server.properties"
            server_config.write_text(server_config.read_text().replace("session.ttl.seconds=60", "session.ttl.seconds=180"))
            self.case("Three isolated Linux network stacks and explicit routing", self.topology)
            self.launch_services()
            self.case("Direct business path succeeds with a temporary allow rule", self.direct_control)
            self.case("Firewall blocks terminal from the original business port", self.direct_denied)
            self.case("Unregistered certificate denied across terminal/gateway networks", self.unauthorized)
            self.service("agent", "terminal", "alice-agent.properties", AGENT_PORT)
            self.case("Authorized C/S through the gateway across both subnets",
                      lambda: self.probe("baseline", "--bytes", "2097152", "--fragmented"))
            self.case("Bidirectional delay, jitter and packet loss with byte checks", self.weak_link)
            self.case("100 percent outbound loss stalls an established connection and removal restores it", self.blackhole)
            self.case("After link recovery a fresh gateway connection still works", lambda: self.probe("recovered"))
            self.case("Direct path is still denied after recovery", self.direct_denied)
            self.result["known_gaps"] = [
                "Processes in the terminal namespace can share the authenticated loopback Agent listener.",
                "The same VM runs all namespaces; Windows, production host boundaries and physical UKey are untested.",
                "The gateway account adapter still uses the sample business protocol.",
            ]
            self.result["passed"] = True
        except Exception as error:
            self.result["error"] = str(error)
            raise
        finally:
            self.close()
            if any(self.result["cleanup"].values()):
                self.result["passed"] = False
            self.result["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.save()


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        child(*sys.argv[2:])
    else:
        require(os.geteuid() == 0 and sys.platform.startswith("linux"), "Run on a disposable Linux guest as root")
        destination = Path(sys.argv[2]).resolve()
        destination.mkdir()
        with tempfile.TemporaryDirectory(prefix="cs-ukey-net-") as work:
            Lab(Path(sys.argv[1]).resolve(), destination, Path(work) / "pki").run()
