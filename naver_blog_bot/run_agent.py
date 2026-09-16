#!/usr/bin/env python3
"""claude -p 가 Playwright MCP 브라우저로 직접 네이버·제품 페이지를 열어 읽고 글을 쓰게 한다.

  python3 run_agent.py                # config.json 사용
  python3 run_agent.py --dry-run      # 프롬프트만 출력
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
SECTIONS = ("제목", "본문", "해시태그", "패턴분석", "수집자료")


def build_prompt(cfg):
    tpl = (HERE / "prompts" / "agent_prompt.md").read_text(encoding="utf-8")
    return tpl.format(
        keyword=cfg["keyword"], keyword_enc=quote(cfg["keyword"]), top_n=int(cfg.get("top_n", 3)),
        product_name=cfg.get("product_name", ""), product_urls="\n".join(cfg.get("product_urls", [])),
        brand_notes=cfg.get("brand_notes", ""), min_chars=cfg.get("min_chars", 2000),
    )


def split_sections(text):
    names = "|".join(SECTIONS)
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(rf"===({names})===\s*(.*?)(?=\n===|\Z)", text, re.S)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="output")
    ap.add_argument("--max-turns", type=int, default=40, help="브라우저 도구 호출 상한")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    prompt = build_prompt(cfg)
    if args.dry_run:
        print(prompt)
        return

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{cfg['keyword']}_{date.today():%Y%m%d}_agent"
    cmd = [
        "claude", "-p", "--output-format", "text",
        "--mcp-config", str(HERE / ".mcp.json"), "--strict-mcp-config",
        "--allowedTools", "mcp__playwright",
        "--permission-mode", "dontAsk",
        "--max-turns", str(args.max_turns),
    ]
    if cfg.get("claude_model"):
        cmd += ["--model", cfg["claude_model"]]
    print("실행:", " ".join(cmd), file=sys.stderr)
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    (out_dir / f"{stem}.raw.md").write_text(r.stdout, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"claude -p 실패 (code {r.returncode}):\n{r.stderr[-2000:]}")
    sec = split_sections(r.stdout)
    if "본문" not in sec:
        sys.exit(f"출력 구분자를 찾지 못했습니다. 원문: {out_dir / (stem + '.raw.md')}\n{r.stdout[-1500:]}")
    post = {k: sec.get(k, "") for k in SECTIONS}
    post.update({"keyword": cfg["keyword"], "date": str(date.today())})
    (out_dir / f"{stem}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(f"# {post['제목']}\n\n{post['본문']}\n\n{post['해시태그']}\n", encoding="utf-8")
    print(f"완료: {out_dir / (stem + '.md')}  (본문 {len(post['본문'])}자)")


if __name__ == "__main__":
    main()
