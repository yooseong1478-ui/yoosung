#!/usr/bin/env python3
"""생성된 글(output/*.json)을 네이버 블로그 글쓰기 화면에 입력하고 발행한다.

  python3 publish_post.py samples/남자보정속옷_뉴슬림엑스.md            # 입력만 하고 발행 전 멈춤(검토용)
  python3 publish_post.py samples/남자보정속옷_뉴슬림엑스.md --publish  # 발행까지  (.md 또는 output/*.json 모두 가능)

- 첫 실행 시 브라우저 창이 뜨면 네이버에 직접 로그인하세요. 로그인 상태는 .browser_profile/ 에 저장됩니다.
- 네이버 에디터 마크업은 자주 바뀌므로, 안 되면 SELECTORS 의 셀렉터를 개발자도구로 확인해 고치세요.
"""
import argparse
import json
import os
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
    "save_draft": "button:has-text('저장'):not(:has-text('임시저장 글'))",
    "image_button": "button[data-name='image'], button:has-text('사진'), .se-toolbar-item-image button",
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


def insert_image(page, frame, path: Path):
    """에디터 툴바의 사진 버튼 → 파일 선택창에 파일을 넣는다. 실패하면 False."""
    try:
        with page.expect_file_chooser(timeout=8_000) as fc:
            frame.locator(SELECTORS["image_button"]).first.click()
        fc.value.set_files(str(path))
        page.wait_for_timeout(2500)          # 업로드 대기
        page.keyboard.press("End")
        page.keyboard.press("Enter")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"이미지 삽입 실패 {path.name}: {e}", file=sys.stderr)
        return False


def type_paragraphs(page, paragraphs, frame=None, images_dir: Path | None = None):
    for para in paragraphs:
        m = re.fullmatch(r"\[\[IMG:(.+?)\]\]", para.strip()) if para else None
        if m and images_dir and (images_dir / m.group(1)).exists():
            if insert_image(page, frame or page, images_dir / m.group(1)):
                continue
            para = f"(이미지 넣기: {m.group(1)})"
        elif para and para.strip().startswith("[[PHOTO:"):
            para = "(사진 넣기: " + para.strip()[8:-2] + ")"
        heading = bool(para) and bool(re.match(r"^(📌|STEP ?\d|☑️ 이런|■|▶|\d+\.\s)", para.strip()))
        if heading:                      # 소제목은 굵게 (진짜 블로거처럼 보이도록)
            page.keyboard.press("Control+b")
        if para:
            page.keyboard.insert_text(para)
        if heading:
            page.keyboard.press("Control+b")
        page.keyboard.press("Enter")
        time.sleep(0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post_json")
    ap.add_argument("--blog-id", help="네이버 블로그 아이디 (생략 시 로그인한 계정의 글쓰기 페이지 사용)")
    ap.add_argument("--publish", action="store_true", help="발행 버튼까지 누름. 없으면 입력 후 대기")
    ap.add_argument("--draft", action="store_true", help="발행하지 않고 임시저장(저장 버튼)까지만 하고 종료")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--cookies", default=os.environ.get("NAVER_COOKIES", ""),
                    help="브라우저에서 복사한 네이버 쿠키 문자열 (NID_AUT=...; NID_SES=...). CI 발행용, 환경변수 NAVER_COOKIES 로도 지정")
    ap.add_argument("--shot-dir", default="", help="실패/완료 시 스크린샷 저장 폴더")
    args = ap.parse_args()
    src = Path(args.post_json)
    if src.suffix.lower() == ".md":
        lines = src.read_text(encoding="utf-8").splitlines()
        lines = [l for l in lines]
        while lines and not lines[0].strip():
            lines.pop(0)
        title = lines.pop(0).lstrip("# ").strip() if lines else ""
        tag_line = ""
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                if lines[i].strip().startswith("#"):
                    tag_line = lines.pop(i)
                break
        post = {"title": title, "body": "\n".join(lines).strip(), "hashtags": tag_line}
    else:
        post = json.loads(src.read_text(encoding="utf-8"))
    title = post.get("title") or post.get("제목") or ""
    body = post.get("body") or post.get("본문") or ""
    tags = (post.get("hashtags") or post.get("해시태그") or "").replace("#", " ").split()
    images_dir = Path(post["images_dir"]) if post.get("images_dir") else src.parent / "images"
    if not title or not body:
        sys.exit("제목/본문이 비어 있습니다.")

    write_url = f"https://blog.naver.com/{args.blog_id}?Redirect=Write&" if args.blog_id else "https://blog.naver.com/GoBlogWrite.naver"
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), headless=args.headless, viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        shot_dir = Path(args.shot_dir) if args.shot_dir else None
        if shot_dir:
            shot_dir.mkdir(parents=True, exist_ok=True)

        def shot(name):
            if shot_dir:
                try:
                    page.screenshot(path=str(shot_dir / f"{name}.png"), full_page=True)
                except Exception:  # noqa: BLE001
                    pass

        if args.cookies:
            cookies = []
            for part in args.cookies.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies.append({"name": k, "value": v, "domain": ".naver.com", "path": "/"})
            ctx.add_cookies(cookies)
        page.goto(write_url, wait_until="domcontentloaded")

        # 로그인 안 되어 있으면 로그인 페이지로 튕긴다
        if "nid.naver.com" in page.url:
            if args.headless or args.cookies:
                shot("login_required")
                sys.exit("로그인이 필요합니다. 쿠키가 만료됐거나 새 기기 인증이 걸렸습니다. 로컬에서 창을 띄워 로그인하세요.")
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
            shot("editor_not_found")
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
        type_paragraphs(page, strip_markdown(body), frame, images_dir)
        print(f"입력 완료: 제목 {len(title)}자, 본문 {len(body)}자", file=sys.stderr)
        shot("filled")

        if args.draft:
            btn = frame.locator(SELECTORS["save_draft"]).first
            if btn.count():
                btn.click()
                page.wait_for_timeout(2000)
                shot("draft_saved")
                print("임시저장 완료. 네이버 블로그 글쓰기 → 임시저장 글 목록에서 검수 후 발행하세요.", file=sys.stderr)
            else:
                shot("draft_button_missing")
                print("저장 버튼을 찾지 못했습니다. SELECTORS['save_draft'] 를 확인하세요.", file=sys.stderr)
            ctx.close()
            return

        if not args.publish and args.headless:
            print("헤드리스 점검 모드: 입력까지만 확인하고 종료합니다 (--publish 없음).", file=sys.stderr)
            ctx.close()
            return
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
        shot("publish_dialog")
        frame.locator(SELECTORS["publish_confirm"]).click()
        try:
            page.wait_for_url(re.compile(r"blog\.naver\.com/.+/\d+"), timeout=60_000)
        except PWTimeout:
            shot("publish_failed")
            sys.exit(f"발행 확인 실패. 현재 URL: {page.url}")
        shot("published")
        print(f"발행 완료: {page.url}")
        if shot_dir:
            (shot_dir / "published_url.txt").write_text(page.url, encoding="utf-8")
        ctx.close()


if __name__ == "__main__":
    main()
