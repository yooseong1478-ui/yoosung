@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM 더블클릭하면 브라우저 창이 뜹니다. 네이버 로그인 후 글이 자동 입력됩니다.
REM 실제 발행까지 하려면: publish_local.bat --publish
where python >nul 2>nul || (echo Python 이 없습니다. https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요. & pause & exit /b 1)
python -c "import playwright" 2>nul || (pip install playwright && python -m playwright install chromium)
python publish_post.py samples\남자보정속옷_뉴슬림엑스.md %*
pause
