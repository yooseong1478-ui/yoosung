#!/usr/bin/env python3
"""CI 2차 수집: 뉴슬림엑스 제품 페이지들의 상세 이미지(OCR), 사용후기·Q&A 게시글을 collected/<keyword>/extra/ 에 저장한다."""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_sources as fs  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

BASE = "https://bodyshaper.co.kr"
keyword = sys.argv[1] if len(sys.argv) > 1 else "남자보정속옷"
out = Path("collected") / keyword / "extra"
(out / "img").mkdir(parents=True, exist_ok=True)
log, result = [], {"products": [], "reviews": [], "qna": []}


def note(m):
    print(m, file=sys.stderr); log.append(m)


def text_of(el):
    for s in el(["script", "style", "noscript"]):
        s.decompose()
    return re.sub(r"\n{3,}", "\n\n", el.get_text("\n", strip=True))


def ocr(path):
    try:
        r = subprocess.run(["tesseract", str(path), "-", "-l", "kor+eng", "--psm", "4"], capture_output=True, text=True, timeout=180)
        return r.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"(OCR 실패: {e})"


# 1) 제품 페이지 + 상세 이미지 OCR
for pno in (65, 64, 112):
    url = f"{BASE}/product/detail.html?product_no={pno}"
    try:
        html = fs.get(url).text
        (out / f"product_{pno}.html").write_text(html, encoding="utf-8")
        s = BeautifulSoup(html, "lxml")
        info = s.select_one(".infoArea") or s.select_one(".xans-product-detail")
        detail = s.select_one("#prdDetail")
        item = {"product_no": pno, "url": url, "info": text_of(info)[:3000] if info else "",
                "detail_text": text_of(detail)[:3000] if detail else "", "images": []}
        for i, img in enumerate((detail.select("img") if detail else [])):
            src = img.get("src") or img.get("ec-data-src") or ""
            if not src or "cafe24.com/design" in src:
                continue
            src = urljoin(BASE, src)
            try:
                r = fs.SESSION.get(src, timeout=30); r.raise_for_status()
                ext = ".jpg" if ".jp" in src.lower() else ".png"
                p = out / "img" / f"p{pno}_{i+1}{ext}"
                p.write_bytes(r.content)
                item["images"].append({"src": src, "file": p.name, "ocr": ocr(p)})
                note(f"[이미지] {src} -> OCR {len(item['images'][-1]['ocr'])}자")
            except Exception as e:  # noqa: BLE001
                note(f"[이미지] 실패 {src}: {e}")
        result["products"].append(item)
        note(f"[제품] {pno}: info {len(item['info'])}자, 이미지 {len(item['images'])}장")
    except Exception as e:  # noqa: BLE001
        note(f"[제품] 실패 {url}: {e}")

# 2) 사용후기 / Q&A 게시판 (목록 2페이지 + 개별 글)
for board_no, key in ((4, "reviews"), (6, "qna")):
    nos = []
    for page in (1, 2, 3):
        url = f"{BASE}/board/product/list.html?board_no={board_no}&page={page}"
        try:
            html = fs.get(url).text
            (out / f"board{board_no}_p{page}.html").write_text(html, encoding="utf-8")
            nos += re.findall(r"no=(\d+)&amp;board_no=%d|no=(\d+)&board_no=%d" % (board_no, board_no), html)
        except Exception as e:  # noqa: BLE001
            note(f"[게시판] 실패 {url}: {e}")
    ids = []
    for a, b in nos:
        n = a or b
        if n not in ids:
            ids.append(n)
    note(f"[게시판 {board_no}] 글 {len(ids)}개")
    for n in ids[:40]:
        url = f"{BASE}/product/provider/review_read.xml?no={n}&board_no={board_no}&spread_flag=T"
        alt = f"{BASE}/board/product/read.html?no={n}&board_no={board_no}"
        for u in (url, alt):
            try:
                html = fs.get(u).text
                s = BeautifulSoup(html, "lxml")
                body = s.select_one(".detail, .xans-board-read, .board-read, .boardView, body")
                txt = text_of(body) if body else ""
                if len(txt) > 20:
                    result[key].append({"no": n, "url": u, "text": txt[:2500]})
                    break
            except Exception as e:  # noqa: BLE001
                note(f"[글] 실패 {u}: {e}")
    note(f"[게시판 {board_no}] 본문 확보 {len(result[key])}개")

(out / "extra.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
(out / "log.txt").write_text("\n".join(log), encoding="utf-8")
