"""claude -p 헤드리스 호출 공용 헬퍼."""
import json
import re
import subprocess
import sys


NO_TOOLS_NOTE = ("\n\n[출력 규칙] 파일을 만들거나 읽거나 어떤 도구도 사용하지 마세요. 권한을 요청하지 마세요. "
                 "요청한 결과 텍스트만 그대로 표준 출력으로 내보내세요.")


def claude_p(prompt: str, model: str = "", extra: list | None = None, cwd=None, timeout=1800, tools: bool = False) -> str:
    """tools=False(기본): 도구 없이 텍스트만 생성. tools=True: extra 로 넘긴 MCP/도구 설정 사용."""
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    if not tools:
        cmd += ["--tools", "", "--strict-mcp-config"]
        prompt = prompt + NO_TOOLS_NOTE
    cmd += extra or []
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=cwd, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p 실패 (code {r.returncode}): {r.stderr[-1500:]}")
    return r.stdout


def extract_json(text: str):
    """응답 안의 첫 JSON 배열/객체를 꺼낸다 (```json 펜스 허용)."""
    m = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.S)
    cand = m.group(1) if m else None
    if cand is None:
        starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
        if not starts:
            raise ValueError("JSON 을 찾지 못했습니다")
        cand = text[min(starts):]
        end = max(cand.rfind("]"), cand.rfind("}"))
        cand = cand[:end + 1]
    return json.loads(cand)


def split_sections(text: str, names=("제목", "본문", "해시태그", "패턴분석", "수집자료")):
    pat = "|".join(names)
    return {m.group(1): m.group(2).strip() for m in re.finditer(rf"===({pat})===\s*(.*?)(?=\n===|\Z)", text, re.S)}


if __name__ == "__main__":
    print(claude_p(sys.stdin.read()))
