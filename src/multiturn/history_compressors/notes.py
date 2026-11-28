"""
문서 블록을 짧은 글로 바꾸는 history 압축기: presummary, fact_notes

공통
    과거 user 메시지의 <documentation> 블록만 바꾼다. 질문·형식 줄과 assistant 답변은 그대로 둔다.
    직전 keep_recent 턴과 현재 턴의 문서는 원문으로 둔다.
    바꾼 글도 <documentation> 블록 안에 둔다 (답변 지시문 mt_answer_v2 는 이 블록을 제공된 문서로 본다. 지시문은 바꾸지 않는다).

presummary (사전 요약 대체)
    문서 블록의 "## Document: <페이지>" 마다 본문을, 위키 구축 단계에서 미리 만든 페이지 요약으로 바꾼다.
    요약은 build_presummaries.py 가 data/presummaries/<요약 모델>/<페이지 경로>.md 에 한 번 만들어 둔다 (PresummaryStore).
    요약이 없는 페이지가 나오면 원문으로 대체하지 않고 MissingPresummaryError 로 멈춘다.
    run 에서 압축 LLM 토큰은 0 이다. 요약 생성 비용은 구축 비용으로 _build_log.jsonl 에 따로 있다.

fact_notes (사실 메모)
    턴 j 가 끝날 때 그 턴의 문서·질문·답변에서 핵심 사실 메모를 뽑아 두고, 이후 턴의 기록에서 턴 j 의 문서 블록을 메모로 바꾼다.
    문서가 없는 턴은 바꿀 블록이 없어 메모를 만들지 않는다.
    정보 누출 금지: NotesExtractor.extract 는 (턴 번호, 그 턴의 문서, 질문, 답변, 목표 길이, sample_idx) 만 받는다.
    replay 에서 답변은 기준 궤적의 그 턴 답변이다 (기록에 들어가는 답변과 같다).
    같은 (턴, 문서, 질문, 답변, sample_idx) 이면 같은 메모를 쓴다 (메모리 안 memo + 응답 캐시, sample_idx 는 trial 의 sample).
    메모 추출 토큰은 메모를 만든 턴의 trial 에 넣는다: replay 가 턴 k trial 에서 turn_end(...) 로 턴 k 메모를 받아 그 토큰을 더한다.
    이후 턴에서 같은 메모를 다시 쓰는 것은 0 토큰이다. 메모 실패(3번 시도 뒤에도 빈 출력·length) 는 NotesFailedError.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from multiturn.history_compressors.base import HistoryCompressor, HistoryResult, split_turns
from multiturn.history_compressors.budget import default_token_counter, question_of
from multiturn.prompt import DOC_BLOCK_RE

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
PRESUMMARY_ROOT = Path(__file__).resolve().parents[3] / "data" / "presummaries"
MIN_TARGET_TOKENS = 60
_DOC_SPLIT_RE = re.compile(r"^## Document: (.+)$", re.M)
PRESUMMARY_NOTE = "(Pre-written summary of this page.)"


class MissingPresummaryError(RuntimeError):
    """요약이 없는 페이지. 원문으로 대체하지 않고 멈춘다."""


class NotesFailedError(RuntimeError):
    """메모 추출이 3번 모두 빈 출력 또는 출력 한도(length) 로 끝났다."""


@dataclass
class SectionPrompt:
    version: str
    sha256: str
    sections: dict


def load_section_prompt(stem: str, version: str, required=("system", "user")) -> SectionPrompt:
    path = PROMPTS_DIR / f"{stem}_{version}.md"
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
    missing = set(required) - sections.keys()
    if missing:
        raise ValueError(f"{path}: 섹션이 없습니다: {sorted(missing)}")
    return SectionPrompt(version, hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], sections)


def target_tokens_for(source_tokens: int, ratio: float) -> int:
    return max(MIN_TARGET_TOKENS, round(source_tokens * ratio))


def output_ok(res) -> bool:
    return bool((res.text or "").strip()) and res.finish_reason != "length"


def split_doc_pages(block: str) -> list[tuple[str | None, str]]:
    """<documentation> 블록 본문 -> [(페이지, 본문)]. 첫 "## Document:" 앞 글자는 (None, 글자)."""
    out, heads = [], list(_DOC_SPLIT_RE.finditer(block))
    if not heads:
        return [(None, block)]
    if block[:heads[0].start()].strip():
        out.append((None, block[:heads[0].start()]))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(block)
        out.append((h.group(1).strip(), block[h.end():end]))
    return out


def _older_turns(past: list[dict], keep_recent: int) -> tuple[list[list[dict]], int]:
    turns = split_turns(past)
    n_old = max(0, len(turns) - keep_recent)
    return turns, n_old


# ---------------- presummary ----------------

class PresummaryStore:
    """data/presummaries/<모델>/ 의 페이지 요약과 _manifest.json, _build_log.jsonl."""

    def __init__(self, root: Path):
        self.root = Path(root)
        mf = self.root / "_manifest.json"
        if not mf.exists():
            raise MissingPresummaryError(f"{mf} 가 없습니다. build_presummaries.py 로 먼저 요약을 만드세요")
        self.manifest = json.loads(mf.read_text(encoding="utf-8"))
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()

    @classmethod
    def for_model(cls, model: str, root: Path = PRESUMMARY_ROOT) -> "PresummaryStore":
        return cls(Path(root) / model)

    def path(self, page: str) -> Path:
        return self.root / page

    def get(self, page: str) -> str:
        with self._lock:
            if page in self._cache:
                return self._cache[page]
        p = self.path(page)
        if not p.exists():
            raise MissingPresummaryError(f"{page} 의 사전 요약이 없습니다 ({p}). build_presummaries.py 로 만드세요. "
                                         "원문으로 대체하지 않습니다.")
        text = p.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        if not text:
            raise MissingPresummaryError(f"{p} 가 비었습니다")
        with self._lock:
            self._cache[page] = text
        return text

    def build_log(self) -> list[dict]:
        p = self.root / "_build_log.jsonl"
        if not p.exists():
            return []
        last = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                last[r["page"]] = r
        return list(last.values())

    def config(self) -> dict:
        return {"root": self.root.as_posix(), "manifest": self.manifest}


class PreSummary(HistoryCompressor):
    name = "presummary"

    def __init__(self, store: PresummaryStore | None, keep_recent: int = 1, token_counter=None):
        if store is None:
            raise ValueError("presummary 는 사전 요약 저장소가 필요합니다 (--presummary-model)")
        if keep_recent < 0:
            raise ValueError("keep_recent 는 0 이상")
        self.store = store
        self.keep_recent = keep_recent
        self.count = token_counter or default_token_counter

    def replace_block(self, block: str, pages_used: list[str]) -> str:
        parts = []
        for page, body in split_doc_pages(block):
            if page is None:
                parts.append(body)
                continue
            pages_used.append(page)
            parts.append(f"## Document: {page}\n\n{PRESUMMARY_NOTE}\n{self.store.get(page)}\n\n")
        return "".join(parts).rstrip("\n")

    def compress_past(self, past, current_user, budget_tokens, state):
        turns, n_old = _older_turns(past, self.keep_recent)
        pages: list[str] = []
        blocks = 0
        out = []
        for j, t in enumerate(turns):
            for m in t:
                m = dict(m)
                if j < n_old and m["role"] == "user":
                    def repl(match):
                        nonlocal blocks
                        blocks += 1
                        return match.group(1) + self.replace_block(match.group(2), pages) + match.group(3)
                    m["content"] = DOC_BLOCK_RE.sub(repl, m["content"])
                out.append(m)
        return HistoryResult(messages=out, info={"doc_blocks_replaced": blocks, "pages_replaced": pages})

    def config(self):
        return {"name": self.name, "keep_recent": self.keep_recent, "store": self.store.config()}


# ---------------- fact_notes ----------------

@dataclass
class NotesOutcome:
    turn: int
    text: str | None
    source_tokens: int
    target_tokens: int
    results: list = field(default_factory=list)
    cache_hits: list = field(default_factory=list)
    failed: bool = False
    reason: str | None = None
    notes_tokens: int | None = None

    @property
    def prompt_tokens(self):
        return sum(r.prompt_tokens for r in self.results)

    @property
    def completion_tokens(self):
        return sum(r.completion_tokens for r in self.results)

    @property
    def reasoning_tokens(self):
        return sum(r.reasoning_tokens or 0 for r in self.results)

    def record(self, target_ratio: float) -> dict:
        ratio = round(self.notes_tokens / self.source_tokens, 4) if self.notes_tokens is not None and self.source_tokens else None
        return {"turn": self.turn, "source_tokens": self.source_tokens, "target_tokens": self.target_tokens,
                "notes_tokens": self.notes_tokens, "ratio": ratio, "target_ratio": target_ratio,
                "over_2x_target": (self.notes_tokens is not None and self.notes_tokens > 2 * self.target_tokens),
                "attempts": len(self.results), "cache_hits": sum(self.cache_hits), "failed": self.failed}


class NotesExtractor:
    """메모 추출 LLM 호출. cached 는 multiturn.response_cache.CachedLLM (메모 모델을 감쌈).

    extract 는 그 턴의 문서·질문·답변만 받는다. 이후 턴의 질문, 정답, key_facts, key_entities 를 받는 인자가 없다."""

    def __init__(self, cached, target_ratio: float = 0.25, prompt: SectionPrompt | None = None,
                 max_attempts: int = 3, token_counter=None):
        if not 0 < target_ratio <= 1:
            raise ValueError("notes target_ratio 는 0 초과 1 이하")
        self.cached = cached
        self.target_ratio = target_ratio
        self.prompt = prompt or load_section_prompt("fact_notes", "v1")
        self.max_attempts = max_attempts
        self.count = token_counter or default_token_counter

    def build_messages(self, turn: int, documentation: str, question: str, answer: str, target_tokens: int) -> list[dict]:
        user = self.prompt.sections["user"].format(turn=turn, documentation=documentation.strip(),
                                                   question=question.strip(), answer=(answer or "").strip() or "(empty)",
                                                   target_tokens=target_tokens)
        return [{"role": "system", "content": self.prompt.sections["system"]}, {"role": "user", "content": user}]

    def extract(self, turn: int, documentation: str, question: str, answer: str, sample_idx: int) -> NotesOutcome:
        src = self.count(documentation)
        target = target_tokens_for(src, self.target_ratio)
        messages = self.build_messages(turn, documentation, question, answer, target)
        out = NotesOutcome(turn=turn, text=None, source_tokens=src, target_tokens=target)
        for _ in range(self.max_attempts):
            res, hit = self.cached.chat(messages, sample_idx=sample_idx, store_if=output_ok)
            out.results.append(res)
            out.cache_hits.append(hit)
            if output_ok(res):
                out.text = res.text.strip()
                out.notes_tokens = self.count(out.text)
                return out
            out.reason = "length" if res.finish_reason == "length" else "empty"
        out.failed = True
        return out

    def config(self) -> dict:
        llm = self.cached.llm
        return {"prompt": [self.prompt.version, self.prompt.sha256], "max_attempts": self.max_attempts,
                "target_ratio": self.target_ratio, "min_target_tokens": MIN_TARGET_TOKENS,
                "sampling": llm.sampling_info(), "backend": llm.backend, "base_url": llm.base_url}


def notes_block(turn: int, text: str) -> str:
    return f"## Fact notes from turn {turn} (they replace the documentation attached in that turn)\n\n{text.strip()}"


class FactNotes(HistoryCompressor):
    name = "fact_notes"
    per_sample = True        # 기록이 sample 마다 다르다 (메모 호출의 sample_idx). replay 가 state={"sample_idx": i} 로 넘긴다

    def __init__(self, extractor: NotesExtractor | None, keep_recent: int = 1):
        if extractor is None:
            raise ValueError("fact_notes 는 메모 추출기가 필요합니다 (--notes-model, --notes-reasoning-effort, "
                             "--notes-max-tokens)")
        if keep_recent < 0:
            raise ValueError("keep_recent 는 0 이상")
        self.extractor = extractor
        self.keep_recent = keep_recent
        self._memo: dict[tuple, NotesOutcome] = {}
        self._locks: dict[tuple, threading.Lock] = {}
        self._lock = threading.Lock()

    def notes_for(self, turn: int, user_content: str, answer: str, sample_idx: int) -> NotesOutcome | None:
        """턴 turn 의 메모. 그 턴 user 메시지에 문서 블록이 없으면 None. 문서 블록이 여럿이면 이어 붙여 한 번에 뽑는다."""
        docs = [m.group(2) for m in DOC_BLOCK_RE.finditer(user_content)]
        if not docs:
            return None
        documentation = "\n\n".join(docs)
        question = question_of(user_content)
        key = (turn, documentation, question, answer, sample_idx)
        with self._lock:
            if key in self._memo:
                return self._memo[key]
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:                                   # 같은 메모를 동시에 두 번 부르지 않는다
            with self._lock:
                if key in self._memo:
                    return self._memo[key]
            o = self.extractor.extract(turn, documentation, question, answer, sample_idx)
            if o.failed:
                raise NotesFailedError(f"fact_notes: 턴 {turn} 메모 추출이 {len(o.results)}번 모두 실패 ({o.reason})")
            with self._lock:
                self._memo[key] = o
            return o

    def turn_end(self, turn: int, user_content: str, answer: str, sample_idx: int) -> NotesOutcome | None:
        """턴이 끝날 때 만드는 메모 (토큰은 이 턴 trial 에 귀속)."""
        return self.notes_for(turn, user_content, answer, sample_idx)

    def compress_past(self, past, current_user, budget_tokens, state):
        sample_idx = (state or {}).get("sample_idx", 0)
        turns, n_old = _older_turns(past, self.keep_recent)
        out, replaced = [], []
        for j, t in enumerate(turns):
            user = next((m["content"] for m in t if m["role"] == "user"), "")
            answer = "\n".join(m["content"] for m in t if m["role"] == "assistant")
            o = self.notes_for(j, user, answer, sample_idx) if j < n_old else None
            for m in t:
                m = dict(m)
                if o is not None and m["role"] == "user":
                    blocks = list(DOC_BLOCK_RE.finditer(m["content"]))
                    first = blocks[0]
                    # 블록이 여럿이면 첫 블록 자리에 메모, 나머지 블록은 지운다 (메모가 모든 블록을 합쳐 뽑은 것)
                    content = m["content"]
                    for b in reversed(blocks[1:]):
                        content = content[:b.start()] + content[b.end():]
                    content = (content[:first.start()] + first.group(1) + notes_block(j, o.text) + first.group(3)
                               + content[first.end():])
                    m["content"] = content
                out.append(m)
            if o is not None:
                replaced.append(j)
        return HistoryResult(messages=out, info={"notes_turns_replaced": replaced})

    def config(self):
        return {"name": self.name, "keep_recent": self.keep_recent, "extractor": self.extractor.config()}
