#!/usr/bin/env python3
"""Check the handoff package and run its existing local acceptance suite."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "demo"


def verify_files():
    manifest = json.loads((ROOT / "SHA256SUMS.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        file = ROOT / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Missing or changed package file: {name}. Extract a fresh copy.")
    expected_jars = {ROOT / name for name in manifest if name.startswith("demo/lib/") and name.endswith(".jar")}
    if set((DEMO / "lib").glob("*.jar")) != expected_jars:
        raise ValueError("The demo/lib directory has an unexpected JAR file.")
    print(f"Package integrity OK ({len(manifest)} files).", flush=True)


def java_environment(selected_home):
    configured = selected_home or os.environ.get("JAVA_HOME")
    suffix = ".exe" if os.name == "nt" else ""
    java = Path(configured).expanduser().resolve() / "bin" / ("java" + suffix) if configured else shutil.which("java")
    if not java or not Path(java).is_file():
        raise ValueError("Java was not found. Install a JDK 17 or later and set JAVA_HOME or use --java-home.")
    version = subprocess.run(
        [str(java), "-XshowSettings:properties", "-version"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=15, check=True,
    ).stdout
    version_line = re.search(r'(?m)^\s*java\.version\s*=\s*((\d+)[^\r\n]*)', version)
    home_line = re.search(r'(?m)^\s*java\.home\s*=\s*([^\r\n]+)', version)
    if not version_line or int(version_line.group(2)) < 17 or not home_line:
        raise ValueError("Java 17 or later is required. Select it with --java-home.")
    home = Path(configured).expanduser().resolve() if configured else Path(home_line.group(1).strip())
    if not (home / "bin" / ("keytool" + suffix)).is_file():
        raise ValueError("The selected Java has no keytool. Select a complete JDK with --java-home.")
    env = dict(os.environ, JAVA_HOME=str(home))
    env["PATH"] = str(home / "bin") + os.pathsep + env.get("PATH", "")
    print(f"Python {sys.version.split()[0]}; Java {version_line.group(1).strip()}.", flush=True)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "doctor", "quick", "full"], nargs="?", default="quick")
    parser.add_argument("--java-home", type=Path, help="Select a JDK for this run")
    parser.add_argument("--output", type=Path, default=ROOT / "results", help="Parent directory for new runs")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        raise ValueError("Python 3.10 or later is required.")
    verify_files()
    if args.action == "verify":
        return 0
    env = java_environment(args.java_home)
    if args.action == "doctor":
        return 0

    # The existing suite chooses free ports and provisions fresh demo credentials.
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=args.action + "-", dir=output))
    report = run / "acceptance-result.json"
    seconds = "5" if args.action == "quick" else "60"
    print(f"Run directory: {run}", flush=True)
    result = subprocess.run(
        [sys.executable, "-B", str(DEMO / "tools/manage.py"), "acceptance",
         "--dir", str(run), "--seconds", seconds],
        cwd=DEMO, env=env,
    )
    if report.exists():
        print(f"Share this report: {report}", flush=True)
    else:
        print(f"No report generated. See the console and {run} for startup details.", flush=True)
    return result.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
