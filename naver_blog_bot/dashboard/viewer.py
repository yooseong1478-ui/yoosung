"""페이지 안에서 브라우저를 보고 조작하는 뷰어 (noVNC 대체).

서버 스레드 하나가 Playwright 브라우저를 소유하고, 화면을 JPEG 로 계속 찍어 두며(latest_frame),
웹소켓에서 들어온 클릭/키 입력을 큐로 받아 그대로 브라우저에 전달한다.
용도: 네이버 로그인(사용자가 직접 아이디/비밀번호 입력) — 로그인되면 세션이 프로필 폴더에 저장된다.
"""
import base64
import os
import queue
import threading
import time
from pathlib import Path

LOGIN_URL = "https://nid.naver.com/nidlogin.login?url=https%3A%2F%2Fblog.naver.com%2FGoBlogWrite.naver"
W, H = 1000, 720


class BrowserViewer:
    def __init__(self, profile_dir: Path, on_done=None, log=print):
        self.profile = profile_dir
        self.on_done = on_done
        self.log = log
        self.cmds: "queue.Queue[dict]" = queue.Queue()
        self.frame_b64 = ""
        self.url = ""
        self.active = False
        self.status = "idle"        # idle | running | done | error
        self.message = ""
        self._thread = None

    # ------------------------------------------------------------ 제어
    def start(self, target="login", test_url=""):
        if self.active:
            return False
        self.active, self.status, self.message = True, "running", ""
        self._thread = threading.Thread(target=self._run, args=(target, test_url), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self.cmds.put({"type": "stop"})

    def send(self, cmd: dict):
        if self.active:
            self.cmds.put(cmd)

    # ------------------------------------------------------------ 브라우저 스레드
    def _run(self, target, test_url):
        from playwright.sync_api import sync_playwright
        exe = os.environ.get("PW_CHROMIUM") or None
        args = ["--no-sandbox", "--disable-dev-shm-usage"]
        try:
            with sync_playwright() as pw:
                ctx = pw.chromium.launch_persistent_context(str(self.profile), headless=True, executable_path=exe, args=args,
                                                            viewport={"width": W, "height": H}, locale="ko-KR")
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(test_url if target == "test" else LOGIN_URL, wait_until="domcontentloaded", timeout=45000)
                deadline = time.time() + 900          # 15분
                last_shot = 0
                while time.time() < deadline:
                    # 입력 처리
                    try:
                        while True:
                            c = self.cmds.get_nowait()
                            if c["type"] == "stop":
                                raise StopIteration
                            self._apply(page, c)
                    except queue.Empty:
                        pass
                    # 화면 캡처 (초당 ~4장)
                    if time.time() - last_shot > 0.25:
                        try:
                            self.frame_b64 = base64.b64encode(page.screenshot(type="jpeg", quality=60)).decode()
                            self.url = page.url
                        except Exception:  # noqa: BLE001
                            pass
                        last_shot = time.time()
                    # 로그인 완료 감지
                    if target == "login" and "nid.naver.com" not in page.url and "naver.com" in page.url:
                        page.wait_for_timeout(1500)
                        self.status, self.message = "done", "네이버 로그인 완료"
                        break
                    time.sleep(0.05)
                else:
                    self.status, self.message = "error", "시간이 초과됐습니다. 다시 시작하세요."
                ctx.close()
        except StopIteration:
            self.status, self.message = "idle", "중단됨"
        except Exception as e:  # noqa: BLE001
            self.status, self.message = "error", f"브라우저 오류: {str(e)[:200]}"
            self.log(f"뷰어 오류: {e}")
        finally:
            self.active = False
            self.frame_b64 = ""
            if self.status == "done" and self.on_done:
                try:
                    self.on_done()
                except Exception as e:  # noqa: BLE001
                    self.log(f"완료 처리 오류: {e}")

    @staticmethod
    def _apply(page, c):
        t = c.get("type")
        if t == "click":
            page.mouse.click(float(c["x"]), float(c["y"]))
        elif t == "type":
            page.keyboard.type(str(c.get("text", "")), delay=20)
        elif t == "key":
            page.keyboard.press(str(c.get("key", "Enter")))
        elif t == "scroll":
            page.mouse.wheel(0, float(c.get("dy", 300)))
        elif t == "goto":
            page.goto(str(c.get("url", LOGIN_URL)), wait_until="domcontentloaded")
