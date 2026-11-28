"""후보 2 query_select_hybrid 측정 + 기존 query_select(BM25) 기준선.

점수 = minmax(BM25) + minmax(cos(bge-m3)). 질의 = 현재 질문 + 직전 n 턴 사용자 질문 (BM25·임베딩 모두).
조각 = 기존 query_select 의 _units_of_turn (문장·코드·Q/A). 같은 조각 텍스트는 한 번만 임베딩 (캐시).
최근 1턴 원문 유지, 예산 B = r x 원본 기록 토큰 (기존 select_history 와 같은 그리디 채우기).

python docs/experiments/feasibility/hybrid.py
"""
from __future__ import annotations

import json
import math
import time

import requests

from common import (OUT, RATIOS, SAMPLES, check_turns, count_tokens, evidence_checks, history_and_current,
                    history_tokens, load_scenario, prev_questions, question_of, split_turns, text_of)
from compressors.question_preserve import bm25
from config import CFG
from multiturn.history_compressors.budget import _units_of_turn, render_selected, select_history

EMB: dict[str, list[float]] = {}
EMB_STATS = {"calls": 0, "texts": 0, "tokens": 0, "seconds": 0.0}
BASE = CFG.embed_base_url


def embed_many(texts: list[str], batch=32):
    new = [t for t in dict.fromkeys(texts) if t not in EMB]
    for i in range(0, len(new), batch):
        chunk = new[i:i + batch]
        t0 = time.perf_counter()
        r = requests.post(f"{BASE}/api/embed", json={"model": CFG.embed_model, "input": chunk, "truncate": False,
                                                     "options": {"num_ctx": CFG.embed_ctx}}, timeout=600)
        r.raise_for_status()
        EMB_STATS["seconds"] += time.perf_counter() - t0
        EMB_STATS["calls"] += 1
        EMB_STATS["texts"] += len(chunk)
        EMB_STATS["tokens"] += sum(count_tokens(c) for c in chunk)
        for c, v in zip(chunk, r.json()["embeddings"]):
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            EMB[c] = [x / n for x in v]
    return [EMB[t] for t in texts]


def minmax(xs):
    lo, hi = min(xs), max(xs)
    return [0.0 if hi == lo else (x - lo) / (hi - lo) for x in xs]


def select_hybrid(query: str, past, budget, keep_recent=1, w_emb=1.0):
    turns = split_turns(past)
    recent = turns[len(turns) - keep_recent:] if keep_recent else []
    older = turns[:len(turns) - len(recent)]
    recent_msgs = [m for t in recent for m in t]
    remaining = budget - history_tokens(recent_msgs, count_tokens)
    cands = [u for i, t in enumerate(older) for u in _units_of_turn(i, t)]
    if not cands or remaining <= 0:
        return recent_msgs, 0.0
    text, spans, pos = "", [], 0
    for u in cands:
        spans.append((pos, pos + len(u["text"]), u["kind"]))
        text += u["text"] + "\n"
        pos = len(text)
    b = bm25(query, text, spans)
    t0 = time.perf_counter()
    vecs = embed_many([u["text"] for u in cands])
    qv = embed_many([query])[0]
    emb_s = time.perf_counter() - t0
    cos = [sum(a * c for a, c in zip(qv, v)) for v in vecs]
    score = [x + w_emb * y for x, y in zip(minmax(b), minmax(cos))]
    ranked = sorted(range(len(cands)), key=lambda i: (-score[i], i))
    chosen = []
    for i in ranked:
        trial = chosen + [cands[i]]
        if count_tokens(render_selected(trial)) <= remaining:
            chosen = trial
    if not chosen:
        return recent_msgs, emb_s
    return [{"role": "user", "content": render_selected(chosen)}] + recent_msgs, emb_s


def main():
    rows = []
    for sid in SAMPLES:
        scn = load_scenario(sid)
        for k in check_turns(scn):
            past, cur = history_and_current(scn, k)
            raw = text_of(past)
            n = history_tokens(past, count_tokens)
            q = question_of(cur)
            for r in RATIOS:
                B = int(n * r)
                variants = {}
                t0 = time.perf_counter()
                variants["query_select"] = (select_history(q, past, B, count_tokens)[0], 0.0)
                bm_s = time.perf_counter() - t0
                for nprev in (0, 1, 2):
                    qq = " ".join(prev_questions(scn, k, nprev) + [q])
                    variants[f"hybrid_q{nprev}"] = select_hybrid(qq, past, B)
                for name, (msgs, emb_s) in variants.items():
                    comp = text_of(msgs)
                    rows.append({"scenario": sid, "turn": k, "turn_type": scn["turns"][k]["turn_type"], "ratio": r,
                                 "method": name, "hist_tokens": n, "budget": B,
                                 "comp_tokens": history_tokens(msgs, count_tokens),
                                 "embed_seconds": round(emb_s, 3), "bm25_select_seconds": round(bm_s, 3),
                                 "checks": evidence_checks(scn, k, raw, comp)})
                print(sid, k, r, "done", flush=True)
    (OUT / "hybrid_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "hybrid_embed_stats.json").write_text(json.dumps({**EMB_STATS, "unique_texts": len(EMB)}, indent=1))
    print(EMB_STATS, len(EMB))


if __name__ == "__main__":
    main()
