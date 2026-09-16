#!/usr/bin/env python3
"""slides.json 을 1080x1080 PNG 로 렌더링한다 (Playwright 스크린샷).
사용: python3 make_images.py work/<작업>/slides.json [시리즈라벨] [블로그이름]"""
import html
import json
import os
import sys
from pathlib import Path

TEMPLATE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<style>
 html,body{{margin:0;width:1080px;height:1080px;background:#F7F5F0;font-family:Pretendard,-apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:#374151}}
 .wrap{{box-sizing:border-box;width:1080px;height:1080px;padding:96px;display:flex;flex-direction:column}}
 .label{{font-size:28px;color:#2563EB;font-weight:600;letter-spacing:.02em}}
 h1{{font-size:64px;line-height:1.25;color:#1F2937;margin:28px 0 48px;font-weight:800;word-break:keep-all}}
 ul{{list-style:none;padding:0;margin:0;flex:1}}
 li{{font-size:40px;line-height:1.5;margin:0 0 22px;padding-left:52px;position:relative;word-break:keep-all}}
 li:before{{content:"";position:absolute;left:0;top:26px;width:20px;height:20px;border-radius:50%;background:#2563EB}}
 .foot{{display:flex;justify-content:space-between;font-size:26px;color:#6B7280}}
</style></head><body><div class="wrap">
 <div class="label">{label}</div><h1>{title}</h1><ul>{items}</ul>
 <div class="foot"><span>{footnote}</span><span>{blog}</span></div>
</div></body></html>"""


def _chromium():
    exe = os.environ.get("PW_CHROMIUM")
    if not exe and Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome").exists():
        exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    args = ["--no-sandbox"] if (hasattr(os, "geteuid") and os.geteuid() == 0) else []
    return exe, args


def render(slides, out_dir: Path, label="", blog=""):
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    exe, args = _chromium()
    made = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, executable_path=exe or None, args=args)
        page = b.new_page(viewport={"width": 1080, "height": 1080})
        for s in slides:
            if s.get("type") != "slide":
                continue
            items = "".join(f"<li>{html.escape(str(i))}</li>" for i in s.get("items", [])[:5])
            page.set_content(TEMPLATE.format(label=html.escape(s.get("label", label)), title=html.escape(s.get("title", "")),
                                             items=items, footnote=html.escape(s.get("footnote", "")), blog=html.escape(blog)))
            page.wait_for_timeout(200)
            f = out_dir / f"slide_{int(s['index']):02d}.png"
            page.screenshot(path=str(f))
            s["file"] = f.name
            made.append(f)
        b.close()
    return made


if __name__ == "__main__":
    src = Path(sys.argv[1])
    slides = json.loads(src.read_text(encoding="utf-8"))
    files = render(slides, src.parent / "images", label=sys.argv[2] if len(sys.argv) > 2 else "",
                   blog=sys.argv[3] if len(sys.argv) > 3 else "")
    src.write_text(json.dumps(slides, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(files)}장 렌더링: {src.parent / 'images'}")
