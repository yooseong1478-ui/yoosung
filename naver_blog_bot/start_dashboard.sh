#!/usr/bin/env bash
# 맥/리눅스: ./start_dashboard.sh  → 브라우저가 http://127.0.0.1:8787 을 엽니다
cd "$(dirname "$0")"
python3 -c "import fastapi, playwright" 2>/dev/null || { pip3 install -r requirements.txt && python3 -m playwright install chromium; }
python3 dashboard/app.py
