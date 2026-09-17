#!/usr/bin/env python3
"""네이버 블로그 자동화 대시보드 (PC 에서 실행).

  python3 dashboard/app.py   →  브라우저에서 http://127.0.0.1:8787

버튼: 네이버 로그인(창 띄워 로그인 → 세션 저장) → 글감 찾기(인기 블로그 글 + 뉴스 수집) → 글 쓰기(AI 팀) → 임시저장/발행
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
BOT = HERE.parent
sys.path.insert(0, str(BOT))
PROFILE = BOT / ".browser_profile"
WORK = BOT / "work"
WORK.mkdir(exist_ok=True)
PY = sys.executable
CLOUD = os.environ.get("NAVER_BOT_CLOUD") == "1" or os.environ.get("CODESPACES") == "true"


def novnc_url():
    """Codespaces 에서 noVNC(원격 화면) 주소. 로컬이면 빈 문자열."""
    name, domain = os.environ.get("CODESPACE_NAME"), os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if name and domain:
        return f"https://{name}-6080.{domain}/?autoconnect=1&resize=remote&password=vscode"
    return "http://127.0.0.1:6080/?autoconnect=1&resize=remote&password=vscode" if CLOUD else ""


app = FastAPI(title="Naver Blog Bot Dashboard")
app.mount("/work", StaticFiles(directory=str(WORK)), name="work")

LOG = deque(maxlen=400)
STATE = {"busy": "", "logged_in": None, "login_id": "", "keyword": "", "work": "", "candidates": [], "final": None,
         "last_publish": "", "cloud": CLOUD, "novnc_url": novnc_url(),
         "claude_logged_in": None, "claude_login_state": "idle", "claude_login_url": "", "claude_login_msg": ""}
LOCK = threading.Lock()
CLAUDE = {"proc": None, "master": None, "buf": ""}


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    LOG.append(line)
    print(line, flush=True)


def run_bg(name, fn, *args):
    with LOCK:
        if STATE["busy"]:
            return False
        STATE["busy"] = name

    def runner():
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001
            log(f"오류: {e}")
        finally:
            STATE["busy"] = ""
    threading.Thread(target=runner, daemon=True).start()
    return True


# ------------------------------------------------------------------ 로그인
def check_login():
    """저장된 프로필로 네이버에 로그인돼 있는지 확인 (헤드리스)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://blog.naver.com/GoBlogWrite.naver", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            ok = "nid.naver.com" not in page.url
            STATE["logged_in"] = ok
            if ok:
                m = re.search(r"blog\.naver\.com/([A-Za-z0-9_\-]+)", page.url)
                STATE["login_id"] = m.group(1) if m else ""
        except Exception as e:  # noqa: BLE001
            log(f"로그인 확인 실패: {e}")
            STATE["logged_in"] = False
        finally:
            ctx.close()
    log("네이버 로그인 상태: " + ("로그인됨" if STATE["logged_in"] else "로그인 필요"))


def do_login():
    """창을 띄워 사용자가 직접 로그인하게 하고, 로그인되면 닫는다 (세션은 .browser_profile 에 저장)."""
    from playwright.sync_api import sync_playwright
    if CLOUD:
        log("로그인 창을 원격 화면에 띄웠습니다. '로그인 화면 보기' 버튼으로 화면을 열어 네이버 로그인을 완료해 주세요 (최대 10분).")
        log("해외 IP 접속이라 '새로운 기기 로그인' 인증(문자/이메일)이 뜰 수 있습니다. 그 화면에서 그대로 진행하면 됩니다.")
    else:
        log("로그인 창을 엽니다. 창에서 네이버 로그인을 완료해 주세요 (최대 10분).")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), headless=False, viewport={"width": 1100, "height": 800})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login?url=https%3A%2F%2Fblog.naver.com%2FGoBlogWrite.naver", wait_until="domcontentloaded")
        deadline = time.time() + 600
        while time.time() < deadline:
            page.wait_for_timeout(1500)
            try:
                if "nid.naver.com" not in page.url and "naver.com" in page.url:
                    break
            except Exception:  # noqa: BLE001
                break
        page.wait_for_timeout(2000)
        ctx.close()
    check_login()


# ------------------------------------------------------------------ Claude 로그인 (구독 OAuth, claude CLI)
ANSI_RE = re.compile(r"\x1b\]8;;[^\x07]*\x07|\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x07")


def check_claude():
    try:
        r = subprocess.run(["claude", "auth", "status", "--json"], capture_output=True, text=True, timeout=30)
        ok = bool(json.loads(r.stdout or "{}").get("loggedIn"))
    except Exception as e:  # noqa: BLE001
        log(f"Claude 상태 확인 실패: {e}")
        ok = False
    STATE["claude_logged_in"] = ok
    if ok:
        STATE["claude_login_state"] = "done"
    log("Claude 로그인 상태: " + ("로그인됨" if ok else "로그인 필요"))
    return ok


