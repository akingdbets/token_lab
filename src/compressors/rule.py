"""
규칙 기반 문맥 정제 (마크다운 휴리스틱)

LLM 없이 정해진 규칙으로 형식 잡음만 걷어낸다. 비용 0, 결과는 항상 같다.
코드 블록(``` ... ```) 내용과 인라인 코드(`...`)는 절대 고치지 않는다
(정답의 대부분이 함수·파라미터 이름이기 때문).

규칙 (생성자 인자로 하나씩 끌 수 있다. 규칙별 효과를 나눠 볼 때 사용)
    frontmatter   문서 앞 YAML 머리말(--- key: ... ---) 제거
    anchors       제목 뒤 앵커 { #id } 제거
    html          HTML 태그 제거 (안의 글자는 남김), <style>/<script> 블록은 통째로 제거
    links         [글자](주소) -> 글자, 이미지 ![..](..) 제거
    emphasis      **굵게**, *기울임* 표시 제거 (목록 기호 "* " 는 그대로)
    admonitions   /// tip, /// note | 제목, //// tab | ... 같은 상자 표시 줄 제거 (제목 글자는 남김)
    dedup_code    앞에 나온 코드 블록과 똑같은 코드 블록은 한 줄 안내로 대체
    whitespace    줄 끝 공백 제거, 3줄 이상 빈 줄을 1줄로
"""

from __future__ import annotations

import re
from collections import Counter

from compressors.base import CompressResult, Compressor

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
FRONTMATTER = re.compile(r"^---[ \t]*\n(?:[\w-]+:.*\n)(?:(?!---[ \t]*\n).*\n)*?---[ \t]*\n", re.M)
ANCHOR = re.compile(r"[ \t]*\{\s*#[\w\-]+\s*\}")
STYLE_SCRIPT = re.compile(r"<(style|script)\b[^>]*>.*?</\1>\s*", re.S | re.I)
HTML_TAG = re.compile(r"</?[a-zA-Z][^>\n]*>")
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]\n]+)\]\((?:[^()\s]|\([^)\s]*\))+(?:\s+\"[^\"]*\")?\)")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
ITALIC = re.compile(r"(?<![\*\w])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\*\w])")
ADMONITION = re.compile(r"^[ \t]*/{3,}[ \t]*(?:[\w-]+)?[ \t]*(?:\|[ \t]*(.*?))?[ \t]*$", re.M)
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
FILE_LINE = re.compile(r"^# file: (\S+)", re.M)


def split_fences(text: str) -> list[tuple[bool, str]]:
    """[(코드 블록 여부, 조각)]. 코드 블록 조각은 여는/닫는 ``` 줄을 포함한다."""
    parts: list[tuple[bool, str]] = []
    buf: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        m = FENCE.match(line)
        if fence is None and m:
            if buf:
                parts.append((False, "\n".join(buf)))
            buf, fence = [line], m.group(1)
        elif fence is not None and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                and not line.strip()[len(m.group(1)):].strip():
            buf.append(line)
            parts.append((True, "\n".join(buf)))
            buf, fence = [], None
        else:
            buf.append(line)
    if buf:
        parts.append((fence is not None, "\n".join(buf)))   # 닫히지 않은 코드 블록도 코드로 취급
    return parts


class RuleCompressor(Compressor):
    name = "rule"
    RULES = ("frontmatter", "anchors", "html", "links", "emphasis",
             "admonitions", "dedup_code", "whitespace")

    def __init__(self, **enabled: bool):
        unknown = set(enabled) - set(self.RULES)
        if unknown:
            raise ValueError(f"알 수 없는 규칙: {sorted(unknown)}")
        self.enabled = {r: enabled.get(r, True) for r in self.RULES}

    def config(self) -> dict:
        return dict(self.enabled)

    def compress(self, question: str, context: str) -> CompressResult:
        hits: Counter = Counter()
        on = self.enabled
        out: list[str] = []
        seen_code: dict[str, str] = {}

        for is_code, chunk in split_fences(context.replace("\r\n", "\n")):
            if is_code:
                if on["dedup_code"]:
                    key = FILE_LINE.sub("", chunk).strip()
                    if key in seen_code:
                        hits["dedup_code"] += 1
                        out.append(f"(Same code as {seen_code[key]} above.)")
                        continue
                    m = FILE_LINE.search(chunk)
                    seen_code[key] = f"`{m.group(1)}`" if m else "the block"
                out.append(chunk)
                continue
            out.append(self._prose(chunk, hits))

        text = "\n".join(out)
        if on["whitespace"]:
            text, n = re.subn(r"\n{3,}", "\n\n", text)
            hits["whitespace"] += n
            text = text.strip() + "\n"
        return CompressResult(text=text, info={"rule_hits": dict(hits)})

    def _prose(self, s: str, hits: Counter) -> str:
        on = self.enabled

        def sub(rule: str, pattern: re.Pattern, repl, text: str) -> str:
            text, n = pattern.subn(repl, text)
            hits[rule] += n
            return text

        if on["frontmatter"]:
            s = sub("frontmatter", FRONTMATTER, "", s)
        if on["admonitions"]:
            s = sub("admonitions", ADMONITION, lambda m: m.group(1) or "\0DROP", s)
            s = re.sub(r"^\0DROP\n?", "", s, flags=re.M)
        if on["html"]:
            s = sub("html", STYLE_SCRIPT, "", s)
        if on["links"]:
            s = sub("links", IMAGE, "", s)
            s = sub("links", LINK, r"\1", s)

        # 인라인 코드 바깥 조각에만 적용
        pieces, last = [], 0
        for m in INLINE_CODE.finditer(s):
            pieces.append(self._plain(s[last:m.start()], sub))
            pieces.append(m.group(0))
            last = m.end()
        pieces.append(self._plain(s[last:], sub))
        s = "".join(pieces)

        if on["whitespace"]:
            s = sub("whitespace", re.compile(r"[ \t]+$", re.M), "", s)
        return s

    def _plain(self, s: str, sub) -> str:
        on = self.enabled
        if on["anchors"]:
            s = sub("anchors", ANCHOR, "", s)
        if on["html"]:
            s = sub("html", HTML_TAG, "", s)
        if on["emphasis"]:
            s = sub("emphasis", BOLD, r"\1", s)
            s = sub("emphasis", ITALIC, r"\1", s)
        return s
