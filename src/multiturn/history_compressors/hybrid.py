"""
query_select_hybrid: 현재 질문으로 과거 조각을 BM25 + 임베딩(bge-m3) 코사인 유사도를 합친 점수로 고른다.

query_select(budget.py) 와 같은 규칙
    - 예산: 절대 토큰 또는 비율(r=0.5: 그 턴 원본 과거 기록의 50%)
    - 최근 keep_recent 턴은 원문으로 남기고, 나머지 턴의 조각(_units_of_turn: 문장·코드·Q/A)을 점수 순으로 예산까지 고른다
    - 고른 조각은 원래 순서대로 <selected_history> 메시지 하나에 넣는다 (어느 턴에서 왔는지 표시)
    - 받는 것: 현재 질문, 과거 기록, 예산, 토큰 카운터. 정답·key_facts·evidence·turn_type·depends_on 은 받지 않는다
다른 점
    - 점수 = w_bm25 × minmax(BM25) + w_emb × minmax(cos(질문, 조각)). 기본 0.5 : 0.5 (--hybrid-bm25-weight)
    - query_select 는 BM25 점수가 0 보다 큰 조각만 후보로 둔다. hybrid 는 모든 조각이 후보다 (임베딩 점수가 있으므로)
    - 질의 = 현재 질문만 (직전 질문을 붙이는 변형은 측정에서 근거가 줄어 넣지 않는다, scratch/feasibility/REPORT.md)

임베딩
    OllamaEmbedder: Ollama /api/embed (CFG.embed_base_url, CFG.embed_model = bge-m3). 단위 벡터로 정규화해 둔다.
    같은 (모델, 텍스트) 는 한 번만 계산한다: 메모리 캐시 + 디스크 캐시(results/cache/embeddings.sqlite, --resume 때도 재사용).
    sample 이 달라도 기록이 같으면 같은 결과다 (결정적).
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from pathlib import Path

from multiturn.history_compressors.base import HistoryResult, split_turns
from multiturn.history_compressors.budget import (
    BudgetCompressor, _ratio_extra, _units_of_turn, budget_info, history_tokens, question_of, render_selected,
)


class EmbeddingError(RuntimeError):
    """임베딩 서버 호출 실패. 원문이나 BM25 만으로 대체하지 않는다."""


class OllamaEmbedder:
    """bge-m3 임베딩 (Ollama). embed_many 는 단위 벡터 목록을 돌려준다. 스레드 안전."""

    def __init__(self, base_url: str | None = None, model: str | None = None, ctx: int | None = None,
                 cache_path: str | Path | None = None, batch: int = 32, timeout: int = 600):
        from config import CFG
        self.base_url = (base_url or CFG.embed_base_url).rstrip("/")
        self.model = model or CFG.embed_model
        self.ctx = ctx or CFG.embed_ctx
        self.batch, self.timeout = batch, timeout
        self.cache_path = Path(cache_path) if cache_path else CFG.results_dir / "cache" / "embeddings.sqlite"
        self._mem: dict[str, list[float]] = {}
        self._lock = threading.Lock()          # 캐시·디스크 쓰기
        self._call_lock = threading.Lock()     # 서버 호출은 한 번에 하나 (CPU 임베딩이라 동시 호출해도 빨라지지 않음)
        self.stats = {"calls": 0, "texts_embedded": 0, "disk_hits": 0}
        self._db_conn = None

    def _db(self):
        if self._db_conn is None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_conn = sqlite3.connect(self.cache_path, timeout=30, check_same_thread=False)
            self._db_conn.execute("CREATE TABLE IF NOT EXISTS emb (key TEXT PRIMARY KEY, model TEXT, vec TEXT NOT NULL)")
            self._db_conn.commit()
        return self._db_conn

    def _key(self, text: str) -> str:
        return hashlib.sha256(json.dumps([self.model, text], ensure_ascii=False).encode("utf-8")).hexdigest()

    def _request(self, texts: list[str]) -> list[list[float]]:
        """연결 오류·HTTP 오류는 requests 예외 그대로 올린다 (replay 의 with_backoff 가 다시 부른다)."""
        import requests
        r = requests.post(f"{self.base_url}/api/embed",
                          json={"model": self.model, "input": texts, "truncate": False,
                                "options": {"num_ctx": self.ctx}}, timeout=self.timeout)
        r.raise_for_status()
        vecs = r.json().get("embeddings")
        if not isinstance(vecs, list) or len(vecs) != len(texts):
            raise EmbeddingError(f"임베딩 응답 형식이 다릅니다 ({self.base_url}, {self.model}): {len(vecs or [])}/{len(texts)}")
        return vecs

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            missing = [t for t in dict.fromkeys(texts) if t not in self._mem]
            if missing:
                db = self._db()
                for t in missing:
                    row = db.execute("SELECT vec FROM emb WHERE key = ?", (self._key(t),)).fetchone()
                    if row:
                        self._mem[t] = json.loads(row[0])
                        self.stats["disk_hits"] += 1
            todo = [t for t in dict.fromkeys(texts) if t not in self._mem]
        for i in range(0, len(todo), self.batch):
            chunk = todo[i:i + self.batch]
            with self._call_lock:
                chunk = [t for t in chunk if t not in self._mem]        # 기다리는 동안 다른 스레드가 만들었을 수 있다
                if not chunk:
                    continue
                vecs = self._request(chunk)
                self.stats["calls"] += 1
                self.stats["texts_embedded"] += len(chunk)
            with self._lock:
                db = self._db()
                for t, v in zip(chunk, vecs):
                    n = math.sqrt(sum(x * x for x in v)) or 1.0
                    unit = [x / n for x in v]
                    self._mem[t] = unit
                    db.execute("INSERT OR IGNORE INTO emb VALUES (?, ?, ?)", (self._key(t), self.model, json.dumps(unit)))
                db.commit()
        return [self._mem[t] for t in texts]

    def config(self) -> dict:
        return {"backend": "ollama", "base_url": self.base_url, "model": self.model, "ctx": self.ctx,
                "cache": str(self.cache_path)}


def minmax(xs: list[float]) -> list[float]:
    lo, hi = min(xs), max(xs)
    return [0.0 if hi == lo else (x - lo) / (hi - lo) for x in xs]


def select_hybrid(question: str, past: list[dict], budget: int, token_counter, embedder, keep_recent: int = 1,
                  w_bm25: float = 0.5) -> tuple[list[dict], dict]:
    """현재 질문과 과거 기록·예산·토큰 카운터·임베더만 받아 기록을 고른다 (정답·key_facts 를 받지 않음)."""
    from compressors.question_preserve import bm25

    w_emb = 1.0 - w_bm25
    turns = split_turns(past)
    recent = turns[len(turns) - keep_recent:] if keep_recent else []
    older = turns[:len(turns) - len(recent)]
    recent_msgs = [m for t in recent for m in t]
    remaining = budget - history_tokens(recent_msgs, token_counter)
    cands = [u for i, t in enumerate(older) for u in _units_of_turn(i, t)]
    info = {"candidates": len(cands), "selected": 0, "hybrid_bm25_weight": w_bm25}
    if not cands or remaining <= 0:
        return recent_msgs, info
    text, spans, pos = "", [], 0
    for u in cands:
        spans.append((pos, pos + len(u["text"]), u["kind"]))
        text += u["text"] + "\n"
        pos = len(text)
    b = bm25(question, text, spans)
    vecs = embedder.embed_many([u["text"] for u in cands] + [question])
    qv, uv = vecs[-1], vecs[:-1]
    cos = [sum(a * c for a, c in zip(qv, v)) for v in uv]
    score = [w_bm25 * x + w_emb * y for x, y in zip(minmax(b), minmax(cos))]
    ranked = sorted(range(len(cands)), key=lambda i: (-score[i], i))
    chosen: list[dict] = []
    for i in ranked:
        trial = chosen + [cands[i]]
        if token_counter(render_selected(trial)) <= remaining:
            chosen = trial
    info["selected"] = len(chosen)
    if not chosen:
        return recent_msgs, info
    # render_selected 는 조각을 원래 순서(턴, 위치)대로 놓는다
    return [{"role": "user", "content": render_selected(chosen)}] + recent_msgs, info


class QuerySelectHybrid(BudgetCompressor):
    family = "query_select_hybrid"

    def __init__(self, budget=None, keep_recent: int = 1, token_counter=None, ratio=None, embedder=None,
                 bm25_weight: float = 0.5):
        super().__init__(budget, keep_recent, token_counter, ratio=ratio)
        if not 0.0 <= bm25_weight <= 1.0:
            raise ValueError("hybrid_bm25_weight 는 0 이상 1 이하")
        self.embedder = embedder if embedder is not None else OllamaEmbedder()
        self.bm25_weight = bm25_weight

    def config(self):
        cfg = getattr(self.embedder, "config", None)
        return {**super().config(), "bm25_weight": self.bm25_weight, "embedding_weight": round(1 - self.bm25_weight, 6),
                "embedder": cfg() if callable(cfg) else None}

    def compress_past(self, past, current_user, budget_tokens, state):
        budget = self.effective_budget(past)
        msgs, sel = select_hybrid(question_of(current_user), past, budget, self.count, self.embedder,
                                  self.keep_recent, self.bm25_weight)
        return HistoryResult(messages=msgs, info=budget_info(msgs, budget, self.count, **sel, **_ratio_extra(self, budget)))
