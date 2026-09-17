# 네이버 블로그 자동화 봇

## 🚀 설치 없이 사이트로 쓰기 (GitHub Codespaces)

1. 링크 클릭: **https://codespaces.new/yooseong1478-ui/yoosung?quickstart=1** → "Create codespace" → 2~5분 대기.
   대시보드 탭이 자동으로 열립니다. (안 열리면 아래 PORTS 탭에서 8787 옆 지구본 아이콘)
2. **네이버 로그인 하기** 버튼 → 페이지 안에 뜨는 화면에서 네이버 아이디/비밀번호로 로그인 (한 번만, 세션 저장).
   해외 접속이라 "새로운 기기" 인증 문자가 오면 그 화면에서 입력하세요.
3. 글 목록에서 올릴 글의 **임시저장** 또는 **발행** 버튼. 끝나면 결과가 카드에 표시됩니다.

새 글은 Claude 대화에서 만들어 저장소에 올리면 다음 접속 때 목록에 나타납니다.
글감 찾기·글쓰기를 사이트 안에서 직접 하려면 화면 아래 "고급 기능 열기"(Claude 구독 로그인 필요).

---
# 네이버 블로그 자동발행 봇 (글 생성 파트)

키워드의 네이버 블로그 **상위노출 글 N개 패턴**을 읽고, **지정 제품(뉴슬림엑스) 공식 페이지 내용**만으로
그 패턴에 맞는 글을 `claude -p`(헤드리스 모드)로 생성합니다.

> 이 스크립트는 네이버·쇼핑몰에 직접 접속하므로 **로컬 PC나 본인 서버에서** 실행하세요.
> Claude Code 웹 환경은 네트워크 정책상 naver.com, bodyshaper.co.kr 접속이 막혀 있습니다.


## 가장 쉬운 방법: 대시보드 (명령어 없이 버튼으로)

