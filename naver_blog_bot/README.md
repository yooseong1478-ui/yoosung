# 네이버 블로그 자동발행 봇 (글 생성 파트)

키워드의 네이버 블로그 **상위노출 글 N개 패턴**을 읽고, **지정 제품(뉴슬림엑스) 공식 페이지 내용**만으로
그 패턴에 맞는 글을 `claude -p`(헤드리스 모드)로 생성합니다.

> 이 스크립트는 네이버·쇼핑몰에 직접 접속하므로 **로컬 PC나 본인 서버에서** 실행하세요.
> Claude Code 웹 환경은 네트워크 정책상 naver.com, bodyshaper.co.kr 접속이 막혀 있습니다.

## 준비

```bash
cd naver_blog_bot
pip install -r requirements.txt
cp config.example.json config.json   # 키워드, 제품 URL, (선택) 네이버 API 키 수정
claude --version                      # Claude Code CLI 로그인 상태여야 함
```

`config.json` 항목

| 키 | 설명 |
|---|---|
| `keyword` | 상위노출 패턴을 분석할 검색 키워드 (예: 남자보정속옷) |
| `top_n` | 분석할 상위 글 개수 (기본 3) |
| `product_urls` | 글 내용의 근거가 될 제품 페이지 URL 목록 |
| `product_name`, `brand_notes` | 프롬프트에 그대로 들어가는 제품명과 브랜드 메모 |
| `naver_client_id/secret` | 있으면 네이버 검색 API 사용, 비우면 검색 결과 HTML 파싱 |
| `claude_model` | 비우면 CLI 기본 모델 |
| `min_chars` | 본문 최소 글자 수 |

네이버 검색 API 키는 https://developers.naver.com 에서 "검색" 애플리케이션을 등록하면 발급됩니다.
HTML 파싱은 네이버 마크업이 바뀌면 깨질 수 있으니 API 사용을 권장합니다.

## 방식 A: `claude -p` + 브라우저 (Claude가 직접 웹을 열어 읽음, 권장)

Claude Code 헤드리스 모드에 Playwright MCP 브라우저를 붙여, Claude가 스스로
네이버 블로그 검색 → 상위 글 3개 → 제품 페이지를 열어 읽고 글까지 씁니다. 파서가 없어 마크업 변경에 강합니다.

```bash
python3 run_agent.py                 # 결과: output/<키워드>_<날짜>_agent.md / .json / .raw.md
python3 run_agent.py --dry-run       # 에이전트 프롬프트만 출력
python3 run_agent.py --max-turns 60  # 글이 길어 도구 호출이 많이 필요하면 상향
```

내부적으로 다음을 실행합니다 (`.mcp.json` 은 `npx @playwright/mcp@latest --headless` 설정).

```bash
claude -p --output-format text \
  --mcp-config .mcp.json --strict-mcp-config \
  --allowedTools mcp__playwright --permission-mode dontAsk --max-turns 40
```

- Node 18 이상과 Chromium이 필요합니다. 처음 한 번 `npx playwright install chromium` 을 실행하세요.
- root 계정(도커 등)에서 돌리면 `.mcp.json` 의 args 에 `"--no-sandbox"` 를 추가해야 합니다.
- 네이버가 봇으로 판단해 캡차를 띄우면 `--headless` 를 빼고 창을 띄운 채 실행하세요.
- 에이전트 프롬프트는 `prompts/agent_prompt.md` 에 있고, 광고·카페 글 제외, 모바일 본문 페이지 사용, 제품 페이지 사실만 사용 규칙이 들어 있습니다.

## 방식 B: 파이썬 수집 + `claude -p` 생성

```bash
./run.sh                      # 수집 + 생성 한 번에
python3 fetch_sources.py      # 수집만: sources/<키워드>/posts.json, products.json
python3 generate_post.py      # 생성만: output/<키워드>_<날짜>.md / .json
python3 generate_post.py --dry-run   # claude 호출 없이 프롬프트만 저장
```

결과물

- `output/<키워드>_<날짜>.md` : 제목 + 본문(`[사진: 설명]` 위치 표시) + 해시태그
- `output/<키워드>_<날짜>.json` : 발행 스크립트가 쓰기 좋은 구조 (`title`, `body`, `hashtags`, `pattern`)
- `output/<키워드>_<날짜>.raw.md` : claude 원문 출력
- `output/<키워드>_<날짜>.prompt.md` : 실제로 보낸 프롬프트 (디버깅용)

