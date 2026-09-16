#!/usr/bin/env python3
"""네이버 블로그 통계(CSV/텍스트)를 넣으면 규칙 수정 제안과 다음 주제 후보를 analysis.md 로 만든다.
사용: python3 improve_prompts.py stats.csv [--apply]   (--apply: 제안된 주제를 topics.md 에 추가)"""
import re
import sys
from datetime import date
from pathlib import Path

from claude_cli import claude_p

HERE = Path(__file__).resolve().parent
stats = Path(sys.argv[1]).read_text(encoding="utf-8")
team = HERE / "team"
prompt = (f"{(team / '07_analyst.md').read_text(encoding='utf-8')}\n\n=== 현재 02_seo_rules.md ===\n"
          f"{(team / '02_seo_rules.md').read_text(encoding='utf-8')}\n\n=== 현재 04_writer.md ===\n"
          f"{(team / '04_writer.md').read_text(encoding='utf-8')}\n\n=== 네이버 블로그 통계 ===\n{stats}\n\nanalysis.md 를 작성하세요.")
out = claude_p(prompt)
p = HERE / "work" / f"analysis_{date.today():%Y%m%d}.md"
p.parent.mkdir(exist_ok=True)
p.write_text(out, encoding="utf-8")
print(f"저장: {p}")
if "--apply" in sys.argv:
    topics = re.findall(r"^- \[ \] .+$", out, re.M)
    if topics:
        with open(HERE / "topics.md", "a", encoding="utf-8") as f:
            f.write("\n".join(topics) + "\n")
        print(f"topics.md 에 주제 {len(topics)}개 추가")
    print("규칙 수정은 analysis.md 를 보고 team/02_seo_rules.md 에 직접 반영하세요 (자동 반영하지 않습니다).")
