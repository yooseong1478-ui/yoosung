#!/usr/bin/env bash
# 전체 파이프라인: 브라우저 에이전트로 수집+작성 → 네이버 블로그 입력(→ --publish 시 발행)
# 사용법: ./run_all.sh [--publish]
set -euo pipefail
cd "$(dirname "$0")"
[ -f config.json ] || { echo "cp config.example.json config.json 후 수정하세요."; exit 1; }
python3 run_agent.py
LATEST=$(ls -t output/*_agent.json | head -1)
python3 publish_post.py "$LATEST" "$@"
