#!/usr/bin/env python3
"""생성된 글(output/*.json)을 네이버 블로그 글쓰기 화면에 입력하고 발행한다.

  python3 publish_post.py output/남자보정속옷_20260916_agent.json            # 입력만 하고 발행 전 멈춤(검토용)
  python3 publish_post.py output/남자보정속옷_20260916_agent.json --publish  # 발행까지

- 첫 실행 시 브라우저 창이 뜨면 네이버에 직접 로그인하세요. 로그인 상태는 .browser_profile/ 에 저장됩니다.
- 네이버 에디터 마크업은 자주 바뀌므로, 안 되면 SELECTORS 의 셀렉터를 개발자도구로 확인해 고치세요.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = Path(__file__).resolve().parent
PROFILE = HERE / ".browser_profile"
SELECTORS = {
    "title": ".se-title-text, .se-documentTitle .se-text-paragraph",
    "body": ".se-main-container .se-text-paragraph, .se-component.se-text .se-text-paragraph",
    "publish_open": "button:has-text('발행')",
    "publish_confirm": "button:has-text('발행'):not(:has-text('취소')) >> nth=-1",
    "tag_input": "input[placeholder*='태그'], .tag_input input",
}


def strip_markdown(body: str) -> list[str]:
    """생성 글의 마크다운 흔적을 걷어내고 문단 리스트로 만든다. [사진: ...] 은 안내 줄로 남긴다."""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            out.append("")
            continue
        s = re.sub(r"^#{1,6}\s*", "", s)                # 소제목 #
        s = re.sub(r"^[-*]\s+", "· ", s)               # 불릿
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)         # 굵게
        if s.startswith("|"):                           # 표는 셀을 ' / ' 로 이어 붙임
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r"-+", c) for c in cells if c):
                continue
            s = " / ".join(c for c in cells if c)
        out.append(s)
    return out


def type_paragraphs(page, paragraphs):
    for para in paragraphs:
        if para:
            page.keyboard.insert_text(para)
        page.keyboard.press("Enter")
        time.sleep(0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post_json")
    ap.add_argument("--blog-id", help="네이버 블로그 아이디 (생략 시 로그인한 계정의 글쓰기 페이지 사용)")
    ap.add_argument("--publish", action="store_true", help="발행 버튼까지 누름. 없으면 입력 후 대기")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    post = json.loads(Path(args.post_json).read_text(encoding="utf-8"))
    title = post.get("title") or post.get("제목") or ""
    body = post.get("body") or post.get("본문") or ""
    tags = (post.get("hashtags") or post.get("해시태그") or "").replace("#", " ").split()
    if not title or not body:
        sys.exit("제목/본문이 비어 있습니다.")

    write_url = f"https://blog.naver.com/{args.blog_id}?Redirect=Write&" if args.blog_id else "https://blog.naver.com/GoBlogWrite.naver"
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), headless=args.headless, viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(write_url, wait_until="domcontentloaded")

        # 로그인 안 되어 있으면 로그인 페이지로 튕긴다 → 사용자가 직접 로그인할 때까지 대기(최대 5분)
        if "nid.naver.com" in page.url:
            print("브라우저에서 네이버 로그인을 해 주세요 (5분 대기)...", file=sys.stderr)
            page.wait_for_url(lambda u: "nid.naver.com" not in u, timeout=300_000)
            page.goto(write_url, wait_until="domcontentloaded")

        # 글쓰기 에디터는 mainFrame 안에 있을 수도, 최상위에 있을 수도 있다
        frame = page
        for f in page.frames:
            if "PostWriteForm" in f.url or "postwrite" in f.url.lower():
                frame = f
                break
        try:
            frame.wait_for_selector(SELECTORS["title"], timeout=30_000)
        except PWTimeout:
            sys.exit("에디터 제목 영역을 찾지 못했습니다. SELECTORS['title'] 을 확인하세요.")

        # 이어쓰기 팝업이 뜨면 '취소'
        for txt in ("취소", "아니오"):
            btn = frame.locator(f"button:has-text('{txt}')").first
            if btn.count() and btn.is_visible():
                btn.click()
                break

        frame.locator(SELECTORS["title"]).first.click()
        page.keyboard.insert_text(title)
        frame.locator(SELECTORS["body"]).first.click()
        type_paragraphs(page, strip_markdown(body))
        print(f"입력 완료: 제목 {len(title)}자, 본문 {len(body)}자", file=sys.stderr)

        if not args.publish:
            print("발행 전 상태로 멈췄습니다. 검토 후 브라우저에서 직접 발행하거나 --publish 로 다시 실행하세요. (Ctrl+C 로 종료)", file=sys.stderr)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                return

        frame.locator(SELECTORS["publish_open"]).first.click()
        tag_box = frame.locator(SELECTORS["tag_input"]).first
        if tag_box.count():
            tag_box.click()
            for t in tags[:10]:
                page.keyboard.insert_text(t)
                page.keyboard.press("Enter")
        frame.locator(SELECTORS["publish_confirm"]).click()
        page.wait_for_url(re.compile(r"blog\.naver\.com/.+/\d+"), timeout=60_000)
        print(f"발행 완료: {page.url}")
        ctx.close()


if __name__ == "__main__":
    main()
