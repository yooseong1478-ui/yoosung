#!/usr/bin/env bash
# 사용법: ./run.sh [config.json]
# 1) 상위노출 글 + 제품 페이지 수집  2) claude -p 로 글 생성
set -euo pipefail
cd "$(dirname "$0")"
CFG="${1:-config.json}"
[ -f "$CFG" ] || { echo "config 가 없습니다. cp config.example.json config.json 후 수정하세요."; exit 1; }
python3 fetch_sources.py --config "$CFG"
python3 generate_post.py --config "$CFG"
