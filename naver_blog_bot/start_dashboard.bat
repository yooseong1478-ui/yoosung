@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 네이버 블로그 자동화 대시보드 시작 ===
where python >nul 2>nul || (echo Python 이 없습니다. https://www.python.org/downloads/ 에서 설치할 때 "Add python.exe to PATH" 를 체크하고 다시 실행하세요. & pause & exit /b 1)
python -c "import fastapi, playwright" 2>nul || (echo 필요한 프로그램을 설치합니다 (처음 한 번, 2~5분)... & pip install -r requirements.txt & python -m playwright install chromium)
where claude >nul 2>nul || echo [안내] Claude Code(claude) 가 없으면 글쓰기 단계가 동작하지 않습니다. https://claude.ai/code 안내대로 설치 후 claude 를 한 번 실행해 로그인하세요.
python dashboard\app.py
pause
