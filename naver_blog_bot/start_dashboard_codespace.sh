#!/usr/bin/env bash
# Codespace 가 켜질 때마다 실행 (devcontainer postStartCommand). 대시보드를 백그라운드로 띄운다.
cd "$(dirname "$0")"
mkdir -p work
if curl -sS -m 2 "http://127.0.0.1:${PORT:-8787}/api/status" >/dev/null 2>&1; then
  echo "대시보드가 이미 실행 중입니다."
  exit 0
fi
nohup python3 dashboard/app.py > work/dashboard.log 2>&1 &
echo "대시보드 시작 (포트 ${PORT:-8787}). 로그: naver_blog_bot/work/dashboard.log"
