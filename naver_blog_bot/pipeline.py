#!/usr/bin/env python3
"""팀장 역할: topics.md 의 주제 한 줄 → 리서치 → 글쓰기 → 이미지 → 조립. 결과는 work/<날짜_키워드>/.

  python3 pipeline.py                 # topics.md 맨 위 미완료 주제 처리
  python3 pipeline.py --topic "남자보정속옷" --product-url URL
  python3 pipeline.py --steps write,image,assemble --work work/20260916_남자보정속옷   # 일부 단계만 재실행
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from claude_cli import claude_p, extract_json

HERE = Path(__file__).resolve().parent
TEAM = HERE / "team"


def read(p):
    return Path(p).read_text(encoding="utf-8")


def report(step, msg):
    print(f"[팀장] {step} 완료: {msg}", file=sys.stderr)


# ------------------------------------------------------------- 주제 큐
def pick_topic():
    lines = read(HERE / "topics.md").splitlines()
    for i, l in enumerate(lines):
        m = re.match(r"^- \[ \]\s*(.+)$", l.strip())
        if m:
            parts = [x.strip() for x in m.group(1).split("|")]
            return i, parts[0], (parts[1] if len(parts) > 1 else ""), (parts[2] if len(parts) > 2 else "")
    return None


def mark_done(idx, note):
    p = HERE / "topics.md"
    lines = read(p).splitlines()
    lines[idx] = lines[idx].replace("- [ ]", "- [x]", 1) + f"  ← {note}"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------- 1. 리서치
def research_context_from_collected(keyword):
    d = HERE / "collected" / keyword
    if not (d / "posts.json").exists():
        return None
    posts = json.loads(read(d / "posts.json"))
    ctx = [f"# 수집 자료 (키워드: {keyword})", "## 네이버 블로그 상위노출 글 (광고 제외, 순위순)"]
    for p in posts[:5]:
        ctx.append(f"### {p['rank']}위 | {p['title']} | {p['url']} | 사진 {p['images']}장\n{p['body'][:3500]}\n")
    if (d / "products.json").exists():
        for pr in json.loads(read(d / "products.json")):
            if pr.get("detail_text"):
                ctx.append(f"## 제품 페이지 {pr['url']}\n{pr['name']}\n옵션: {', '.join(pr['options'])}\n{pr['detail_text'][:2500]}\n")
    ex = d / "extra" / "extra.json"
    if ex.exists():
        e = json.loads(read(ex))
        for pr in e.get("products", []):
            ocr = "\n".join(im["ocr"] for im in pr["images"] if im.get("ocr"))
            ctx.append(f"## 제품 상세 {pr['url']}\n{pr['info'][:800]}\n{pr['detail_text'][:1500]}\n[상세 이미지 OCR]\n{ocr[:3000]}\n")
        qna = [q["text"][:800] for q in e.get("qna", []) if re.search(r"사이즈|입는|차이", q["text"])][:4]
        if qna:
            ctx.append("## 공식몰 Q&A 발췌\n" + "\n---\n".join(qna))
    return "\n".join(ctx)


def step_research(work, keyword, product_url, memo, cfg, use_browser):
    role = read(TEAM / "03_researcher.md")
    ctx = research_context_from_collected(keyword)
    if ctx:
        prompt = (f"{role}\n\n---\n주제: {keyword}\n제품 URL: {product_url}\n메모: {memo}\n\n"
                  f"아래 수집 자료만 근거로 research.md 를 작성하세요. 브라우저는 쓰지 않습니다.\n\n{ctx}")
        out = claude_p(prompt, cfg.get("claude_model", ""))
    elif use_browser:
        prompt = (f"{role}\n\n---\n주제: {keyword}\n제품 URL: {product_url}\n메모: {memo}\n\n"
                  f"playwright 브라우저 도구로 https://m.search.naver.com/search.naver?where=m_blog&query={keyword} 와 "
                  f"제품 URL 을 직접 열어 읽고 research.md 를 작성하세요.")
        out = claude_p(prompt, cfg.get("claude_model", ""),
                       ["--mcp-config", str(HERE / ".mcp.json"), "--strict-mcp-config",
                        "--allowedTools", "mcp__playwright", "--max-turns", "40"], cwd=HERE, tools=True)
    else:
        sys.exit(f"collected/{keyword}/ 가 없습니다. GitHub Actions 'collect-naver-sources' 를 실행하거나 --browser 로 실행하세요.")
    (work / "research.md").write_text(out, encoding="utf-8")
    report("1단계 리서치", f"{len(out)}자, research.md")
    return out


# ------------------------------------------------------------- 2. 글쓰기
def measure(post_md):
    lines = post_md.strip().splitlines()
    title = lines[0].lstrip("# ").strip() if lines else ""
    body = "\n".join(lines[1:])
    txt = re.sub(r"\[사진:[^\]]*\]", "", body)
    txt = re.sub(r"#\S+", "", txt)
    chars = len(re.sub(r"\s", "", txt))
    photos = len(re.findall(r"\[사진:", body))
    segs = [len(re.sub(r"\s", "", s)) for s in re.split(r"\[사진:[^\]]*\]", body)]
    return {"title_len": len(title), "chars": chars, "photos": photos, "max_gap": max(segs) if segs else 0, "title": title}


def step_write(work, keyword, cfg, product_url="", feedback="", prev=""):
    fixed = (f"검색 키워드: {keyword}\n"
             f"- 제목 맨 앞과 첫 문단에는 반드시 이 검색 키워드(띄어쓰기는 허용: '{keyword}' 또는 '{keyword.replace('보정속옷', ' 보정속옷')}')를 넣습니다. "
             f"research.md 의 선택 키워드·롱테일 문구는 보조 키워드로 본문에 3~5회 씁니다.\n"
             + (f"- 구매처는 반드시 이 주소로 안내합니다: {product_url}\n" if product_url else ""))
    redo = ""
    if feedback:
        redo = (f"=== 팀장 재작업 요청 ===\n{feedback}\n아래 '이전 원고'를 바탕으로 문제만 고치세요. 잘 된 부분은 유지하고, "
                f"분량을 늘려야 하면 새 소제목이나 체험 문단을 추가하세요(줄이지 마세요).\n=== 이전 원고 ===\n{prev}\n")
    prompt = (f"{read(TEAM / '04_writer.md')}\n\n=== 스타일 가이드 ===\n{read(TEAM / '01_style_guide.md')}\n\n"
              f"=== SEO 규칙 ===\n{read(TEAM / '02_seo_rules.md')}\n\n=== research.md ===\n{read(work / 'research.md')}\n\n"
              f"{fixed}\n{redo}\npost.md 내용만 출력하세요 (설명, 코드펜스 없이).")
    out = claude_p(prompt, cfg.get("claude_model", "")).strip()
    out = re.sub(r"^```\w*\n|\n```$", "", out)
    m = measure(out)
    report("2단계 글쓰기", f"제목 {m['title_len']}자, 본문 {m['chars']}자, 사진 {m['photos']}곳, 최대 사진 간격 {m['max_gap']}자")
    return out, m


def lead_review_post(m):
    issues = []
    if not 25 <= m["title_len"] <= 60:
        issues.append(f"제목 {m['title_len']}자 → 33~51자로")
    if m["chars"] < 1150:
        issues.append(f"본문이 공백 제외 {m['chars']}자로 짧음 → 최소 {1300 - m['chars']}자 이상 추가해 1,300~1,900자로 (STEP 하나 추가 또는 각 STEP 에 체험 문단 2~3줄 추가)")
    elif m["chars"] > 2100:
        issues.append(f"본문 {m['chars']}자 → 1,300~1,900자로 줄이기")
    if m["photos"] < 14:
        issues.append(f"사진 자리 {m['photos']}곳 → 17곳 이상으로")
    if m["max_gap"] > 320:
        issues.append(f"사진 없이 {m['max_gap']}자 이어짐 → 90~170자마다 [사진: ] 삽입")
    return issues


# ------------------------------------------------------------- 3. 이미지
ASSETS = HERE / "assets" / "newslimx"


def asset_list_text():
    mf = ASSETS / "manifest.json"
    if not mf.exists():
        return "(없음)"
    m = json.loads(read(mf))
    return m.get("note", "") + "\n" + "\n".join(f"- {i['file']}: {i['desc']}" for i in m["images"])


def place_assets(slides, work):
    """type=asset 항목의 공식 이미지를 work/images 로 복사하고 file 을 파일명으로 맞춘다."""
    import shutil
    (work / "images").mkdir(parents=True, exist_ok=True)
    for s in slides:
        if s.get("type") == "asset" and s.get("file"):
            src = ASSETS / Path(s["file"]).name
            if src.exists():
                dst = work / "images" / f"asset_{int(s['index']):02d}_{src.name}"
                shutil.copy(src, dst)
                s["file"] = dst.name
            else:
                s["type"], s["note"] = "photo", f"공식 이미지 {s['file']} 없음"
                s.pop("file", None)


def step_images(work, keyword, cfg):
    prompt = (f"{read(TEAM / '05_image_maker.md')}\n\n=== 이미지 스타일 ===\n{read(TEAM / '05_image_style.md')}\n\n"
              f"=== 공식 이미지 목록 (asset 으로 사용 가능) ===\n{asset_list_text()}\n\n"
              f"=== post.md ===\n{read(work / 'post.md')}\n\nslides.json 배열만 출력하세요.")
    slides = extract_json(claude_p(prompt, cfg.get("claude_model", "")))
    placeholders = re.findall(r"\[사진:[^\]]*\]", read(work / "post.md"))
    slides = sorted(slides, key=lambda s: int(s.get("index", 0)))[:len(placeholders)]
    for i, ph in enumerate(placeholders, 1):
        if i > len(slides):
            slides.append({"index": i, "placeholder": ph, "type": "photo", "note": ph})
        slides[i - 1]["index"] = i
        slides[i - 1]["placeholder"] = ph
    (work / "slides.json").write_text(json.dumps(slides, ensure_ascii=False, indent=2), encoding="utf-8")
    from make_images import render
    for old in (work / "images").glob("slide_*.png"):   # 이전 실행 잔재 제거
        old.unlink()
    files = render(slides, work / "images", label=cfg.get("series_label", keyword), blog=cfg.get("blog_name", ""))
    place_assets(slides, work)
    (work / "slides.json").write_text(json.dumps(slides, ensure_ascii=False, indent=2), encoding="utf-8")
    n_photo = sum(1 for s in slides if s.get("type") == "photo")
    n_asset = sum(1 for s in slides if s.get("type") == "asset")
    report("3단계 이미지", f"슬라이드 {len(files)}장 렌더링, 공식 이미지 {n_asset}장, 실사 필요 {n_photo}곳 (work/images)")
    return slides


# ------------------------------------------------------------- 4. 조립 (코드로 결정적으로 처리)
def step_assemble(work):
    post = read(work / "post.md").strip()
    slides = json.loads(read(work / "slides.json"))
    lines = post.splitlines()
    title = lines[0].lstrip("# ").strip()
    rest = lines[1:]
    hashtags = ""
    for i in range(len(rest) - 1, -1, -1):
        if rest[i].strip():
            if rest[i].strip().startswith("#"):
                hashtags = rest.pop(i).strip()
            break
    body = "\n".join(rest).strip()
    images, k = [], 0

    def repl(m):
        nonlocal k
        s = slides[k] if k < len(slides) else {"type": "photo"}
        k += 1
        if s.get("type") in ("slide", "asset") and s.get("file"):
            images.append({"token": f"[[IMG:{s['file']}]]", "file": s["file"], "type": s["type"]})
            return f"[[IMG:{s['file']}]]"
        images.append({"token": f"[[PHOTO:{m.group(1)}]]", "file": "", "type": "photo"})
        return f"[[PHOTO:{m.group(1)}]]"

    body = re.sub(r"\[사진:\s*([^\]]*)\]", repl, body)
    (work / "final.md").write_text(f"{title}\n\n{body}\n\n{hashtags}\n", encoding="utf-8")
    (work / "final.json").write_text(json.dumps({"title": title, "body": body, "hashtags": hashtags, "images": images,
                                                 "images_dir": str(work / "images")}, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    report("4단계 조립", f"final.md / final.json, 이미지 토큰 {len(images)}개")


# ------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--topic")
    ap.add_argument("--product-url", default="")
    ap.add_argument("--memo", default="")
    ap.add_argument("--work", help="기존 작업 폴더 (일부 단계 재실행용)")
    ap.add_argument("--steps", default="research,write,image,assemble")
    ap.add_argument("--browser", action="store_true", help="수집 자료가 없으면 브라우저 에이전트로 리서치")
    ap.add_argument("--no-mark", action="store_true", help="topics.md 완료 표시 안 함")
    args = ap.parse_args()
    cfg = json.loads(read(HERE / args.config)) if (HERE / args.config).exists() else {}
    steps = [s.strip() for s in args.steps.split(",")]

    idx = None
    if args.topic:
        keyword, product_url, memo = args.topic, args.product_url, args.memo
    else:
        t = pick_topic()
        if not t:
            sys.exit("topics.md 에 미완료 주제가 없습니다.")
        idx, keyword, product_url, memo = t
    work = Path(args.work) if args.work else HERE / "work" / f"{date.today():%Y%m%d}_{keyword.replace(' ', '')}"
    work.mkdir(parents=True, exist_ok=True)
    print(f"[팀장] 작업 시작: {keyword} → {work}", file=sys.stderr)

    if "research" in steps:
        step_research(work, keyword, product_url, memo, cfg, args.browser)
    if "write" in steps:
        best, best_issues = None, None
        out, m = step_write(work, keyword, cfg, product_url)
        issues = lead_review_post(m)
        best, best_issues = out, issues
        for attempt in range(2):
            if not issues:
                break
            print(f"[팀장] 글쓰기 재작업 요청 {attempt + 1}: {'; '.join(issues)}", file=sys.stderr)
            out, m = step_write(work, keyword, cfg, product_url, feedback="\n".join(issues), prev=out)
            issues = lead_review_post(m)
            if len(issues) < len(best_issues):
                best, best_issues = out, issues
        (work / "post.md").write_text(best, encoding="utf-8")
        if best_issues:
            print(f"[팀장] 재작업 후에도 남은 문제 (사람 확인 필요): {'; '.join(best_issues)}", file=sys.stderr)
    if "image" in steps:
        step_images(work, keyword, cfg)
    if "assemble" in steps:
        step_assemble(work)
    (HERE / "work" / "LATEST").write_text(str(work), encoding="utf-8")
    if idx is not None and not args.no_mark and "assemble" in steps:
        mark_done(idx, f"{date.today()} {work.name}")
    print(f"[팀장] 전체 완료: {work / 'final.md'}  (다음: python3 publish_post.py {work / 'final.json'} --draft)", file=sys.stderr)


if __name__ == "__main__":
    main()
