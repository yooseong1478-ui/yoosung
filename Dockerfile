# 네이버 블로그 자동화 대시보드 — 어떤 Docker 호스팅(Hugging Face Spaces, Render, Railway, 본인 서버)에서도 동작
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    NAVER_BOT_CLOUD=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    PORT=7860

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        git curl fonts-noto-cjk fonts-nanum ca-certificates >/dev/null \
    && rm -rf /var/lib/apt/lists/*

# 실행 계정 (Hugging Face Spaces 는 uid 1000 필요)
RUN useradd -m -u 1000 user
WORKDIR /app

COPY naver_blog_bot/requirements.txt /app/naver_blog_bot/requirements.txt
RUN pip install --no-cache-dir -r /app/naver_blog_bot/requirements.txt \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rX /opt/pw-browsers

COPY . /app
RUN chown -R user:user /app
USER user
ENV HOME=/home/user

EXPOSE 7860
CMD ["python3", "naver_blog_bot/dashboard/app.py"]
