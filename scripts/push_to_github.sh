#!/usr/bin/env bash
# 推送代码到 https://github.com/tongjialiang/supercare
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

GIT=(git -c safe.directory="$REPO_ROOT")
REMOTE="${GITHUB_REMOTE:-git@github.com:tongjialiang/supercare.git}"

"${GIT[@]}" remote set-url origin "$REMOTE" 2>/dev/null || "${GIT[@]}" remote add origin "$REMOTE"

echo ">>> 推送到 $REMOTE (main) ..."
"${GIT[@]}" push -u origin main --force

echo ">>> 完成: https://github.com/tongjialiang/supercare"
