#!/usr/bin/env bash
# 로컬 PC에서 실행: 브라우저 창이 뜨면 네이버 로그인 1회 → 글 입력 → (--publish 시) 발행
# 사용법: ./publish_local.sh [글파일] [--publish]
set -euo pipefail
cd "$(dirname "$0")"
POST="${1:-samples/남자보정속옷_뉴슬림엑스.md}"; shift || true
python3 -c "import playwright" 2>/dev/null || { pip install playwright && python3 -m playwright install chromium; }
python3 publish_post.py "$POST" "$@"
