#!/usr/bin/env python3
"""키워드의 네이버 블로그 상위노출 글 N개와 제품 페이지를 수집해 sources/<keyword>/ 에 저장한다.

수집 순서
1. 네이버 검색 API(키가 있으면) → 없으면 search.naver.com 블로그 탭 HTML 파싱
2. 각 글은 blog.naver.com/PostView.naver 로 본문을 읽고, 실패 시 m.blog.naver.com 으로 재시도
3. 제품 페이지는 본문 텍스트, 가격, 옵션(사이즈), 이미지 alt 를 추출
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})


def get(url, mobile=False, **kw):
    headers = {"User-Agent": MOBILE_UA} if mobile else {}
    r = SESSION.get(url, headers=headers, timeout=20, **kw)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- 검색 결과
def search_via_api(keyword, top_n, client_id, client_secret):
    r = SESSION.get(
        "https://openapi.naver.com/v1/search/blog.json",
        params={"query": keyword, "display": max(top_n * 3, 10), "sort": "sim"},
        headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
        timeout=20,
    )
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        link = it.get("link", "")
        if "blog.naver.com" not in link:
            continue
        out.append({"url": link, "title": re.sub(r"<[^>]+>", "", it.get("title", "")),
                    "blogger": it.get("bloggername", ""), "postdate": it.get("postdate", "")})
    return out


def search_via_html(keyword, top_n):
    url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={quote(keyword)}"
    soup = BeautifulSoup(get(url).text, "lxml")
    seen, out = set(), []
    selectors = ["a.title_link", ".title_area a", ".api_txt_lines.total_tit", "a[href*='blog.naver.com/']"]
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href", "")
            if "blog.naver.com" not in href:
                continue
            key = normalize_post_url(href)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({"url": href, "title": a.get_text(" ", strip=True), "blogger": "", "postdate": ""})
    return out


def normalize_post_url(url):
    """blog.naver.com/{id}/{logNo} 또는 PostView 형식 → (blogId, logNo)"""
    p = urlparse(url)
    if "blog.naver.com" not in p.netloc:
        return None
    qs = parse_qs(p.query)
    if "blogId" in qs and "logNo" in qs:
        return qs["blogId"][0], qs["logNo"][0]
    m = re.match(r"^/([A-Za-z0-9_\-]+)/(\d+)", p.path)
    if m:
        return m.group(1), m.group(2)
    return None


# ---------------------------------------------------------------- 본문
def fetch_post(blog_id, log_no):
    urls = [
        (f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}", False),
        (f"https://m.blog.naver.com/{blog_id}/{log_no}", True),
    ]
    last_err = None
    for url, mobile in urls:
        try:
            soup = BeautifulSoup(get(url, mobile=mobile).text, "lxml")
            post = parse_post(soup)
            if post["body"].strip():
                post["url"] = url
                return post
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"본문을 읽지 못함 {blog_id}/{log_no}: {last_err}")


def parse_post(soup):
    title_el = soup.select_one(".se-title-text, .pcol1 .se-fs-, h3.se_textarea, .htitle, .tit_h3, h2.se_textarea, .se-module-text.se-title-text")
    title = title_el.get_text(" ", strip=True) if title_el else (soup.title.get_text(strip=True) if soup.title else "")
    container = soup.select_one(".se-main-container") or soup.select_one("#postViewArea") \
        or soup.select_one(".se_component_wrap") or soup.select_one("#viewTypeSelector")
    if container is None:
        return {"title": title, "body": "", "images": 0, "hashtags": [], "headings": []}

    # 문단 단위로 정리하고, 이미지 위치는 [사진] 으로 표시
    lines, headings = [], []
    for el in container.find_all(["p", "h1", "h2", "h3", "h4", "img", "li", "td"]):
        if el.name == "img":
            lines.append("[사진]")
            continue
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        classes = " ".join(el.get("class", []))
        # SmartEditor ONE 에서 큰 글씨/인용구는 소제목으로 쓰이는 경우가 많다
        is_heading = el.name in ("h1", "h2", "h3", "h4") or "se-fs-fs24" in classes or "se-fs-fs19" in classes \
            or el.find_parent(class_="se-section-quotation") is not None
        if is_heading and len(txt) < 60:
            headings.append(txt)
            lines.append(f"## {txt}")
        else:
            lines.append(txt)
    body = "\n".join(lines)
    images = body.count("[사진]")
    tags = [a.get_text(strip=True) for a in soup.select(".post_tag a, .wrap_tag a, a.item")]
    tags = [t for t in tags if t.startswith("#")] or re.findall(r"#[\w가-힣]+", body)[-15:]
    return {"title": title, "body": body, "images": images, "hashtags": tags, "headings": headings}


# ---------------------------------------------------------------- 제품 페이지
def fetch_product(url):
    soup = BeautifulSoup(get(url).text, "lxml")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    name_el = soup.select_one(".headingArea h2, .infoArea h2, h1, .prd_name, .product_name")
    name = name_el.get_text(" ", strip=True) if name_el else (soup.title.get_text(strip=True) if soup.title else "")
    desc = soup.select_one("meta[name=description]")
    price_el = soup.select_one("#span_product_price_text, .price, #span_product_price_sale, .prd_price")
    options = [o.get_text(" ", strip=True) for o in soup.select(".xans-product-option option, select[name^=option] option")]
    options = [o for o in options if o and "선택" not in o and "옵션" not in o]
    detail = soup.select_one("#prdDetail, .cont, #productDetail, .detail, .goods_detail") or soup.body
    detail_text = re.sub(r"\n{3,}", "\n\n", detail.get_text("\n", strip=True)) if detail else ""
    alts = [img.get("alt", "").strip() for img in soup.select("img[alt]") if img.get("alt", "").strip()]
    return {
        "url": url,
        "name": name,
        "meta_description": desc.get("content", "") if desc else "",
        "price": price_el.get_text(" ", strip=True) if price_el else "",
        "options": options[:30],
        "image_alts": alts[:30],
        "detail_text": detail_text[:8000],
    }


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="sources")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    keyword, top_n = cfg["keyword"], int(cfg.get("top_n", 3))
    out_dir = Path(args.out) / keyword
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 검색
    if cfg.get("naver_client_id") and cfg.get("naver_client_secret"):
        results = search_via_api(keyword, top_n, cfg["naver_client_id"], cfg["naver_client_secret"])
        print(f"[검색] 네이버 API 결과 {len(results)}건", file=sys.stderr)
    else:
        results = search_via_html(keyword, top_n)
        print(f"[검색] HTML 파싱 결과 {len(results)}건", file=sys.stderr)
    if not results:
        sys.exit("검색 결과가 없습니다. 네이버 API 키를 설정하거나 셀렉터를 점검하세요.")

    # 2) 본문
    posts = []
    for r in results:
        if len(posts) >= top_n:
            break
        ids = normalize_post_url(r["url"])
        if not ids:
            continue
        try:
            post = fetch_post(*ids)
        except Exception as e:  # noqa: BLE001
            print(f"[본문] 건너뜀 {r['url']}: {e}", file=sys.stderr)
            continue
        post.update({"rank": len(posts) + 1, "search_title": r["title"], "blogger": r["blogger"], "postdate": r["postdate"]})
        posts.append(post)
        print(f"[본문] {post['rank']}위 {post['title']} ({len(post['body'])}자, 사진 {post['images']}장)", file=sys.stderr)
        time.sleep(1.0)
    if len(posts) < top_n:
        print(f"[경고] 요청한 {top_n}개 중 {len(posts)}개만 수집됨", file=sys.stderr)

    # 3) 제품
    products = []
    for url in cfg.get("product_urls", []):
        try:
            products.append(fetch_product(url))
            print(f"[제품] {products[-1]['name']}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[제품] 실패 {url}: {e}", file=sys.stderr)

    (out_dir / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {out_dir}/posts.json, products.json", file=sys.stderr)


if __name__ == "__main__":
    main()
