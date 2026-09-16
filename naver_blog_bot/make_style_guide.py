#!/usr/bin/env python3
"""내가 쓴 글 2~3편(.txt/.md 폴더)을 넣으면 team/01_style_guide.md 를 생성한다.
사용: python3 make_style_guide.py my_posts/"""
import sys
from pathlib import Path

from claude_cli import claude_p

HERE = Path(__file__).resolve().parent
folder = Path(sys.argv[1])
posts = [p.read_text(encoding="utf-8") for p in sorted(folder.glob("*")) if p.suffix.lower() in (".txt", ".md")]
if not posts:
    sys.exit("폴더에 .txt 또는 .md 글이 없습니다.")
prompt = ("아래는 내가 직접 쓴 블로그 글입니다. 문장 길이, 자주 쓰는 표현과 어미, 줄바꿈 습관, 시작과 마무리 방식, "
          "이모지·기호 사용, 피하는 표현을 분석해 다른 작성자가 그대로 따라 쓸 수 있는 '스타일 가이드' 마크다운을 작성하세요. "
          "섹션: 문체 / 시작 / 마무리 / 자주 쓰는 표현 / 피할 표현. 제목은 '# 스타일 가이드 (내 말투)' 로 시작하고 마크다운만 출력하세요.\n\n"
          + "\n\n=====\n\n".join(posts[:5]))
out = claude_p(prompt)
(HERE / "team" / "01_style_guide.md").write_text(out.strip() + "\n", encoding="utf-8")
print("team/01_style_guide.md 갱신 완료")
