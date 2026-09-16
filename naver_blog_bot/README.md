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

## 실행

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

`generate_post.py` 는 프롬프트 전체를 표준입력으로 넘겨 다음을 실행합니다.

```bash
claude -p --output-format text [--model <model>]
```

`-p`(`--print`)는 대화창 없이 한 번 응답하고 종료하는 모드라 cron, GitHub Actions, n8n 등
어떤 스케줄러에서도 호출할 수 있습니다. 로그인은 `claude` 를 한 번 실행해 두면 유지되고,
CI 서버라면 `ANTHROPIC_API_KEY` 환경변수로도 인증됩니다.

## 글 작성 규칙 (prompts/writer_prompt.md)

- 참고 글에서 제목 공식, 첫 문단 키워드 위치, 소제목 흐름, 글자 수, 키워드 반복 횟수, 사진 배치, 마무리, 해시태그를 분석
- 내용은 제품 페이지 사실만 사용하고, 없는 정보는 `[확인 필요: 항목]` 으로 남김
- 참고 글 문장 복사 금지, 의료적 효능 단정 금지, 마지막에 개인 후기 고지 문장

## 발행 단계 연결

`output/*.json` 을 읽어 네이버 블로그 발행(Playwright 자동화 또는 네이버 블로그 API)에 넘기면 됩니다.
발행 파트는 이 저장소에 아직 없습니다.
