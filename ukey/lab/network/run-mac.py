#!/usr/bin/env python3
"""Boot the network lab in a disposable Debian VM on Apple Silicon."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGE_NAME = "debian-12-generic-arm64.tar.xz"
IMAGE_URL = (
    "https://cloud.debian.org/images/cloud/bookworm/20261026-2643/"
    "debian-12-generic-arm64-20261026-2643.tar.xz"
)
IMAGE_SHA512 = (
    "d62a665eb3baee2dd9fda56dc3b5d66854c352792409e5aea03fe5988c433b801239eb"
    "cfab0afa8a2b3f7300eb50a139ca179483380fc2299a2e00963bfa4bf5"
)


def digest(path, algorithm):
    checksum = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def prepare_image(cache):
    cache.mkdir(parents=True, exist_ok=True)
    image = cache / IMAGE_NAME
    if not image.exists():
        download = image.with_suffix(".download")
        subprocess.run([
            "curl", "-fL", "--retry", "2", "--connect-timeout", "15",
            "--max-time", "300", IMAGE_URL, "-o", str(download),
        ], check=True)
        if digest(download, "sha512") != IMAGE_SHA512:
            raise RuntimeError("Debian image download failed SHA-512 verification")
        download.replace(image)
    if digest(image, "sha512") != IMAGE_SHA512:
        raise RuntimeError(f"Unexpected Debian image checksum: {image}")
    return image


def stage_bundle(bundle, dest):
    manifest = json.loads((bundle / "SHA256SUMS.json").read_text())
    files = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file())
    if set(files) != set(manifest) | {"SHA256SUMS.json"}:
        raise RuntimeError("Bundle file list differs from its manifest")
    for name, checksum in manifest.items():
        if digest(bundle / name, "sha256") != checksum:
            raise RuntimeError(f"Unexpected bundle checksum: {name}")
    shutil.copytree(bundle, dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / "tmp/network-lab-cache")
    parser.add_argument("--bundle", type=Path, default=ROOT / "product/dist/cs-ukey-pilot-0.2.0-demo")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This launcher requires Apple Silicon macOS")
    work = args.output.resolve()
    work.mkdir(mode=0o700)
    image = prepare_image(args.cache.resolve())
    share = work / "share"
    share.mkdir()
    stage_bundle(args.bundle.resolve(), share / "bundle")
    shutil.copy2(HERE / "guest.py", share / "guest.py")

    # The verified archive contains a single raw disk member.
    print("Extracting disposable VM disk", flush=True)
    with tarfile.open(image, "r:xz") as archive:
        with archive.extractfile("disk.raw") as source, (work / "disk.raw").open("wb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)

    seed = work / "seed"
    seed.mkdir()
    (seed / "meta-data").write_text(f"instance-id: cs-ukey-network-{os.getpid()}\nlocal-hostname: cs-ukey-lab\n")
    bootstrap = base64.b64encode((HERE / "bootstrap.sh").read_bytes()).decode("ascii")
    (seed / "user-data").write_text(
        "#cloud-config\nssh_pwauth: false\ndisable_root: true\n"
        "write_files:\n  - path: /usr/local/sbin/cs-lab-bootstrap\n"
        "    encoding: b64\n    permissions: '0700'\n"
        f"    content: {bootstrap}\n"
        "runcmd:\n  - [/usr/local/sbin/cs-lab-bootstrap]\n"
    )
    subprocess.run([
        "hdiutil", "makehybrid", "-iso", "-joliet", "-default-volume-name", "cidata",
        "-o", str(work / "seed.iso"), str(seed),
    ], check=True)
    entitlements = work / "entitlements.plist"
    entitlements.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<plist version="1.0"><dict><key>com.apple.security.virtualization</key>'
        '<true/></dict></plist>\n'
    )
    launcher = work / "RunVM"
    subprocess.run(["swiftc", "-parse-as-library", str(HERE / "RunVM.swift"), "-o", str(launcher)], check=True)
    subprocess.run(["codesign", "--sign", "-", "--entitlements", str(entitlements), str(launcher)], check=True)
    print("Booting lab. Console and bootstrap logs:", work, flush=True)
    with (work / "vm-console.log").open("wb") as console:
        result = subprocess.run([
            str(launcher), str(work / "disk.raw"), str(work / "seed.iso"),
            str(share), str(work / "efi.vars"),
        ], stdout=console, stderr=subprocess.STDOUT, timeout=900)
    report = share / "results/network-result.json"
    status = share / "guest.exit"
    if result.returncode or not status.exists() or status.read_text().strip() != "0" or not report.exists():
        raise RuntimeError(f"VM lab did not complete. Inspect {work / 'vm-console.log'} and {share / 'guest-bootstrap.log'}")
    print(report.read_text(), end="")
    if not json.loads(report.read_text())["passed"]:
        raise RuntimeError("One or more required network checks failed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