def _claude_reader():
    """pty 출력을 읽어 로그인 URL 과 완료 여부를 상태에 반영한다."""
    import select
    master, proc = CLAUDE["master"], CLAUDE["proc"]
    while proc.poll() is None:
        r, _, _ = select.select([master], [], [], 1)
        if not r:
            continue
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        CLAUDE["buf"] += ANSI_RE.sub("", chunk.decode("utf-8", "ignore"))
        txt = CLAUDE["buf"]
        if not STATE["claude_login_url"]:
            m = re.search(r"https://claude\.(?:com|ai)/\S*oauth\S*", txt)
            if m:
                STATE["claude_login_url"] = m.group(0).rstrip(".,)")
                STATE["claude_login_state"] = "waiting_code"
                log("Claude 로그인 링크가 준비됐습니다. 링크를 열어 승인한 뒤 나오는 코드를 붙여넣으세요.")
        if re.search(r"(?i)logged in|login successful|successfully", txt):
            break
    time.sleep(1)
    tail = CLAUDE["buf"][-300:].strip()
    try:
        os.close(master)
    except OSError:
        pass
    CLAUDE["proc"] = None
    if check_claude():
        STATE["claude_login_msg"] = "Claude 로그인 완료"
    else:
        STATE["claude_login_state"] = "error"
        STATE["claude_login_msg"] = tail or "로그인이 완료되지 않았습니다. 다시 시작하세요."
        log(f"Claude 로그인 실패: {tail[-160:]}")


def start_claude_login():
    import pty
    if CLAUDE["proc"] is not None:
        return False
    STATE.update({"claude_login_state": "starting", "claude_login_url": "", "claude_login_msg": ""})
    CLAUDE["buf"] = ""
    master, slave = pty.openpty()
    env = dict(os.environ, TERM="xterm", BROWSER="true")     # 서버에서 브라우저를 열지 않도록
    CLAUDE["proc"] = subprocess.Popen(["claude", "auth", "login", "--claudeai"], stdin=slave, stdout=slave, stderr=slave,
                                      env=env, close_fds=True)
    os.close(slave)
    CLAUDE["master"] = master
    threading.Thread(target=_claude_reader, daemon=True).start()
    log("Claude 로그인을 시작합니다...")
    return True


def submit_claude_code(code):
    if CLAUDE["proc"] is None or CLAUDE["master"] is None:
        return False
    os.write(CLAUDE["master"], (code.strip() + "\r").encode())
    STATE["claude_login_state"] = "verifying"
    log("코드를 전달했습니다. 확인 중...")
    return True


def cancel_claude_login():
    p = CLAUDE["proc"]
    if p is not None and p.poll() is None:
        p.kill()
    STATE["claude_login_state"] = "idle"
    STATE["claude_login_url"] = ""


