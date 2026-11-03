"""정답 사본 지우기 (진단용, C1 중복성 검증).

C1 "압축에 강해 보이는 이유는 기억이 아니라 문서 중복성이다" 를 확인하려고, 근거 단위와 정답 사본 단위를 골라 지운다.
LLM 을 쓰지 않는다.

단위 (segment)
    코드 블록      펜스(``` / ~~~) 포함 블록 전체. 줄만 지우면 남은 코드가 단서가 되므로 통째로 지운다
    산문·목록      문장 단위. 목록 항목은 표시(- / 1.) 를 남기고 문장만 지우며, 문장이 다 지워지면 줄째 지운다
    표 행·제목     줄 하나
    머리말         --- 사이의 YAML 줄 하나씩 (description·tags 에도 정답이 나온다)
    문서 머리줄    "## Document: ..." (무작위 대조 조건은 지우지 않는다)
근거 단위 = drop_evidence.evidence_lines 가 찾은 줄에 걸친 단위 (코드 블록 안의 줄이면 블록 전체)
사본 단위 = 정답 핵심어(PromptParts.answer_core, core_match.core_needles) 가 core_match.find_core 로 잡히는 단위

조건
    drop_all_copies        근거 단위 + 사본 단위를 모두 지운다. 지운 문맥에서 정답 핵심어가 0건이어야 한다
    keep_code_copy         drop_all_copies 에서 근거가 아닌 코드 블록 사본 하나(처음 나온 것)만 남긴다
    keep_prose_copy        같은 방식으로 근거가 아닌 코드 밖 사본 하나만 남긴다
    keep_answer_in_place   drop_all_copies 에서 정답 사본이 든 근거 단위 하나만 정답 구절로 바꿔 제자리에 남긴다
                           (코드 블록이면 블록 자리에 구절 한 줄). LLMLingua-2 의 "정답 단어만 제자리에 남음" 재현.
                           결과는 정답 유형(core_match.answer_kind, 식별자형/값형)으로 나눠 본다
    matched_random_drop    근거·사본이 아닌 단위에서 drop_all_copies 가 지운 토큰 수만큼 무작위로 지운다.
                           코드 블록 토큰과 그 밖 토큰을 따로 맞추고(층화), 코드 쪽이 모자라면 나머지를 밖에서 채운다.
                           난수는 (seed, 질문) 으로 정한다. run 마다 _s2, _s3 를 쓴다
사본 검증 (info.verified)
    drop_all_copies    지운 문맥에서 정답 핵심어가 하나도 안 잡힘 (단위 경계를 넘는 사본도 문맥 전체로 다시 본다)
    keep_*_copy        drop_all_copies 가 검증을 통과하고, 남긴 사본에서 정답 핵심어가 잡힘
    keep_answer_in_place   제자리 1건만 허용: 남긴 구절을 빼면 0건이고, 남긴 구절에서 정답 핵심어가 잡힘
    matched_random     근거 단위·사본 단위가 모두 그대로 남음, 지운 토큰 수가 목표의 ±TOKEN_TOLERANCE 안
    verified=False 나 defined=False(사본이 없거나 남길 종류의 사본이 없음) 인 trial 은 집계에서 뺀다.
    defined=False 이면 문맥을 그대로 돌려준다. 미리 src/copies_dry_run.py 로 조건별 문항을 골라 --ids 로 돌린다
info: defined, verified, reason, units, evidence_units, copy_units, copy_units_code, dropped_units, dropped_tokens,
      dropped_tokens_code, context_tokens, dropped_frac, (keep_*) kept_kind, (in_place) kept_phrase, (matched) target_tokens, target_tokens_code
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field

from compressors.base import CompressResult, Compressor, PromptParts
from compressors.drop_evidence import evidence_lines

TOKEN_TOLERANCE = 0.1     # matched_random_drop 이 지운 토큰 수와 목표의 허용 차 (비율)

_FENCE = re.compile(r"^\s*(```|~~~)")
_LIST = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+|\s*>\s*)")
# 문장 끝: . ! ? 뒤 공백, 다음이 대문자·코드·강조·괄호로 시작 ("e.g. query" 처럼 소문자가 오면 나누지 않는다)
_SENT_END = re.compile(r"[.!?]\s+(?=[A-Z`*\[(\"'])")


@dataclass
class Unit:
    kind: str                   # code | prose | list | table | heading | meta | doc_header
    text: str
    lines: tuple[int, ...]


@dataclass
class Segmented:
    lines: list[str]
    units: list[Unit] = field(default_factory=list)
    # 줄마다 ("keep",) | ("block", uid) | ("split", prefix, [uid, ...])
    layout: list[tuple] = field(default_factory=list)

    def render(self, drop: set[int], replace: dict[int, str] | None = None) -> str:
        """drop 단위를 지우고 replace 단위는 주어진 글로 바꾼 문맥. 바꾼 코드 블록은 블록 자리에 그 글 한 줄만 남는다."""
        replace = replace or {}
        if not drop and not replace:
            return "\n".join(self.lines)
        out: list[str] = []
        cut = False                         # 마지막으로 남긴 줄 뒤에 지운 줄이 있었는지
        for i, (line, lay) in enumerate(zip(self.lines, self.layout)):
            if lay[0] == "block":
                if lay[1] in drop or (lay[1] in replace and self.units[lay[1]].lines[0] != i):
                    cut = True
                    continue
                if lay[1] in replace:
                    line = replace[lay[1]]
            elif lay[0] == "split":
                kept = [replace.get(u, self.units[u].text) for u in lay[2] if u not in drop]
                if not kept:
                    cut = True
                    continue
                if len(kept) < len(lay[2]) or any(u in replace for u in lay[2]):
                    line = lay[1] + " ".join(kept)
            elif cut and not line.strip() and out and not out[-1].strip():
                continue                    # 지운 자리 앞뒤 빈 줄이 겹치면 하나만 남긴다
            out.append(line)
            cut = cut and not line.strip()
        return "\n".join(out)


def _split_sentences(text: str) -> list[str]:
    """문장 단위로 나눈다. 인라인 코드(`...`) 안에서는 나누지 않는다."""
    out, start = [], 0
    for m in _SENT_END.finditer(text):
        if text.count("`", 0, m.start()) % 2:
            continue
        piece = text[start:m.start() + 1].strip()
        if piece:
            out.append(piece)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def segment(context: str) -> Segmented:
    lines = context.split("\n")
    seg = Segmented(lines=lines)
    i, in_meta = 0, False
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        m = _FENCE.match(line)
        if m:
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(m.group(1)):
                j += 1
            j = min(j, len(lines) - 1)
            uid = len(seg.units)
            seg.units.append(Unit("code", "\n".join(lines[i:j + 1]), tuple(range(i, j + 1))))
            seg.layout.extend([("block", uid)] * (j - i + 1))
            i = j + 1
            continue
        if not s or s == "---":
            if s == "---":
                # 문서 머리줄 바로 다음(빈 줄 건너뜀)의 --- 가 머리말 시작, 다음 --- 가 끝
                prev = next((lines[k].strip() for k in range(i - 1, -1, -1) if lines[k].strip()), "")
                in_meta = not in_meta and prev.startswith("## Document:")
            seg.layout.append(("keep",))
            i += 1
            continue
        uid = len(seg.units)
        if s.startswith("## Document:"):
            seg.units.append(Unit("doc_header", line, (i,)))
            seg.layout.append(("split", "", [uid]))
        elif in_meta:
            seg.units.append(Unit("meta", line, (i,)))
            seg.layout.append(("split", "", [uid]))
        elif s.startswith("#"):
            seg.units.append(Unit("heading", line, (i,)))
            seg.layout.append(("split", "", [uid]))
        elif s.startswith("|"):
            seg.units.append(Unit("table", line, (i,)))
            seg.layout.append(("split", "", [uid]))
        else:
            lm = _LIST.match(line)
            prefix = lm.group(1) if lm else line[:len(line) - len(line.lstrip())]
            kind = "list" if lm else "prose"
            uids = []
            for sent in _split_sentences(line[len(prefix):]):
                uids.append(len(seg.units))
                seg.units.append(Unit(kind, sent, (i,)))
            seg.layout.append(("split", prefix, uids))
        i += 1
    return seg


def _has_core(text: str, needles: tuple[str, ...]) -> bool:
    from core_match import find_core
    return any(find_core(text, n) is not None for n in needles)


@dataclass
class Plan:
    """한 문맥의 단위 분석 결과 (조건마다 다시 계산하지 않도록)."""
    seg: Segmented
    evidence: set[int]
    copies: set[int]


def analyze(context: str, quotes: tuple[str, ...], needles: tuple[str, ...]) -> Plan:
    seg = segment(context)
    ev_lines, _ = evidence_lines(context, quotes)
    evidence = {u for u, unit in enumerate(seg.units) if unit.kind != "doc_header" and ev_lines & set(unit.lines)}
    copies = {u for u, unit in enumerate(seg.units) if _has_core(unit.text, needles)}
    return Plan(seg, evidence, copies)


class _CopiesBase(Compressor):
    targets = ("context",)

    def compress(self, parts: PromptParts) -> CompressResult:
        self._parts = parts
        return super().compress(parts)

    def compress_context(self, question: str, context: str) -> str:
        from llm import count_tokens   # 토크나이저는 실제로 지울 때만 불러온다

        self._tok = count_tokens
        needles = self._parts.answer_core
        plan = analyze(context, self._parts.evidence, needles)
        self.add_info(units=len(plan.seg.units), evidence_units=len(plan.evidence), copy_units=len(plan.copies),
                      copy_units_code=sum(plan.seg.units[u].kind == "code" for u in plan.copies),
                      context_tokens=count_tokens(context))
        if not needles or not plan.copies:
            return self._undefined(context, "정답 핵심어가 원문에 없음 (측정 불가)")
        self._replace: dict[int, str] = {}
        drop = self.choose(plan, question, needles)
        if drop is None:
            return context
        out = plan.seg.render(drop, self._replace)
        dropped = [plan.seg.units[u] for u in sorted(drop)]
        # 글을 바꾼 단위는 줄어든 만큼을 지운 토큰으로 센다
        tok = sum(count_tokens(u.text) for u in dropped) + sum(
            count_tokens(plan.seg.units[u].text) - count_tokens(t) for u, t in self._replace.items())
        self.add_info(dropped_units=len(dropped), dropped_tokens=tok,
                      dropped_tokens_code=sum(count_tokens(u.text) for u in dropped if u.kind == "code"),
                      dropped_frac=round(tok / max(1, self._info["context_tokens"]), 4))
        self.add_info(defined=True, **self.verify(plan, drop, out, needles))
        return out

    def _undefined(self, context: str, reason: str) -> str:
        self.add_info(defined=False, verified=False, reason=reason)
        return context

    def choose(self, plan: Plan, question: str, needles: tuple[str, ...]) -> set[int] | None:
        raise NotImplementedError

    def verify(self, plan: Plan, drop: set[int], out: str, needles: tuple[str, ...]) -> dict:
        raise NotImplementedError


def _residual(out: str, needles: tuple[str, ...]) -> list[str]:
    from core_match import find_core
    return [h for h in (find_core(out, n) for n in needles) if h is not None]


class DropAllCopies(_CopiesBase):
    name = "drop_all_copies"

    def choose(self, plan, question, needles):
        return plan.evidence | plan.copies

    def verify(self, plan, drop, out, needles):
        res = _residual(out, needles)
        return {"verified": not res, "reason": f"사본이 남음: {res}" if res else ""}


class KeepOneCopy(_CopiesBase):
    """drop_all_copies 에서 근거가 아닌 사본 하나만 남긴다. keep 이 "code" 면 코드 블록 사본, "prose" 면 그 밖."""

    def __init__(self, keep: str):
        self.keep = keep
        self.name = f"keep_{keep}_copy"

    def choose(self, plan, question, needles):
        cands = [u for u in sorted(plan.copies - plan.evidence)
                 if (plan.seg.units[u].kind == "code") == (self.keep == "code")]
        if not cands:
            self.add_info(defined=False, verified=False, reason=f"근거가 아닌 {self.keep} 사본이 없음")
            return None
        self._kept = cands[0]
        self.add_info(kept_kind=plan.seg.units[cands[0]].kind)
        return (plan.evidence | plan.copies) - {cands[0]}

    def verify(self, plan, drop, out, needles):
        res = _residual(plan.seg.render(drop | {self._kept}), needles)
        if res:
            return {"verified": False, "reason": f"남긴 사본 밖에도 사본이 남음: {res}"}
        if not _has_core(plan.seg.units[self._kept].text, needles):
            return {"verified": False, "reason": "남긴 사본에서 정답 핵심어가 안 잡힘"}
        return {"verified": True, "reason": ""}

    def config(self) -> dict:
        return {"keep": self.keep}


def _kept_phrase(text: str, needle: str, hit: str) -> str:
    """제자리에 남길 구절. 매칭은 영숫자에서 끊기므로 "*.example.com" 이 "example.com" 으로 잡힌다.
    정답 표기(앞 관사 뗀 것) 그대로가 단위 안에 영숫자 경계로 있으면 그 표기를, 없으면 찾은 구절을 남긴다.
    공백까지 넓히면 코드에서 "compresslevel=5" 처럼 다른 단서가 딸려 오므로 넓히지 않는다."""
    from core_match import _strip_article

    lit = _strip_article(needle)
    m = re.search(rf"(?<![A-Za-z0-9]){re.escape(lit)}(?![A-Za-z0-9])", text, re.I)
    return m.group() if m else hit


class KeepAnswerInPlace(_CopiesBase):
    """drop_all_copies 에서 정답 사본이 든 근거 단위 하나(처음 나온 것)를 지우지 않고 그 안의 정답 구절만 남긴다.
    LLMLingua-2 가 근거 문장의 다른 단어는 지우고 정답 단어만 제자리에 남기는 경우를 재현한다."""
    name = "keep_answer_in_place"

    def choose(self, plan, question, needles):
        from core_match import find_core

        cands = sorted(plan.evidence & plan.copies)
        if not cands:
            self.add_info(defined=False, verified=False, reason="정답 사본이 든 근거 단위가 없음")
            return None
        unit = plan.seg.units[cands[0]]
        hits = [(n, find_core(unit.text, n)) for n in needles]
        phrase = " ".join(_kept_phrase(unit.text, n, h) for n, h in hits if h is not None)
        self._kept = cands[0]
        self._replace = {cands[0]: phrase}
        self.add_info(kept_kind=unit.kind, kept_phrase=phrase)
        return (plan.evidence | plan.copies) - {cands[0]}

    def verify(self, plan, drop, out, needles):
        # 제자리 사본 1건만 허용: 남긴 구절을 빼면 0건, 남긴 구절에서는 잡혀야 한다
        res = _residual(plan.seg.render(drop | {self._kept}), needles)
        if res:
            return {"verified": False, "reason": f"제자리 밖에도 사본이 남음: {res}"}
        if not _has_core(self._replace[self._kept], needles):
            return {"verified": False, "reason": "남긴 구절에서 정답 핵심어가 안 잡힘"}
        return {"verified": True, "reason": ""}


class MatchedRandomDrop(_CopiesBase):
    """근거·사본이 아닌 단위에서 drop_all_copies 와 같은 토큰 수를 무작위로 지운다 (지운 양 대조)."""

    def __init__(self, seed: int = 1):
        self.seed = seed
        self.name = "matched_random_drop" if seed == 1 else f"matched_random_drop_s{seed}"

    def choose(self, plan, question, needles):
        tok = self._tok
        target = plan.evidence | plan.copies
        t_code = sum(tok(plan.seg.units[u].text) for u in target if plan.seg.units[u].kind == "code")
        t_all = sum(tok(plan.seg.units[u].text) for u in target)
        rng = random.Random(f"{self.seed}:{hashlib.sha1(question.encode('utf-8')).hexdigest()}")
        free = [u for u, unit in enumerate(plan.seg.units) if u not in target and unit.kind != "doc_header"]
        rng.shuffle(free)
        drop: set[int] = set()

        def fill(pool: list[int], want: float, limit: float) -> int:
            """섞인 순서대로 want 에 닿을 때까지 넣되, 넣으면 limit 를 넘는 단위는 건너뛴다."""
            got = 0
            for u in pool:
                n = tok(plan.seg.units[u].text)
                if got < want and got + n <= limit:
                    drop.add(u)
                    got += n
            return got

        slack = TOKEN_TOLERANCE * t_all
        # 코드 블록은 커서 목표를 넘기 쉽다. 코드 쪽 초과는 전체 허용 차 안에서만 두고, 모자라면 밖에서 채운다
        got_code = fill([u for u in free if plan.seg.units[u].kind == "code"], t_code, t_code + slack)
        fill([u for u in free if plan.seg.units[u].kind != "code"], t_all - got_code, t_all + slack - got_code)
        self.add_info(target_tokens=t_all, target_tokens_code=t_code)
        return drop

    def verify(self, plan, drop, out, needles):
        keep = plan.evidence | plan.copies
        flat = re.sub(r"\s+", " ", out)
        missing = [u for u in keep if re.sub(r"\s+", " ", plan.seg.units[u].text).strip() not in flat]
        got, want = self._info["dropped_tokens"], self._info["target_tokens"]
        reasons = []
        if missing:
            reasons.append(f"근거·사본 단위 {len(missing)}개가 사라짐")
        if want and abs(got - want) > TOKEN_TOLERANCE * want:
            reasons.append(f"지운 토큰 {got} (목표 {want})")
        return {"verified": not reasons, "reason": "; ".join(reasons)}

    def config(self) -> dict:
        return {"seed": self.seed, "token_tolerance": TOKEN_TOLERANCE}
