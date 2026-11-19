#!/usr/bin/env bash
# Prepare the project for GitHub (Linux / macOS).
#
#   ./scripts/publish.sh
#
# It creates the repository, adds the files and makes the first commit.
# The push itself is printed at the end - the credentials stay with you.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v git > /dev/null 2>&1; then
  echo "[aieva] git is not installed" >&2
  exit 1
fi

if [ ! -d .git ]; then
  echo "[aieva] creating the repository..."
  git init
fi

if [ -z "$(git config user.name || true)" ]; then
  echo "[aieva] first set your name and your mail:"
  echo '   git config user.name  "Your Name"'
  echo '   git config user.email "you@example.com"'
  echo ""
fi

echo "[aieva] the files that will be uploaded:"
python3 scripts/check_release.py
echo ""

git add -A
if git diff --cached --quiet; then
  echo "[aieva] nothing to commit - the files are already committed."
else
  git commit -m "Aieva - Math Edition v1"
fi
git branch -M main

echo ""
echo "[aieva] the last step - create an empty repository on github.com"
echo "and then run:"
echo "   git remote add origin https://github.com/<you>/<repo>.git"
echo "   git push -u origin main"
