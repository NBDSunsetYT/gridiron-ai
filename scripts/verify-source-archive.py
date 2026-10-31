"""Validate an allowlisted source archive without printing credential material.

Use only for local/release engineering. This is not an application endpoint.
Private fixture paths are explicit and remain outside the generated archive.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


def private_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if re.search(r"secret|token|password|credential", key, re.I) and isinstance(item, str) and len(item) >= 8:
                yield item.encode()
            else:
                yield from private_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from private_values(item)


def configured_secrets(root: Path, fixtures: list[str]) -> set[bytes]:
    values: set[bytes] = set()
    for key, value in os.environ.items():
        if re.search(r"secret|token|password|(?:^|_)key(?:$|_)|database_url|connection_string", key, re.I) and len(value) >= 16:
            values.add(value.encode())
    for path in root.glob(".env*"):
        if path.name == ".env.example" or not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            value = value.strip().strip("\"'")
            if re.search(r"secret|token|password|(?:^|_)key(?:$|_)|database_url|connection_string", key, re.I) and len(value) >= 16:
                values.add(value.encode())
    for name in fixtures:
        path = Path(name)
        if path.exists():
            values.update(private_values(json.loads(path.read_text())))
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    parser.add_argument("--private-fixture", action="append", default=[])
    parser.add_argument("--report")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    archive = Path(args.archive).resolve()
    forbidden_parts = {".git", "node_modules", ".venv", "__pycache__", "data", "backups", "xcuserdata", "deriveddata", ".build", ".vercel", ".temp", ".branches"}
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".key", ".pem", ".p8", ".p12", ".pfx", ".mobileprovision"}
    credential_pattern = re.compile(rb"(?:^|[\s\"'=])(?:sb_secret_[A-Za-z0-9_-]{24,}|sk-proj-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
    secrets = configured_secrets(root, args.private_fixture)
    files = []
    with zipfile.ZipFile(archive) as handle:
        if handle.testzip() is not None:
            raise SystemExit("Source archive integrity check failed.")
        seen: set[str] = set()
        for entry in handle.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or entry.filename in seen:
                raise SystemExit("Unsafe or duplicate source archive path.")
            seen.add(entry.filename)
            if any(part.lower() in forbidden_parts or part.startswith(".next") for part in path.parts):
                raise SystemExit("Private/cache directory found in source archive.")
            if (path.name.startswith(".env") and str(path) != ".env.example") or path.suffix.lower() in forbidden_suffixes or any(path.name.endswith(suffix) for suffix in (".db-wal", ".db-shm")):
                raise SystemExit("Credential/database path found in source archive.")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise SystemExit("Source archive symlink rejected.")
            if entry.is_dir():
                continue
            raw = handle.read(entry)
            if any(value in raw for value in secrets) or credential_pattern.search(raw):
                raise SystemExit("Credential material found in source archive; publication canceled.")
            files.append({"path": entry.filename, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    report = {
        "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "archive": archive.name,
        "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "fileCount": len(files),
        "integrity": "passed",
        "unsafePaths": "none",
        "configuredCredentialComparison": "passed" if secrets else "no configured local credential values available; structural/pattern checks passed",
        "credentialPatterns": "none",
        "files": files,
    }
    if args.report:
        report_path = Path(args.report).resolve()
        if report_path == archive:
            raise SystemExit("Report cannot replace the archive.")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}))


if __name__ == "__main__":
    main()
