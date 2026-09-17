#!/usr/bin/env python3
"""CI 3차 수집: 상위노출 글의 이미지, 브랜드 키워드 글의 이미지, 이전에 등록한 글 상태.
결과: collected/<keyword>/topimg/, brandimg/, images_index.json, prev_post.json"""
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_sources as fs  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from PIL import Image  # noqa: E402

keyword = sys.argv[1] if len(sys.argv) > 1 else "남자보정속옷"
brand_query = sys.argv[2] if len(sys.argv) > 2 else "뉴슬림엑스"
prev_title = sys.argv[3] if len(sys.argv) > 3 else ""
out = Path("collected") / keyword
log = []


def note(m):
    print(m, file=sys.stderr); log.append(m)


def post_images(html):
    """본문 순서대로 (이미지URL, 캡션, 직전 텍스트) 목록. 지연로딩 placeholder(w80_blur)는 원본 URL 로 치환."""
    soup = BeautifulSoup(html, "lxml")
    cont = soup.select_one(".se-main-container") or soup.select_one("#postViewArea") or soup
    items, last_text, seen = [], "", set()
    for el in cont.find_all(["img", "p", "span"]):
        if el.name == "img":
            src = el.get("data-lazy-src") or el.get("src") or ""
            if "pstatic.net" not in src:
                continue
            base = re.sub(r"\?type=.*$", "", src)
            if base in seen:
                continue
            seen.add(base)
            comp = el.find_parent(class_=re.compile(r"se-component"))
            cap = comp.select_one(".se-caption") if comp else None
            items.append({"url": base + "?type=w773", "caption": cap.get_text(" ", strip=True) if cap else "",
                          "before_text": last_text[-80:]})
        else:
            t = el.get_text(" ", strip=True)
            if t and el.name == "p":
                last_text = t
    return items


def download(items, folder: Path, prefix: str, limit=40):
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, it in enumerate(items[:limit], 1):
        try:
            r = fs.SESSION.get(it["url"], timeout=30, headers={"Referer": "https://blog.naver.com/"})
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            w, h = im.size
            if w > 640:
                im = im.resize((640, int(h * 640 / w)))
            f = folder / f"{prefix}_{i:02d}.jpg"
            im.save(f, "JPEG", quality=78)
            it.update({"file": str(f.relative_to(out)), "w": w, "h": h, "ratio": round(w / h, 2)})
            saved.append(it)
        except Exception as e:  # noqa: BLE001
            note(f"[이미지] 실패 {it['url'][:80]}: {e}")
        time.sleep(0.3)
    return saved


index = {"keyword": keyword, "top_posts": [], "brand_posts": []}

# 1) 상위노출 글 이미지 (이미 수집된 원본 HTML 사용)
posts = json.loads((out / "posts.json").read_text(encoding="utf-8"))
for p in posts[:3]:
    raw = next(iter(sorted((out / "raw").glob(f"post_{p['rank']}_*.html"))), None)
    if not raw:
        continue
    items = post_images(raw.read_text(encoding="utf-8"))
    saved = download(items, out / "topimg", f"top{p['rank']}")
    index["top_posts"].append({"rank": p["rank"], "title": p["title"], "url": p["url"], "image_count": len(items), "images": saved})
    note(f"[상위글 {p['rank']}위] 이미지 {len(items)}장 중 {len(saved)}장 저장")

# 2) 브랜드 키워드 글 이미지
try:
    html = fs.get(f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={quote(brand_query)}").text
    (out / "raw" / "search_brand.html").write_text(html, encoding="utf-8")
    ids = []
    for bid, lno in re.findall(r'https?://blog\.naver\.com/([A-Za-z0-9_\-]+)/(\d+)', html):
        if (bid, lno) not in ids:
            ids.append((bid, lno))
    note(f"[브랜드 검색] '{brand_query}' 블로그 글 {len(ids)}개")
    for n, (bid, lno) in enumerate(ids[:5], 1):
        try:
            ph = fs.get(f"https://blog.naver.com/PostView.naver?blogId={bid}&logNo={lno}").text
            parsed = fs.parse_post(BeautifulSoup(ph, "lxml"))
            items = post_images(ph)
            saved = download(items, out / "brandimg", f"brand{n}", limit=25)
            index["brand_posts"].append({"n": n, "title": parsed["title"], "url": f"https://blog.naver.com/{bid}/{lno}",
                                         "chars": len(parsed["body"]), "image_count": len(items), "images": saved,
                                         "body_head": parsed["body"][:600]})
            note(f"[브랜드글 {n}] {parsed['title'][:40]} 이미지 {len(items)}장 중 {len(saved)}장")
            time.sleep(1)
        except Exception as e:  # noqa: BLE001
            note(f"[브랜드글 {n}] 실패 {bid}/{lno}: {e}")
except Exception as e:  # noqa: BLE001
    note(f"[브랜드 검색] 실패: {e}")

# 3) 이전에 등록한 글 찾기 (제목 정확 검색)
prev = {"query": prev_title, "found": []}
if prev_title:
    for q in (f'"{prev_title}"', prev_title[:30]):
        try:
            html = fs.get(f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={quote(q)}").text
            for bid, lno in re.findall(r'https?://blog\.naver\.com/([A-Za-z0-9_\-]+)/(\d+)', html)[:10]:
                try:
                    ph = fs.get(f"https://blog.naver.com/PostView.naver?blogId={bid}&logNo={lno}").text
                    parsed = fs.parse_post(BeautifulSoup(ph, "lxml"))
                    if "뉴슬림엑스" in parsed["body"] or "뉴슬림엑스" in parsed["title"]:
                        items = post_images(ph)
                        prev["found"].append({"url": f"https://blog.naver.com/{bid}/{lno}", "title": parsed["title"],
                                              "chars": len(parsed["body"]), "images": len(items), "headings": parsed["headings"][:10],
                                              "hashtags": parsed["hashtags"][:20], "body": parsed["body"][:4000]})
                        note(f"[이전 글] 발견 {bid}/{lno}: {parsed['title'][:40]} ({len(parsed['body'])}자, 이미지 {len(items)}장)")
                except Exception as e:  # noqa: BLE001
                    note(f"[이전 글] 본문 실패 {bid}/{lno}: {e}")
            if prev["found"]:
                break
        except Exception as e:  # noqa: BLE001
            note(f"[이전 글] 검색 실패: {e}")
    if not prev["found"]:
        note("[이전 글] 검색 결과에서 찾지 못함 (아직 색인 전이거나 제목이 다름)")

(out / "images_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
(out / "prev_post.json").write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
(out / "images_log.txt").write_text("\n".join(log), encoding="utf-8")
