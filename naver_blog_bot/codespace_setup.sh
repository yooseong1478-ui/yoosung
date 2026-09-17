#!/usr/bin/env bash
# Codespace 가 처음 만들어질 때 한 번 실행 (devcontainer postCreateCommand). 실패하면 원인을 남기고 멈춘다.
set -euo pipefail
cd "$(dirname "$0")"
LOG=work/setup.log
mkdir -p work
exec > >(tee -a "$LOG") 2>&1
echo "=== [1/4] 한글 폰트 설치 ==="
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq fonts-noto-cjk fonts-nanum >/dev/null
echo "=== [2/4] 파이썬 패키지 ==="
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "=== [3/4] 브라우저(Chromium) ==="
python3 -m playwright install --with-deps chromium
echo "=== [4/4] Claude Code CLI ==="
npm install -g @anthropic-ai/claude-code >/dev/null
claude --version
echo "=== 설치 완료 $(date) ==="