# ------------------------------------------------------------------ 글감 수집
def do_research(topic, product_url, memo):
    import fetch_sources as fs
    from bs4 import BeautifulSoup
    keyword = topic.strip()
    STATE["keyword"] = keyword
    out = BOT / "collected" / keyword
    (out / "raw").mkdir(parents=True, exist_ok=True)
    log(f"'{keyword}' 인기 블로그 글 수집 중...")
    results = fs.search_via_html(keyword, 5)
    posts = []
    for r in results:
        if len(posts) >= 5:
            break
        ids = fs.normalize_post_url(r["url"])
        if not ids:
            continue
        try:
            p = fs.fetch_post(*ids)
            p.update({"rank": len(posts) + 1, "search_title": r["title"], "blogger": "", "postdate": ""})
            posts.append(p)
            log(f"  {p['rank']}위 {p['title'][:40]} ({len(p['body'])}자, 사진 {p['images']}장)")
        except Exception as e:  # noqa: BLE001
            log(f"  건너뜀 {r['url']}: {e}")
        time.sleep(0.8)
    (out / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    log("관련 뉴스 수집 중...")
    news = []
    try:
        html = fs.get(f"https://search.naver.com/search.naver?where=news&query={quote(keyword)}").text
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a.news_tit, .news_tit a, a[class*='title']")[:10]:
            t = a.get_text(" ", strip=True)
            if t and len(t) > 8:
                news.append({"title": t, "url": a.get("href", "")})
        log(f"  뉴스 {len(news)}건")
    except Exception as e:  # noqa: BLE001
        log(f"  뉴스 수집 실패: {e}")
    (out / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")

    products = []
    if product_url:
        try:
            products.append(fs.fetch_product(product_url))
            log(f"  제품 페이지: {products[-1]['name'][:40]}")
        except Exception as e:  # noqa: BLE001
            log(f"  제품 페이지 실패: {e}")
    (out / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")

    STATE["candidates"] = [{"rank": p["rank"], "title": p["title"], "url": p.get("url", ""), "chars": len(p["body"]),
                            "images": p["images"]} for p in posts] + [{"rank": "뉴스", "title": n["title"], "url": n["url"]} for n in news[:5]]
    log("AI 리서치 팀원이 패턴과 사실을 정리하는 중 (1~3분)...")
    work = WORK / f"{date.today():%Y%m%d}_{keyword.replace(' ', '')}"
    work.mkdir(parents=True, exist_ok=True)
    STATE["work"] = work.name
    r = subprocess.run([PY, str(BOT / "pipeline.py"), "--topic", keyword, "--product-url", product_url or "", "--memo", memo or "",
                        "--work", str(work), "--steps", "research", "--no-mark"], capture_output=True, text=True, encoding="utf-8", cwd=BOT)
    for line in (r.stderr or "").splitlines():
        if line.startswith("[팀장]"):
            log(line)
    if r.returncode != 0:
        log(f"리서치 실패: {(r.stderr or '')[-800:]}")
    else:
        log("글감 정리 완료. '글 쓰기' 를 누르세요.")


# ------------------------------------------------------------------ 글 쓰기
def do_write():
    keyword, work = STATE["keyword"], WORK / STATE["work"]
    if not keyword or not (work / "research.md").exists():
        log("먼저 '글감 찾기' 를 실행하세요.")
        return
    log("AI 팀: 글쓰기 → 이미지 → 조립 (3~8분)...")
    r = subprocess.Popen([PY, str(BOT / "pipeline.py"), "--topic", keyword, "--work", str(work), "--steps", "write,image,assemble", "--no-mark"],
                         stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", cwd=BOT)
    for line in r.stderr:
        if line.startswith("[팀장]"):
            log(line.strip())
    r.wait()
    if r.returncode != 0 or not (work / "final.json").exists():
        log("글쓰기 실패. 로그를 확인하세요.")
        return
    STATE["final"] = json.loads((work / "final.json").read_text(encoding="utf-8"))
    STATE["final"]["work"] = work.name
    log("글 완성. 아래 미리보기를 확인하고 '임시저장' 또는 '발행' 을 누르세요.")


# ------------------------------------------------------------------ 발행
def do_publish(mode):
    work = WORK / STATE["work"]
    if not (work / "final.json").exists():
        log("먼저 글을 만드세요.")
        return
    flag = "--draft" if mode == "draft" else "--publish"
    log(("임시저장" if mode == "draft" else "발행") + " 시작 (브라우저 창이 뜹니다" + (", 원격 화면에서 볼 수 있습니다" if CLOUD else "") + ")...")
    r = subprocess.run([PY, str(BOT / "publish_post.py"), str(work / "final.json"), flag, "--shot-dir", str(work / "shots")],
                       capture_output=True, text=True, encoding="utf-8", cwd=BOT)
    for line in ((r.stderr or "") + (r.stdout or "")).splitlines():
        if line.strip():
            log(line.strip())
    if r.returncode == 0:
        STATE["last_publish"] = (r.stdout or "").strip().splitlines()[-1] if r.stdout else "완료"
    else:
        log("발행 단계 실패. 로그인 상태와 에디터를 확인하세요.")


# ------------------------------------------------------------------ API
class ResearchReq(BaseModel):
    topic: str
    product_url: str = ""
    memo: str = ""


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    return {**STATE, "log": list(LOG)[-80:]}


@app.post("/api/login")
def login():
    return {"started": run_bg("login", do_login)}


@app.post("/api/check_login")
def check():
    return {"started": run_bg("check", check_login)}


class CodeReq(BaseModel):
    code: str


@app.post("/api/claude/check")
def claude_check():
    threading.Thread(target=check_claude, daemon=True).start()
    return {"started": True}


@app.post("/api/claude/login")
def claude_login():
    return {"started": start_claude_login()}


@app.post("/api/claude/code")
def claude_code(req: CodeReq):
    return {"ok": submit_claude_code(req.code)}


@app.post("/api/claude/cancel")
def claude_cancel():
    cancel_claude_login()
    return {"ok": True}


@app.post("/api/research")
def research(req: ResearchReq):
    return {"started": run_bg("research", do_research, req.topic, req.product_url, req.memo)}


@app.post("/api/write")
def write():
    return {"started": run_bg("write", do_write)}


@app.post("/api/publish/{mode}")
def publish(mode: str):
    return {"started": run_bg("publish", do_publish, mode)}


@app.get("/api/final")
def final():
    return JSONResponse(STATE["final"] or {})


@app.get("/api/samples")
def samples():
    d = BOT / "samples"
    return [p.name for p in sorted(d.iterdir()) if p.is_dir() and (p / "final.json").exists()]


@app.post("/api/load_sample/{name}")
def load_sample(name: str):
    """미리 만들어 둔 글(samples/<name>)을 작업 폴더로 복사해 바로 발행할 수 있게 한다."""
    import shutil
    src = BOT / "samples" / name
    if not (src / "final.json").exists():
        return {"ok": False, "error": "없는 샘플"}
    work = WORK / f"{date.today():%Y%m%d}_{name}"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(src, work)
    f = json.loads((work / "final.json").read_text(encoding="utf-8"))
    f["images_dir"] = str(work / "images")
    (work / "final.json").write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")
    f["work"] = work.name
    STATE["final"], STATE["work"] = f, work.name
    STATE["keyword"] = name.split("_")[0]
    log(f"준비된 글 '{name}' 을 불러왔습니다. 미리보기 확인 후 발행하세요.")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8787"))
    if not CLOUD:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    threading.Thread(target=check_claude, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
