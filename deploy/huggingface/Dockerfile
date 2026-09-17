# Hugging Face Space 에 "이 파일 하나만" 올리면 되는 Dockerfile.
# Space 만들기 → SDK: Docker → Files → "Create new file" → 이름 Dockerfile → 아래 내용 붙여넣기 → Commit.
# 빌드 시 GitHub 저장소를 받아 와 설치하고, 사이트를 7860 포트로 띄운다.
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 NAVER_BOT_CLOUD=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers PORT=7860 \
    REPO_URL=https://github.com/yooseong1478-ui/yoosung.git \
    REPO_BRANCH=claude/naver-blog-correction-wear-bot-xqnsqm

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git curl fonts-noto-cjk fonts-nanum ca-certificates >/dev/null \
    && rm -rf /var/lib/apt/lists/* && useradd -m -u 1000 user
WORKDIR /app
RUN git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" /app \
    && pip install --no-cache-dir -r /app/naver_blog_bot/requirements.txt \
    && python -m playwright install --with-deps chromium && chmod -R a+rX /opt/pw-browsers \
    && chown -R user:user /app
USER user
ENV HOME=/home/user
EXPOSE 7860
CMD ["python3", "naver_blog_bot/dashboard/app.py"]
