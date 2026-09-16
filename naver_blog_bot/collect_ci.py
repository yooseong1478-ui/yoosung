#!/usr/bin/env python3
"""CI(GitHub Actions)용 수집기: 검색 결과·상위 글·제품 페이지의 원본 HTML과 파싱 결과를 collected/<keyword>/ 에 저장한다.
실패해도 중단하지 않고 log.txt 에 남긴다."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_sources as fs  # noqa: E402

cfg = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "config.example.json").read_text(encoding="utf-8"))
keyword, top_n = cfg["keyword"], int(cfg.get("top_n", 3)) + 2
out = Path("collected") / keyword
raw = out / "raw"
raw.mkdir(parents=True, exist_ok=True)
log = []


def note(msg):
    print(msg, file=sys.stderr)
    log.append(msg)


def save(name, text):
    (raw / name).write_text(text, encoding="utf-8")


# 1) 검색 결과 (PC 블로그탭, 모바일 블로그탭)
links = []
for name, url, mobile in [
    ("search_pc.html", f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={quote(keyword)}", False),
    ("search_mobile.html", f"https://m.search.naver.com/search.naver?where=m_blog&sm=mtb_jum&query={quote(keyword)}", True),
]:
    try:
        html = fs.get(url, mobile=mobile).text
        save(name, html)
        found = re.findall(r'https?://(?:m\.)?blog\.naver\.com/([A-Za-z0-9_\-]+)/(\d+)', html)
        found += [(m.group(1), m.group(2)) for m in re.finditer(r'blogId=([A-Za-z0-9_\-]+)&(?:amp;)?logNo=(\d+)', html)]
        seen = []
        for bid, lno in found:
            if (bid, lno) not in seen:
                seen.append((bid, lno))
        note(f"[검색] {name}: {len(html)} bytes, 블로그 링크 {len(seen)}개")
        links.append((name, seen))
    except Exception as e:  # noqa: BLE001
        note(f"[검색] {name} 실패: {e}")

order = []
for _, seen in links:            # PC 결과를 우선, 모바일 결과로 보충
    for ids in seen:
        if ids not in order:
            order.append(ids)
(out / "search_links.json").write_text(json.dumps([{"blogId": b, "logNo": l} for b, l in order], ensure_ascii=False, indent=2), encoding="utf-8")

# 2) 상위 글 본문
posts = []
for bid, lno in order[:top_n]:
    for url, mobile in [(f"https://blog.naver.com/PostView.naver?blogId={bid}&logNo={lno}", False),
                        (f"https://m.blog.naver.com/{bid}/{lno}", True)]:
        try:
            html = fs.get(url, mobile=mobile).text
            save(f"post_{len(posts)+1}_{bid}_{lno}{'_m' if mobile else ''}.html", html)
            from bs4 import BeautifulSoup
            p = fs.parse_post(BeautifulSoup(html, "lxml"))
            if p["body"].strip():
                p.update({"rank": len(posts) + 1, "url": f"https://blog.naver.com/{bid}/{lno}", "blogId": bid, "logNo": lno})
                posts.append(p)
                note(f"[본문] {p['rank']}위 {p['title'][:40]} ({len(p['body'])}자, 사진 {p['images']}장)")
                break
            note(f"[본문] 파싱 결과 비어 있음: {url}")
        except Exception as e:  # noqa: BLE001
            note(f"[본문] 실패 {url}: {e}")
    time.sleep(1.5)
(out / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

# 3) 제품 페이지 + 공식몰 관련 페이지
products = []
extra = ["https://bodyshaper.co.kr/", "https://bodyshaper.co.kr/product/list.html?cate_no=98",
         "https://m.bodyshaper.co.kr/product/list_thumb.html?cate_no=98"]
for i, url in enumerate(cfg.get("product_urls", []) + extra):
    try:
        html = fs.get(url).text
        save(f"product_{i+1}.html", html)
        pr = fs.fetch_product(url)
        products.append(pr)
        note(f"[제품] {url} -> {pr['name'][:50]} ({len(pr['detail_text'])}자)")
    except Exception as e:  # noqa: BLE001
        note(f"[제품] 실패 {url}: {e}")
(out / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
(out / "log.txt").write_text("\n".join(log), encoding="utf-8")
