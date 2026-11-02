"""Versioned answer prompts shared by experiments and budgeted compressors."""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from compressors.base import PromptParts

# 답변 지시문은 src/prompts/answer_<버전>.md 에 둔다 (바꾸면 이전 결과와 비교할 수 없으므로 새 버전으로)
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass
class AnswerPrompt:
    version: str
    sha256: str                     # 파일 해시 앞 12자리 (같은 버전 이름으로 내용이 바뀌었는지 확인용)
    system: str                     # {answer_format} 자리에 문항 type 의 형식 줄을 넣는다
    user: str                       # {context}, {question} 를 채우는 틀 (문서 + 질문만)
    format: dict[str, str]          # type -> 지시 한 줄. "default" 는 type 이 없거나 모르는 값일 때

    def format_key(self, qtype: str | None) -> str:
        return qtype if qtype in self.format and qtype != "default" else "default"

    def parts(self, context: str, question: str, qtype: str | None,
              evidence: tuple[str, ...] = ()) -> PromptParts:
        """압축 전 입력 세 부분. system 은 형식 줄을 끼운 뒤의 전체 (압축 대상).
        evidence 는 문항의 근거 인용문 (drop_evidence 압축기가 읽는다, 메시지에는 들어가지 않음)."""
        fmt = self.format[self.format_key(qtype)]
        return PromptParts(system=self.system.replace("{answer_format}", fmt), context=context, question=question,
                           evidence=tuple(evidence))

    def messages(self, parts: PromptParts) -> list[dict]:
        user = self.user.format(context=parts.context, question=parts.question)
        return [{"role": "system", "content": parts.system}, {"role": "user", "content": user}]


def answer_prompt_versions() -> list[str]:
    return sorted(p.stem.removeprefix("answer_") for p in PROMPTS_DIR.glob("answer_*.md"))


def load_answer_prompt(version: str) -> AnswerPrompt:
    path = PROMPTS_DIR / f"answer_{version}.md"
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
    missing = {"system", "format", "user"} - sections.keys()
    if "{answer_format}" not in sections.get("system", ""):
        missing.add("system 의 {answer_format}")
    if missing:
        sys.exit(f"{path}: 섹션이 없습니다: {sorted(missing)}")
    fmt = dict(re.findall(r"^- (\w+):[ \t]*(.+?)\s*$", sections["format"], re.M))
    if "default" not in fmt:
        sys.exit(f"{path}: format 에 default 줄이 없습니다")
    if "TODO:" in sections["system"] or any("TODO:" in v for v in fmt.values()):
        sys.exit(f"{path}: 아직 채우지 않은 TODO 가 있습니다")
    return AnswerPrompt(version=version, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
                        system=sections["system"], user=sections["user"], format=fmt)
