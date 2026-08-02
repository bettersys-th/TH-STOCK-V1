"""Fail CI when common secrets or private files are about to enter the repo."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}
EXCLUDED_PARTS = {".git", ".venv", "data", "node_modules", "venv"}
EXCLUDED_FILES = {"index.html", "scripts/security_guard.py"}
MAX_BYTES = 2_000_000
FORBIDDEN_NAMES = [
    re.compile(r"^\.env(?:\..+)?$", re.I),
    re.compile(r".*\.(?:key|pem|p12|pfx)$", re.I),
    re.compile(r".*(?:credentials|secrets?).*\.json$", re.I),
]
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Stripe live secret": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


def excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def scan(root: Path = ROOT) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or excluded(path):
            continue
        relative = path.relative_to(root)
        if relative.as_posix() != ".env.example" and any(
            pattern.fullmatch(path.name) for pattern in FORBIDDEN_NAMES
        ):
            findings.append(f"forbidden file: {relative}")
        if (
            relative.as_posix() in EXCLUDED_FILES
            or path.suffix.lower() not in TEXT_SUFFIXES
            or path.stat().st_size > MAX_BYTES
        ):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"possible {label}: {relative}")
    return sorted(set(findings))


def main() -> int:
    findings = scan()
    if findings:
        print("Security guard blocked the build:")
        for finding in findings:
            print(f"- {finding}")
        print("Remove the secret/file and rotate any exposed credential before retrying.")
        return 1
    print("Security guard passed: no forbidden files or common secret signatures found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
