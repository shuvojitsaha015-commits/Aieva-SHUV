"""Check what goes to GitHub.

    python3 scripts/check_release.py

It lists the files that would be uploaded, the ones that are excluded by
``.gitignore`` and it looks for a secret that should never be committed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The patterns of a secret that must never be committed.
SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']"),
)

#: The values that are only placeholders.
PLACEHOLDERS = ("your-", "changeme", "example", "xxxx", "<", "todo")


def git(*args: str) -> str:
    """Run a git command and return its output."""
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def is_repository() -> bool:
    return (ROOT / ".git").exists()


def main() -> int:
    if not is_repository():
        print("This folder is not a git repository yet.")
        print("Run 'git init' first, then run this script again.")
        print()
        print("Everything in the folder is uploaded, except what .gitignore names:")
        ignore = ROOT / ".gitignore"
        if ignore.is_file():
            for line in ignore.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    print(f"  - {line}")
        return 1

    tracked = [line for line in git("ls-files").splitlines() if line]
    untracked = [line for line in git("ls-files", "-o", "--exclude-standard").splitlines() if line]
    ignored = [
        line for line in git("ls-files", "-o", "-i", "--exclude-standard").splitlines() if line
    ]
    upload = sorted(tracked + untracked)

    print("=" * 66)
    print("Aieva - what goes to GitHub")
    print("=" * 66)
    print(f"  files that are uploaded : {len(upload)}")
    print(f"  files that are excluded : {len(ignored)} (the .gitignore rules)")

    size = sum((ROOT / name).stat().st_size for name in upload if (ROOT / name).is_file())
    print(f"  size of the upload      : {size / 1024 / 1024:.1f} MB")

    print()
    print("The folders that stay out of the repository:")
    folders = sorted({str(Path(name).parent).replace("\\", "/") for name in ignored})
    for folder in folders:
        print(f"  - {folder}")

    print()
    print("Looking for a secret ...")
    problems: list[str] = []
    for name in upload:
        path = ROOT / name
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                if any(marker in value.lower() for marker in PLACEHOLDERS):
                    continue
                problems.append(f"{name}: {value[:12]}...")
    if problems:
        print("  FOUND - these must not be committed:")
        for problem in problems:
            print(f"    {problem}")
        print("  Fix them (or add the file to .gitignore) before you push.")
        return 1
    print("  none found - the upload is safe.")
    print()
    print("Next:")
    print("  git add .")
    print('  git commit -m "Aieva - Math Edition v1"')
    print("  git branch -M main")
    print("  git remote add origin https://github.com/<you>/<repo>.git")
    print("  git push -u origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