## `claude -p` 동작

`run_agent.py` 와 `generate_post.py` 는 프롬프트 전체를 표준입력으로 넘겨 다음을 실행합니다.

```bash
claude -p --output-format text [--model <model>]
```

`-p`(`--print`)는 대화창 없이 한 번 응답하고 종료하는 모드라 cron, GitHub Actions, n8n 등
어떤 스케줄러에서도 호출할 수 있습니다. 방식 A는 여기에 `--mcp-config` 로 브라우저 도구를 붙이고
`--allowedTools mcp__playwright` 로 도구 사용을 미리 허용한 것입니다. 로그인은 `claude` 를 한 번 실행해 두면 유지되고,
CI 서버라면 `ANTHROPIC_API_KEY` 환경변수로도 인증됩니다.

## 글 작성 규칙 (prompts/writer_prompt.md)

- 참고 글에서 제목 공식, 첫 문단 키워드 위치, 소제목 흐름, 글자 수, 키워드 반복 횟수, 사진 배치, 마무리, 해시태그를 분석
- 내용은 제품 페이지 사실만 사용하고, 없는 정보는 `[확인 필요: 항목]` 으로 남김
- 참고 글 문장 복사 금지, 의료적 효능 단정 금지, 마지막에 개인 후기 고지 문장

## 발행 (publish_post.py)

```bash
pip install playwright && python3 -m playwright install chromium   # 최초 1회
python3 publish_post.py output/남자보정속옷_20260916_agent.json            # 에디터에 입력만 하고 발행 전 대기
python3 publish_post.py output/남자보정속옷_20260916_agent.json --publish  # 태그 입력 후 발행까지
./run_all.sh [--publish]                                                 # 수집+작성+입력(+발행) 한 번에
```

- 첫 실행 때 브라우저 창에서 네이버에 직접 로그인하면 `.browser_profile/` 에 세션이 남아 다음부터는 자동입니다.
- 기본값은 발행 전 멈춤이라 글을 눈으로 검토한 뒤 직접 발행 버튼을 누를 수 있습니다.
- `[사진: 설명]` 줄은 그대로 들어가므로 발행 전에 실제 사진으로 바꾸세요.
- 네이버 에디터 셀렉터는 `publish_post.py` 의 `SELECTORS` 에 모여 있어 마크업이 바뀌면 그 부분만 고치면 됩니다.
- 자동발행은 네이버 이용약관상 제재 대상이 될 수 있으니 계정 보호를 위해 하루 발행 수를 낮게 유지하세요.

### 로컬 한 줄 실행
윈도우는 `publish_local.bat` 을 더블클릭하면 됩니다 (발행까지 하려면 명령창에서 `publish_local.bat --publish`).

```bash
./publish_local.sh samples/남자보정속옷_뉴슬림엑스.md            # 로그인 → 입력 → 검토 대기
./publish_local.sh samples/남자보정속옷_뉴슬림엑스.md --publish  # 로그인 → 입력 → 발행
```

### GitHub Actions 로 발행 (PC 없이)
1. PC 브라우저에서 네이버에 로그인한 뒤 개발자도구 → Application → Cookies → `https://www.naver.com` 에서
   `NID_AUT` 와 `NID_SES` 값을 복사해 `NID_AUT=값; NID_SES=값` 형태로 만듭니다.
2. GitHub 저장소 Settings → Secrets and variables → Actions → New repository secret 에 이름 `NAVER_COOKIES` 로 저장합니다.
3. Actions 탭 → `publish-naver-post` → Run workflow. `publish` 를 끄면 입력까지만 점검하고 스크린샷을 아티팩트로 남기며,
   켜면 실제 발행합니다. 로그인 페이지로 튕기면 쿠키 만료 또는 해외 IP 새 기기 인증이므로 로컬 실행으로 전환하세요.

## 이 환경(Claude Code 웹)에서 바로 돌리려면

claude.ai/code 의 환경 설정에서 네트워크 정책을 "제한 없음"으로 바꾸거나 허용 도메인에
`naver.com`, `*.naver.com`, `bodyshaper.co.kr` 을 추가한 새 환경을 만든 뒤 세션을 열면
`python3 run_agent.py` 를 세션 안에서 실행할 수 있습니다.
