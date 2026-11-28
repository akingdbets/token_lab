"""후보 1 LongLLMLingua (rank_method="longllmlingua") 측정.

멀티턴 적용(가정): 매 턴 현재 질문으로 과거 기록 전체를 다시 압축. 최근 1턴은 원문 유지 (query_select 와 같게).
문맥 단위 = 오래된 턴의 사용자 질문, 문서 페이지(## Document: 단위), assistant 답변 (원래 순서 유지, reorder 안 함).
예산 = r x 원본 기록 토큰 (압축 모델 토크나이저 기준) - 최근 턴 토큰.

python docs/experiments/feasibility/longlingua.py --model Qwen/Qwen2.5-0.5B --mode timing
python docs/experiments/feasibility/longlingua.py --model Qwen/Qwen2.5-0.5B --mode quality
"""
from __future__ import annotations

import argparse
import json
import re
import time

from common import (OUT, RATIOS, SAMPLES, PeakRSS, check_turns, evidence_checks, gb, history_and_current,
                    history_tokens, count_tokens, load_scenario, question_of, split_turns, text_of)

TIMING_POINTS = [("v2_01_auth_switch", 11), ("v2_02_response_design", 17)]   # 기록 약 1.1만 / 2.1만 토큰


class KVCompat:
    """llmlingua 0.2.2 는 past_key_values 를 [(k, v), ...] 로 다룬다. transformers 5 는 Cache 객체만 쓰므로
    모델 호출 앞뒤에서 형식을 바꿔 준다 (설치된 llmlingua 는 고치지 않는다)."""

    def __init__(self, model):
        self.__dict__["m"] = model

    def __getattr__(self, n):
        return getattr(self.m, n)

    def __call__(self, *a, past_key_values=None, **kw):
        from transformers import Cache, DynamicCache
        if past_key_values is not None and not isinstance(past_key_values, Cache):
            past_key_values = DynamicCache(ddp_cache_data=[(k, v) for k, v in past_key_values])
        out = self.m(*a, past_key_values=past_key_values, **kw)
        pkv = out.past_key_values
        if pkv is not None and isinstance(pkv, Cache):
            out.past_key_values = [(layer.keys, layer.values) for layer in pkv.layers]
        return out


def contexts_of(older_msgs):
    out = []
    for m in older_msgs:
        if m["role"] == "user" and "## Document:" in m["content"]:
            parts = re.split(r"(?=^## Document: )", m["content"], flags=re.M)
            out.extend(p for p in parts if p.strip())
        else:
            out.append(m["content"])
    return out


def compress(pc, past, question, r, keep_recent=1):
    turns = split_turns(past)
    recent = turns[len(turns) - keep_recent:]
    older = [m for t in turns[:len(turns) - keep_recent] for m in t]
    recent_msgs = [m for t in recent for m in t]
    tok = lambda s: len(pc.tokenizer.encode(s, add_special_tokens=False))
    total = sum(tok(m["content"]) for m in past)
    target = int(total * r) - sum(tok(m["content"]) for m in recent_msgs)
    ctxs = contexts_of(older)
    if target <= 0 or not ctxs:
        return recent_msgs, {"target": target, "skipped": True}
    res = pc.compress_prompt(ctxs, instruction="", question=question, target_token=target,
                             rank_method="longllmlingua", condition_in_question="after_condition",
                             reorder_context="original", dynamic_context_compression_ratio=0.3,
                             condition_compare=True, context_budget="+100", concate_question=False,
                             use_sentence_level_filter=False)
    msgs = [{"role": "user", "content": "<compressed_history>\n" + res["compressed_prompt"] + "\n</compressed_history>"}]
    return msgs + recent_msgs, {"target": target, "contexts": len(ctxs), "origin_tokens_model": res.get("origin_tokens"),
                                "compressed_tokens_model": res.get("compressed_tokens")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=["timing", "quality"], required=True)
    ap.add_argument("--ratios", default="0.25,0.5,0.75")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--types", default="recall,synthesis")
    ap.add_argument("--max-points", type=int, default=0)
    ap.add_argument("--dtype", default="float32", choices=["float32", "bfloat16"])
    a = ap.parse_args()
    import torch
    if a.threads:
        torch.set_num_threads(a.threads)
    from llmlingua import PromptCompressor
    tag = a.model.split("/")[-1] + ("" if a.dtype == "float32" else "_" + a.dtype)
    with PeakRSS() as mem:
        base = mem.peak
        t0 = time.perf_counter()
        pc = PromptCompressor(model_name=a.model, device_map="cpu", model_config={"dtype": getattr(torch, a.dtype)})
        pc.model = KVCompat(pc.model)
        load_s = time.perf_counter() - t0
        after_load = mem.peak
        ratios = [float(x) for x in a.ratios.split(",")]
        rows = []
        if a.mode == "timing":
            points = [(sid, k, r) for sid, k in TIMING_POINTS for r in ratios]
        else:
            types = a.types.split(",")
            points = [(sid, t["turn"], r) for sid in SAMPLES for t in load_scenario(sid)["turns"] if t["turn_type"] in types for r in ratios]
        for sid, k, r in (points[:a.max_points] if a.max_points else points):
            scn = load_scenario(sid)
            past, cur = history_and_current(scn, k)
            mem.reset()
            t0 = time.perf_counter()
            msgs, info = compress(pc, past, question_of(cur), r)
            sec = time.perf_counter() - t0
            comp = text_of(msgs)
            row = {"model": a.model, "scenario": sid, "turn": k, "turn_type": scn["turns"][k]["turn_type"], "ratio": r,
                   "hist_tokens": history_tokens(past, count_tokens), "comp_tokens": history_tokens(msgs, count_tokens),
                   "seconds": round(sec, 2), "peak_rss_gb": gb(mem.peak), **info,
                   "checks": evidence_checks(scn, k, text_of(past), comp)}
            rows.append(row)
            print(json.dumps({x: row[x] for x in ("scenario", "turn", "ratio", "hist_tokens", "comp_tokens", "seconds", "peak_rss_gb")}), flush=True)
            (OUT / f"ll_{a.mode}_{tag}.json").write_text(json.dumps(
                {"model": a.model, "dtype": a.dtype, "load_seconds": round(load_s, 1), "rss_before_gb": gb(base),
                 "rss_after_load_gb": gb(after_load), "threads": torch.get_num_threads(), "rows": rows},
                ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
