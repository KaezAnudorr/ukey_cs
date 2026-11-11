#!/usr/bin/env python3
"""Package the verified C/S releases with a separate handoff entry point."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RELEASE = "cs-ukey-pilot-0.2.0-demo"
DIST = ROOT / "product/dist"


def sha256(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def verify_release(file):
    expected = file.with_suffix(".zip.sha256").read_text().split()[0]
    if sha256(file) != expected:
        raise ValueError(f"Release checksum mismatch: {file}")


def stage(stage_root):
    binary = DIST / (RELEASE + ".zip")
    source = DIST / (RELEASE + "-source.zip")
    for archive in (binary, source):
        verify_release(archive)
    with zipfile.ZipFile(binary) as bundle:
        for entry in bundle.namelist():
            path = PurePosixPath(entry)
            if path.is_absolute() or ".." in path.parts or "\\" in entry:
                raise ValueError(f"Unsafe release path: {entry}")
        bundle.extractall(stage_root / "demo")
    demo = stage_root / "demo"
    manifest = json.loads((demo / "SHA256SUMS.json").read_text())
    actual = {file.relative_to(demo).as_posix() for file in demo.rglob("*") if file.is_file()}
    if actual != set(manifest) | {"SHA256SUMS.json"}:
        raise ValueError("Binary release file list differs from its manifest")
    for name, expected in manifest.items():
        if sha256(demo / name) != expected:
            raise ValueError(f"Binary release file checksum mismatch: {name}")

    (stage_root / "source").mkdir()
    shutil.copy2(source, stage_root / "source")
    shutil.copy2(source.with_suffix(".zip.sha256"), stage_root / "source")
    for name in ("START-HERE.md", "NETWORK.md", "REAL-PILOT.md", "test.py", "test.cmd"):
        shutil.copy2(HERE / name, stage_root / name)
    lab = stage_root / "lab/network"
    lab.mkdir(parents=True)
    for name in ("RunVM.swift", "run-mac.py", "bootstrap.sh", "guest.py"):
        shutil.copy2(ROOT / "lab/network" / name, lab / name)

    baseline = stage_root / "baseline"
    baseline.mkdir()
    for relative in (
        "2026-11-06/v0.2/acceptance-result.json",
        "2026-11-09/network-lab/network-result.json",
    ):
        shutil.copy2(ROOT / "evidence/development" / relative, baseline)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DIST / "cs-ukey-handoff-0.2.0-demo.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    with tempfile.TemporaryDirectory(prefix="cs-ukey-handoff-") as temp:
        folder = Path(temp)
        stage(folder)
        files = {file.relative_to(folder).as_posix(): sha256(file)
                 for file in sorted(folder.rglob("*")) if file.is_file()}
        (folder / "SHA256SUMS.json").write_text(json.dumps(files, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as bundle:
            for file in sorted(folder.rglob("*")):
                if file.is_file():
                    bundle.write(file, file.relative_to(folder).as_posix())
    output.with_suffix(".zip.sha256").write_text(f"{sha256(output)}  {output.name}\n", encoding="ascii")
    print(output)


if __name__ == "__main__":
    main()