1. Python 설치 (https://www.python.org/downloads/ , 설치 화면에서 "Add python.exe to PATH" 체크)
2. Claude Code 설치 후 `claude` 를 한 번 실행해 로그인 (글쓰기 단계에 필요)
3. GitHub 에서 저장소를 ZIP 으로 내려받아 압축을 풀고, `naver_blog_bot` 폴더의 **`start_dashboard.bat`** 을 더블클릭
   (맥/리눅스는 `./start_dashboard.sh`)
4. 브라우저에 대시보드(http://127.0.0.1:8787)가 열리면 순서대로 버튼을 누릅니다.

| 단계 | 버튼 | 하는 일 |
|---|---|---|
| 1 | 네이버 로그인 창 열기 | 로그인 창이 뜨고, 로그인하면 자동으로 닫히며 세션이 `.browser_profile/` 에 저장됨 (다음부터 생략) |
| 2 | 인기 글 + 뉴스 모으기 | 키워드의 네이버 블로그 상위 5개 글과 뉴스 10건, 내 제품 페이지를 모아 AI 리서치 팀원이 패턴·사실을 정리 |
| 3 | AI 팀에게 글 쓰기 시키기 | 글쓰기 → 슬라이드 이미지 → 조립. 미리보기에 글과 이미지, 직접 찍을 사진 자리가 표시됨 |
| 4 | 임시저장 / 바로 발행 | 저장된 세션으로 에디터를 열어 글·이미지를 넣고 임시저장 또는 발행 (소제목은 굵게) |

대시보드는 이 PC 안에서만 동작하는 로컬 프로그램이라 네이버 아이디·비밀번호를 어디에도 보내지 않습니다.

## 준비 (직접 명령어로 쓰는 경우)

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


## AI 팀 시스템 (주제 한 줄 → 임시저장)

영상 "클로드 코워크 + n8n 블로그 자동화" 구조를 `claude -p` 위에 그대로 옮긴 것입니다.
팀장 1명과 팀원 4명이 `team/` 폴더의 역할 파일대로 순서대로 일합니다.

| 단계 | 파일 | 하는 일 | 결과 |
|---|---|---|---|
| 팀장 | `team/00_lead.md`, `pipeline.py` | 주제를 꺼내 팀원에게 순서대로 시키고 수치로 검수, 문제 있으면 해당 팀원만 재작업 | `work/<날짜_키워드>/` |
| 말투 | `team/01_style_guide.md`, `make_style_guide.py` | 내가 쓴 글 2~3편으로 스타일 가이드 생성 | 스타일 가이드 |
| SEO 규칙 | `team/02_seo_rules.md` | 상위노출 실측 수치 기반 규칙 (키워드별로 리서치가 갱신) | 규칙 |
| 1 리서치 | `team/03_researcher.md` | 세부 키워드 후보, 상위글 3개 패턴 수치, 제품 사실+출처 | `research.md` |
| 2 글쓰기 | `team/04_writer.md` | 말투+SEO+리서치를 반영해 글 작성, 사진 자리만 표시 | `post.md` |
| 3 이미지 | `team/05_image_maker.md`, `make_images.py` | 사진 자리마다 슬라이드 설계 → 1080x1080 PNG 렌더링, 실사 자리는 photo 로 표시 | `slides.json`, `images/` |
| 4 조립 | `team/06_assembler.md`(문서), `pipeline.py` 코드 | 사진 자리에 이미지 토큰 삽입, 해시태그 정리 | `final.md`, `final.json` |
| 5 발행 | `publish_post.py --draft` | 에디터에 글+이미지 입력 후 **임시저장**까지만. 발행 버튼은 사람이 | 임시저장 글 |
| 주간 | `team/07_analyst.md`, `improve_prompts.py` | 네이버 통계로 잘된 글/안 된 글 비교, 다음 주제와 규칙 수정 제안 | `work/analysis_*.md` |

```bash
# 0) 준비: topics.md 에 주제 한 줄 추가 (- [ ] 키워드 | 제품URL | 메모)
python3 make_style_guide.py my_posts/          # (선택) 내 글 폴더로 말투 파일 생성
# 1) 수집: GitHub Actions 'collect-naver-sources' 실행 → collected/<키워드>/ 커밋 → git pull
# 2) 팀 실행
python3 pipeline.py                            # 맨 위 미완료 주제 → work/<날짜_키워드>/final.json
python3 pipeline.py --browser                  # 수집 자료 없으면 브라우저 에이전트가 직접 리서치
python3 pipeline.py --steps write,image,assemble --work work/20260916_남자보정속옷   # 일부 재작업
# 3) 임시저장 (로그인 1회 후 자동)
python3 publish_post.py "$(cat work/LATEST)/final.json" --draft
# 4) 매주: 네이버 통계 내려받아 stats/latest.csv 로 저장 후
python3 improve_prompts.py stats/latest.csv --apply
```

- `[[PHOTO:설명]]` 자리는 실사가 필요한 곳이라 에디터에 "(사진 넣기: 설명)" 문구로 들어갑니다. 임시저장 글을 열어 사진으로 바꾸세요.
- 슬라이드 이미지는 사진 버튼 → 파일 선택으로 자동 삽입합니다. 에디터 마크업이 바뀌면 `SELECTORS["image_button"]` 을 고치세요.
- n8n 으로 스케줄링하려면 `n8n/blog_pipeline.json` 을 임포트하고 명령의 `/ABSOLUTE/PATH` 만 바꾸면 됩니다 (매일 06:00 생성+임시저장, 매주 월 통계 분석).
  Windows 작업 스케줄러나 cron 으로 같은 두 명령을 걸어도 됩니다.

## 이 환경(Claude Code 웹)에서 바로 돌리려면

claude.ai/code 의 환경 설정에서 네트워크 정책을 "제한 없음"으로 바꾸거나 허용 도메인에
`naver.com`, `*.naver.com`, `bodyshaper.co.kr` 을 추가한 새 환경을 만든 뒤 세션을 열면
`python3 run_agent.py` 를 세션 안에서 실행할 수 있습니다.
