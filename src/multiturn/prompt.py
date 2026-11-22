"""
멀티턴 답변 메시지 조립 (src/prompts/mt_answer_<version>.md)

    p = load_mt_prompt("v1")
    system = p.system
    user = p.user_message(turn, corpus)     # 턴의 evidence_pages 원문을 싱글턴 build_context 형식으로 첨부

문서 블록은 싱글턴과 같다: "## Document: <doc_id>\n\n<원문>" 을 빈 줄로 이어 <documentation> 안에 넣는다.
history 압축기(per_message)는 <documentation> ... </documentation> 블록만 압축 대상으로 본다 (DOC_BLOCK_RE).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
DOC_BLOCK_RE = re.compile(r"(<documentation>\n)(.*?)(\n</documentation>)", re.S)
SECTIONS = ("system", "format", "user_with_docs", "user_no_docs")


@dataclass
class MTPrompt:
    version: str
    sha256: str
    system: str
    format: dict[str, str]
    user_with_docs: str
    user_no_docs: str

    def answer_format(self, qtype: str | None) -> str:
        return self.format.get(qtype or "default") or self.format["default"]

    def user_text(self, question: str, qtype: str | None, context: str | None) -> str:
        fmt = self.answer_format(qtype)
        if context:
            return self.user_with_docs.format(context=context, question=question, answer_format=fmt)
        return self.user_no_docs.format(question=question, answer_format=fmt)

    def user_message(self, turn: dict, corpus) -> str:
        context = build_context(corpus, turn["evidence_pages"]) if turn["evidence_pages"] else None
        return self.user_text(turn["question"], turn.get("type"), context)


def build_context(corpus, pages: list[str]) -> str:
    """싱글턴 experiment.build_context 와 같은 형식 (그 함수는 item dict 를 받아 여기서 같은 식을 쓴다)."""
    from experiment import build_context as single_build_context
    return single_build_context(corpus, {"evidence_pages": pages})


def load_mt_prompt(version: str = "v1") -> MTPrompt:
    path = PROMPTS_DIR / f"mt_answer_{version}.md"
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    sections, cur = {}, None
    for line in text.split("\n"):
        m = re.match(r"## (\w+)\s*$", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
        elif cur:
            sections[cur].append(line)
    sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    missing = set(SECTIONS) - sections.keys()
    if missing:
        raise ValueError(f"{path}: 섹션이 없습니다: {sorted(missing)}")
    fmt = dict(re.findall(r"^- (\w+):[ \t]*(.+?)\s*$", sections["format"], re.M))
    if "default" not in fmt:
        raise ValueError(f"{path}: format 에 default 줄이 없습니다")
    return MTPrompt(version=version, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
                    system=sections["system"], format=fmt,
                    user_with_docs=sections["user_with_docs"], user_no_docs=sections["user_no_docs"])
