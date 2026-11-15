"""Хук Claude Code після кожної правки файлу (PostToolUse: Edit|Write|MultiEdit).

* *.ps1 і *.bat — повертає закінчення рядків CRLF (у .gitattributes вони -text), *.ps1 — ще й UTF-8 BOM:
  без нього Windows PowerShell 5.1 читає кирилицю як ANSI.
* dmxctl/*.py, tests/*.py — запускає pytest (~1 с); dmxctl/static/app.js — node --check.
  Якщо перевірка впала, повертає код 2: Claude бачить помилку й виправляє її одразу.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BOM = b"\xef\xbb\xbf"


def fix_line_endings(path: Path) -> str | None:
    data = path.read_bytes()
    fixed = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if path.suffix.lower() == ".ps1" and not fixed.startswith(BOM):
        fixed = BOM + fixed
    if fixed != data:
        path.write_bytes(fixed)
        return f"{path.name}: відновлено CRLF" + (" і BOM" if path.suffix.lower() == ".ps1" else "")
    return None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    return res.returncode, (res.stdout + res.stderr).strip()


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    file_path = (event.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    path = Path(file_path).resolve()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return 0                      # файл поза проєктом
    if not path.exists():
        return 0

    if path.suffix.lower() in (".ps1", ".bat"):
        note = fix_line_endings(path)
        if note:
            print(note)
        return 0

    if rel.endswith(".py") and (rel.startswith("dmxctl/") or rel.startswith("tests/")):
        try:
            import pytest  # noqa: F401
        except ImportError:
            return 0
        code, out = run([sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"], root)
        if code not in (0, 5):        # 5 — тестів не знайдено
            print("pytest впав після правки " + rel + ":\n" + out[-3000:], file=sys.stderr)
            return 2
        return 0

    if rel == "dmxctl/static/app.js" and shutil.which("node"):
        code, out = run(["node", "--check", rel], root)
        if code != 0:
            print("Синтаксична помилка в app.js:\n" + out[-2000:], file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
