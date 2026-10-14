"""
규칙 기반 문맥 정제 (마크다운 휴리스틱)

LLM 없이 정해진 규칙으로 형식 잡음만 걷어낸다. 비용 0, 결과는 항상 같다.
코드 블록(``` ... ```) 내용과 인라인 코드(`...`)는 절대 고치지 않는다
(정답의 대부분이 함수·파라미터 이름이기 때문).

규칙 (생성자 인자로 하나씩 끌 수 있다. 규칙별 효과를 나눠 볼 때 사용)
    frontmatter   문서 앞 YAML 머리말(--- key: ... ---) 정리. frontmatter_keep 키(기본 title, description, tags)만
                  남기고 나머지(verified, sources 해시·경로 등 메타데이터)는 제거. 요약 키는 문서 전체 의미를
                  담고 있어 지우면 의미 유사도가 크게 떨어진다. frontmatter_keep=() 이면 머리말을 통째로 제거
                  (dev baseline v1 의 rule 동작, REGISTRY 의 rule_fm_all)
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

from compressors.base import Compressor

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
FM_KEY = re.compile(r"^([\w-]+):")
FRONTMATTER_KEEP = ("title", "description", "tags")


def trim_frontmatter(block: str, keep: tuple[str, ...]) -> str:
    """머리말 블록(--- ... ---)에서 keep 에 든 최상위 키만 남긴다. 들여쓰기·목록으로 이어지는 줄은
    앞 키에 딸린 값으로 본다. 남길 키가 없으면 블록을 통째로 지운다."""
    kept: list[str] = []
    on = False
    for line in block.split("\n")[1:-2]:      # 여는 ---, 닫는 --- 와 그 뒤 빈 문자열 제외
        m = FM_KEY.match(line)
        if m:
            on = m.group(1) in keep
        if on:
            kept.append(line)
    return "---\n" + "\n".join(kept) + "\n---\n" if kept else ""


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
    targets = ("context",)
    RULES = ("frontmatter", "anchors", "html", "links", "emphasis",
             "admonitions", "dedup_code", "whitespace")

    def __init__(self, frontmatter_keep: tuple[str, ...] = FRONTMATTER_KEEP, name: str = "rule", **enabled: bool):
        unknown = set(enabled) - set(self.RULES)
        if unknown:
            raise ValueError(f"알 수 없는 규칙: {sorted(unknown)}")
        self.enabled = {r: enabled.get(r, True) for r in self.RULES}
        self.frontmatter_keep = tuple(frontmatter_keep)
        self.name = name                # 결과 기록용 이름. 설정을 바꾼 변형은 REGISTRY 키와 같게 준다

    def config(self) -> dict:
        return {**self.enabled, "frontmatter_keep": list(self.frontmatter_keep)}

    def compress_context(self, question: str, context: str) -> str:
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
        self.add_info(rule_hits=dict(hits))
        return text

    def _prose(self, s: str, hits: Counter) -> str:
        on = self.enabled

        def sub(rule: str, pattern: re.Pattern, repl, text: str) -> str:
            text, n = pattern.subn(repl, text)
            hits[rule] += n
            return text

        if on["frontmatter"]:
            s = sub("frontmatter", FRONTMATTER, lambda m: trim_frontmatter(m.group(0), self.frontmatter_keep), s)
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
