# Prepare the project for GitHub (Windows).
#
#   .\scripts\publish.ps1
#
# It creates the repository, adds the files and makes the first commit.
# The push itself is printed at the end - the credentials stay with you.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git is not installed - see https://git-scm.com/downloads"
}

if (-not (Test-Path .git)) {
    Write-Host "[aieva] creating the repository..."
    git init | Out-Null
}

if (-not (git config user.name)) {
    Write-Host "[aieva] first set your name and your mail:"
    Write-Host '   git config user.name  "Your Name"'
    Write-Host '   git config user.email "you@example.com"'
    Write-Host ""
}

Write-Host "[aieva] the files that will be uploaded:"
python scripts/check_release.py
Write-Host ""

git add -A
if ($LASTEXITCODE -ne 0) { Write-Error "git add failed" }

if (git diff --cached --quiet) {
    Write-Host "[aieva] nothing to commit - the files are already committed."
} else {
    git commit -m "Aieva - Math Edition v1"
}
git branch -M main

Write-Host ""
Write-Host "[aieva] the last step - create an empty repository on github.com"
Write-Host "and then run:"
Write-Host "   git remote add origin https://github.com/<you>/<repo>.git"
Write-Host "   git push -u origin main"
