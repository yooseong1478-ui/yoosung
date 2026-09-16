#!/usr/bin/env python3
"""sources/<keyword>/ 의 수집 결과로 프롬프트를 만들고 `claude -p` 로 글을 생성한다."""
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build_prompt(cfg, posts, products):
    tpl = (HERE / "prompts" / "writer_prompt.md").read_text(encoding="utf-8")
    posts_ctx = []
    for p in posts:
        posts_ctx.append(
            f"### 참고 글 {p['rank']}위\n제목: {p['title']}\n글자 수: {len(p['body'])} / 사진: {p['images']}장\n"
            f"소제목: {' | '.join(p.get('headings', [])) or '(감지 안 됨)'}\n해시태그: {' '.join(p.get('hashtags', []))}\n\n{p['body']}\n"
        )
    prod_ctx = []
    for pr in products:
        prod_ctx.append(
            f"### {pr['name']}\nURL: {pr['url']}\n가격: {pr['price']}\n설명: {pr['meta_description']}\n"
            f"옵션/사이즈: {', '.join(pr['options'])}\n이미지 설명: {', '.join(pr['image_alts'])}\n\n{pr['detail_text']}\n"
        )
    return tpl.format(
        keyword=cfg["keyword"], top_n=len(posts), product_name=cfg.get("product_name", ""),
        brand_notes=cfg.get("brand_notes", ""), min_chars=cfg.get("min_chars", 2000),
        product_context="\n".join(prod_ctx) or "(제품 페이지 수집 실패: 브랜드 메모만 사용)",
        posts_context="\n".join(posts_ctx),
    )


def run_claude(prompt, model=""):
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"claude -p 실패 (code {r.returncode}):\n{r.stderr}")
    return r.stdout


def split_sections(text):
    parts = {}
    for m in re.finditer(r"===(제목|본문|해시태그|패턴분석)===\s*(.*?)(?=\n===|\Z)", text, re.S):
        parts[m.group(1)] = m.group(2).strip()
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--sources", default="sources")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true", help="claude 를 호출하지 않고 프롬프트만 저장")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    src = Path(args.sources) / cfg["keyword"]
    posts = json.loads((src / "posts.json").read_text(encoding="utf-8"))
    products = json.loads((src / "products.json").read_text(encoding="utf-8")) if (src / "products.json").exists() else []
    if not posts:
        sys.exit("posts.json 이 비어 있습니다. fetch_sources.py 를 먼저 실행하세요.")

    prompt = build_prompt(cfg, posts, products)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{cfg['keyword']}_{date.today():%Y%m%d}"
    (out_dir / f"{stem}.prompt.md").write_text(prompt, encoding="utf-8")
    if args.dry_run:
        print(f"프롬프트만 저장: {out_dir / (stem + '.prompt.md')}")
        return

    raw = run_claude(prompt, cfg.get("claude_model", ""))
    (out_dir / f"{stem}.raw.md").write_text(raw, encoding="utf-8")
    sec = split_sections(raw)
    if "본문" not in sec:
        sys.exit(f"출력 구분자를 찾지 못했습니다. 원문: {out_dir / (stem + '.raw.md')}")
    post = {"title": sec.get("제목", ""), "body": sec["본문"], "hashtags": sec.get("해시태그", ""),
            "pattern": sec.get("패턴분석", ""), "keyword": cfg["keyword"], "date": str(date.today())}
    (out_dir / f"{stem}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(f"# {post['title']}\n\n{post['body']}\n\n{post['hashtags']}\n", encoding="utf-8")
    print(f"완료: {out_dir / (stem + '.md')}  (본문 {len(post['body'])}자)")


if __name__ == "__main__":
    main()
