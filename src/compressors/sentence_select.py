"""
문장 단위 선택 압축 (멀티턴용, 질문을 보지 않는다)

rule 다음 단계로 쓴다 ("rule>sent_r70"). 문서를 한 번 압축해 여러 턴에 재사용하는 조건이라
질문은 읽지 않는다. 토큰을 지우지 않고 단위(문장·목록 항목)를 통째로 남기거나 지운다.
남은 단위는 원문 글자 그대로라서 토큰 단위 압축의 구두점 분해(0.95.0 -> 0 95 0)와
연결어 삭제가 생기지 않는다.

단위
    코드 블록, 문서 경계 줄(## Document:), 머리말(--- ... ---), 제목(#), 표 행(|), 인용(>),
    글자 없는 줄(구분선 등)은 보호.
    빈 줄은 구조로 남긴다.
    목록 항목은 줄 하나가 단위, 나머지 본문 줄은 문장으로 나눈 것이 단위.
    본문 단위라도 답이 될 만한 형태면 보호한다. 표지는 number, quoted(따옴표 리터럴).
    어느 표지를 보호할지는 protect 수준으로 고른다 (PROTECT_LEVELS):
        loose      number, quoted
        structure  표지 보호 없음 (구조 단위만 보호)

점수와 선택
    보호되지 않은 단위(후보)만 점수를 매긴다. 기본 점수는 LLMLingua-2 의 단어별 보존 확률 평균이다
    (라이브러리의 context-level filter 와 같은 계산, 질문 없음). 점수 높은 순으로 후보 글자 수의
    keep_ratio 만큼 남긴다.

건너뛰기 (문서별, 그 문서는 원문 그대로)
    skip_short   후보 + 보호 글자 수가 min_chars 미만
    skip_dense   보호 글자 비율이 max_protected_share 이상 (기본 1.0 = 끔. 1.0 이면 skip_no_candidates 와 같다)
    skip_no_candidates 후보 단위가 없음
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from compressors.base import Compressor

POLICY_VERSION = "sentence-select-v1"

_FENCE_LINE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_DOCUMENT_HEADER = re.compile(r"^## Document:")
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]")
_TABLE_ROW = re.compile(r"^[ \t]*\|")
_QUOTE = re.compile(r"^[ \t]*>")
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")
# 문장 끝: . ! ? 뒤 공백, 다음이 대문자·여는 기호. "e.g. X" 같은 약어는 끊지 않는다
_SENTENCE_END = re.compile(r"(?<=[.!?])(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\betc\.)[ \t]+(?=[A-Z`\"'(\[*_])")

# strict(인라인 코드·식별자·값 단어까지 보호)와 literal(인라인 코드까지)은 지울 몫이 1~5% 라 뺐다
# (docs/results/multiturn_compression_v1.md 의 측정)
PROTECT_LEVELS = {
    "loose": frozenset({"number", "quoted"}),
    "structure": frozenset(),
}


def _answer_shaped(text: str) -> list[str]:
    """답이 될 만한 형태 표지들 (비어 있으면 후보)."""
    reasons = []
    if re.search(r"\d", text):
        reasons.append("number")
    if re.search(r"\"[^\"\n]+\"|(?<![A-Za-z])'[^'\n]+'(?![A-Za-z])", text):
        reasons.append("quoted")
    return reasons


@dataclass
class Unit:
    text: str               # 원문 글자 그대로 (줄 끝 개행 제외)
    kind: str               # code, doc_header, frontmatter, heading, table, quote, blank, list, sentence
    protected: bool
    line: int               # 같은 줄에서 나온 문장은 같은 line 번호
    newline: str = ""       # 이 줄의 끝 개행 (줄의 마지막 단위에만)
    indent: str = ""        # 줄 앞 들여쓰기 (줄의 첫 단위에만)
    reasons: tuple = ()


def split_units(text: str) -> list[Unit]:
    """문서를 단위로 나눈다. "".join(재조립) 하면 원문과 같다 (모든 단위를 남길 때)."""
    units: list[Unit] = []
    lines = text.splitlines(keepends=True)
    fence: str | None = None
    code: list[str] = []
    line_no = 0
    in_frontmatter = False
    frontmatter: list[str] = []
    seen_content = False

    def body(raw: str) -> tuple[str, str]:
        stripped = raw.rstrip("\r\n")
        return stripped, raw[len(stripped):]

    for raw in lines:
        line_no += 1
        content, nl = body(raw)
        if fence is not None:
            code.append(raw)
            match = _FENCE_LINE.match(content)
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) \
                    and not content[match.end():].strip():
                block = "".join(code)
                units.append(Unit(block, "code", True, line_no, newline=""))
                code, fence = [], None
            continue
        if in_frontmatter:
            frontmatter.append(raw)
            if content.strip() == "---":
                units.append(Unit("".join(frontmatter), "frontmatter", True, line_no))
                frontmatter, in_frontmatter = [], False
            continue
        match = _FENCE_LINE.match(content)
        if match:
            fence = match.group(1)
            code = [raw]
            seen_content = True
            continue
        if content.strip() == "---" and not seen_content:
            in_frontmatter = True
            frontmatter = [raw]
            continue
        if not content.strip():
            units.append(Unit(content, "blank", True, line_no, newline=nl))
            continue
        seen_content = True
        if _DOCUMENT_HEADER.match(content):
            units.append(Unit(content, "doc_header", True, line_no, newline=nl))
            seen_content = False  # 다음 문서의 머리말을 알아본다
            continue
        if not re.search(r"[A-Za-z]", content):     # 구분선(---), 기호만 있는 줄
            units.append(Unit(content, "structure", True, line_no, newline=nl))
            continue
        for pattern, kind in ((_HEADING, "heading"), (_TABLE_ROW, "table"), (_QUOTE, "quote")):
            if pattern.match(content):
                units.append(Unit(content, kind, True, line_no, newline=nl))
                break
        else:
            indent = content[: len(content) - len(content.lstrip(" \t"))]
            rest = content[len(indent):]
            if _LIST_ITEM.match(content):
                pieces, kind = [rest], "list"
            else:
                pieces, kind = _SENTENCE_END.split(rest), "sentence"
            for i, piece in enumerate(pieces):
                reasons = tuple(_answer_shaped(piece))
                units.append(Unit(
                    piece, kind, False, line_no,          # 본문 보호 여부는 protect 수준에 따라 plan() 이 정한다
                    newline=nl if i == len(pieces) - 1 else "",
                    indent=indent if i == 0 else "",
                    reasons=reasons,
                ))
    if fence is not None:       # 닫히지 않은 코드 블록은 끝까지 코드로 본다
        units.append(Unit("".join(code), "code", True, line_no))
    if in_frontmatter:
        units.append(Unit("".join(frontmatter), "frontmatter", True, line_no))
    return units


def join_units(units: list[Unit], keep: list[bool]) -> str:
    """남길 단위만 이어 붙인다. 같은 줄 문장은 공백 하나로, 단위가 모두 지워진 줄은 줄째 없앤다."""
    out: list[tuple[bool, str]] = []      # (여러 줄짜리 블록 여부, 글자)
    by_line: dict[int, list[int]] = {}
    order: list[int] = []
    for i, u in enumerate(units):
        if u.kind in ("code", "frontmatter"):
            order.append(-(i + 1))        # 여러 줄짜리는 따로 둔다
            continue
        if u.line not in by_line:
            by_line[u.line] = []
            order.append(u.line)
        by_line[u.line].append(i)
    for key in order:
        if key < 0:
            i = -key - 1
            if keep[i]:
                out.append((True, units[i].text))
            continue
        idx = by_line[key]
        kept = [i for i in idx if keep[i]]
        if not kept:
            continue
        first, last = units[idx[0]], units[idx[-1]]
        out.append((False, first.indent + " ".join(units[i].text for i in kept) + last.newline))
    # 지운 문단 때문에 생긴 빈 줄 연속은 하나로. 코드 블록·머리말 안은 원문 그대로 둔다
    # (예전에는 전체에 걸어 Python 함수 사이 빈 줄 두 개가 하나로 줄었다)
    pieces: list[str] = []
    run: list[str] = []
    for is_block, text in out:
        if is_block:
            pieces.append(re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", "".join(run)))
            pieces.append(text)
            run = []
        else:
            run.append(text)
    pieces.append(re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", "".join(run)))
    return "".join(pieces)


def _llmlingua2_scorer(model_name: str, model_revision: str, device: str) -> Callable[[list[str]], list[float]]:
    """LLMLingua-2 단어별 보존 확률의 단위 평균 (compress_prompt 의 context-level filter 와 같은 값)."""
    from compressors.llmlingua2 import _load_engine

    def score(texts: list[str]) -> list[float]:
        engine = _load_engine(model_name, model_revision, device)
        get_prob = getattr(engine, "_PromptCompressor__get_context_prob")   # llmlingua==0.2.2
        probs, _ = get_prob([[t] for t in texts], token_to_word="mean", force_tokens=[], token_map={},
                            force_reserve_digit=False)
        return [float(p) for p in probs]

    return score


@dataclass(frozen=True)
class DroppedUnit:
    """압축 때 지운 후보 단위 하나 (원문 글자 그대로)."""
    doc_index: int          # split_documents 순서
    unit_index: int         # 그 문서 split_units 순서
    source: str             # "## Document:" 뒤 이름 (없으면 "")
    text: str


def _document_name(document: str) -> str:
    match = re.match(r"## Document:[ \t]*(.*)", document)
    return match.group(1).strip() if match else ""


def split_documents(context: str) -> list[str]:
    """"## Document:" 줄 앞에서 나눈다 (첫 조각은 경계 줄 앞 머리글일 수 있다)."""
    starts = [m.start() for m in re.finditer(r"^## Document:", context, re.M)]
    if not starts or starts[0] != 0:
        starts = [0, *starts]
    return [context[a:b] for a, b in zip(starts, [*starts[1:], len(context)])]


class SentenceSelectCompressor(Compressor):
    """보호되지 않은 문장·목록 항목을 점수 낮은 것부터 통째로 지운다. 질문은 보지 않는다."""

    targets = ("context",)

    def __init__(
        self,
        *,
        keep_ratio: float = 0.7,
        protect: str = "loose",
        min_chars: int = 1500,
        max_protected_share: float = 1.0,
        scorer: Callable[[list[str]], list[float]] | None = None,
        model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        model_revision: str = "5f0c827",
        device: str = "cpu",
        name: str | None = None,
    ):
        if not 0 < keep_ratio <= 1:
            raise ValueError("keep_ratio는 0보다 크고 1 이하여야 합니다")
        if not 0 < max_protected_share <= 1:
            raise ValueError("max_protected_share는 0보다 크고 1 이하여야 합니다")
        if protect not in PROTECT_LEVELS:
            raise ValueError(f"protect는 {sorted(PROTECT_LEVELS)} 중 하나여야 합니다")
        self.keep_ratio = float(keep_ratio)
        self.protect = protect
        self.min_chars = int(min_chars)
        self.max_protected_share = float(max_protected_share)
        self.model_name = model_name
        self.model_revision = model_revision
        self.device = device
        self._scorer = scorer
        self.scorer_name = "custom" if scorer is not None else "llmlingua2_mean_word_prob"
        self.name = name or f"sent_{protect}_r{round(self.keep_ratio * 100):02d}"

    def config(self) -> dict:
        return {
            "method": "sentence_select",
            "policy_version": POLICY_VERSION,
            "keep_ratio": self.keep_ratio,
            "protect": self.protect,
            "protect_reasons": sorted(PROTECT_LEVELS[self.protect]),
            "min_chars": self.min_chars,
            "max_protected_share": self.max_protected_share,
            "scorer": self.scorer_name,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "uses_question": False,
        }

    def _score(self, texts: list[str]) -> list[float]:
        if self._scorer is None:
            self._scorer = _llmlingua2_scorer(self.model_name, self.model_revision, self.device)
        scores = list(self._scorer(texts))
        if len(scores) != len(texts):
            raise ValueError(f"점수 개수 {len(scores)} 가 단위 개수 {len(texts)} 와 다릅니다")
        return scores

    def _select(self, units: list[Unit], candidates: list[int], scores: list[float]) -> list[bool]:
        """점수 높은 순으로 후보 글자의 keep_ratio 를 채운다 (같은 점수면 앞 단위 먼저)."""
        budget = self.keep_ratio * sum(len(units[i].text) for i in candidates)
        keep = [True] * len(units)
        kept_chars = 0
        for _, i in sorted(zip(scores, candidates), key=lambda p: (-p[0], p[1])):
            if kept_chars >= budget:
                keep[i] = False
            else:
                kept_chars += len(units[i].text)
        return keep

    def _extra_info(self) -> dict:
        return {"method": "sentence_select", "policy_version": POLICY_VERSION, "uses_question": False}

    def _score_candidates(self, question: str, texts: list[str]) -> list[float]:
        """후보 단위 점수. 이 클래스는 질문을 쓰지 않는다 (query_extract 가 재정의)."""
        return self._score(texts)

    def plan(self, document: str) -> tuple[list[Unit], list[int], str]:
        """(단위, 후보 인덱스, 상태). 상태가 select 가 아니면 원문 그대로 둔다."""
        units = split_units(document)
        guarded = PROTECT_LEVELS[self.protect]
        for u in units:
            if u.kind in ("sentence", "list"):
                u.protected = bool(guarded.intersection(u.reasons))
        candidates = [i for i, u in enumerate(units) if not u.protected]
        cand_chars = sum(len(units[i].text) for i in candidates)
        total = sum(len(u.text) for u in units if u.kind != "blank")
        if total < self.min_chars:
            return units, candidates, "skip_short"
        if not candidates:
            return units, candidates, "skip_no_candidates"
        if total and (total - cand_chars) / total >= self.max_protected_share:
            return units, candidates, "skip_dense"
        return units, candidates, "select"

    def compress_context(self, question: str, context: str) -> str:   # 이 클래스는 question 을 쓰지 않는다
        started = time.perf_counter()
        docs = []
        out: list[str] = []
        # 지운 후보 단위 (문서 순서, 문서 안 순서). supplement 가 이 중에서 질문 관련 문장을 되살린다
        self._dropped: list[DroppedUnit] = []
        for doc_index, document in enumerate(split_documents(context)):
            units, candidates, status = self.plan(document)
            cand_chars = sum(len(units[i].text) for i in candidates)
            record = {
                "status": status,
                "chars": len(document),
                "units": len(units),
                "candidate_units": len(candidates),
                "candidate_chars": cand_chars,
            }
            if status != "select":
                out.append(document)
                docs.append(record)
                continue
            scores = self._score_candidates(question, [units[i].text for i in candidates])
            keep = self._select(units, candidates, scores)
            kept_chars = sum(len(units[i].text) for i in candidates if keep[i])
            source = _document_name(document)
            self._dropped.extend(
                DroppedUnit(doc_index=doc_index, unit_index=i, source=source, text=units[i].text)
                for i in candidates if not keep[i]
            )
            compressed = join_units(units, keep)
            out.append(compressed)
            record.update(
                dropped_units=keep.count(False),
                dropped_chars=cand_chars - kept_chars,
                output_chars=len(compressed),
            )
            docs.append(record)
        result = "".join(out)
        self.add_info(
            **self._extra_info(),
            keep_ratio=self.keep_ratio,
            protect=self.protect,
            documents=docs,
            dropped_units=sum(d.get("dropped_units", 0) for d in docs),
            dropped_chars=sum(d.get("dropped_chars", 0) for d in docs),
            source_chars=len(context),
            output_chars=len(result),
            duration_sec=round(time.perf_counter() - started, 4),
        )
        return result
