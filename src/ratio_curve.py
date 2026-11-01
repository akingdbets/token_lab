"""
LLMLingua-2 압축률 – 손실 곡선 (답변·채점 API 호출 없음)

retain_ratio r 을 바꿔 가며 같은 문맥을 압축하고, 압축 결과만으로 재는 지표를 r 별·유형별로 모은다.
답변 정확도는 재지 않는다 (API 비용이 드는 본실험의 몫).

    EVAL_DIR=data/evalsets/claude-v1 TOKENIZER=tiktoken:o200k_base \\
        python src/ratio_curve.py --split dev --ratios 0.9,0.8,0.7,0.6,0.5,0.4,0.3,0.2 --semantic

지표 (정의는 experiment.py 와 같다)
    reduction_pct        문맥 토큰 합의 절감률. 본실험 run 과 비교하려면 TOKENIZER 를 run 과 맞춘다
    semantic_loss        max(1 − 원문·압축 임베딩 코사인, 1 − 핵심 엔티티 보존율). --semantic 일 때만 (로컬 임베딩)
    within_5pct          semantic_loss <= 0.05 인 문항 비율 (과제 목표: 의미 손실 5% 이하)
    entity_retention     핵심 엔티티 보존율
    evidence_retention   근거 인용문 보존율 (evidence_retention.py)
    answer_core_rate     압축 문맥에 정답 핵심어가 남은 문항 비율 (experiment.answer_core_in_context)
    code_ceiling_pct     코드 블록을 통째로 보존할 때의 절감률 상한 = 100 × (1 − 코드 블록 토큰 / 문맥 토큰)
    fallback             압축 결과를 버리고 원문을 쓴 문항 수
결과: results/curves/<시각>/rows.jsonl (문항 × r) 과 summary.json, 표 출력.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compressors import PromptParts
from compressors.llmlingua2 import LLMLingua2Compressor, _split_fenced_blocks
from config import CFG
from corpus import load_corpus
from evidence_retention import item_retention
from experiment import (answer_core_in_context, build_context, cosine, embed_long, entity_retention,
                        git_head, load_items)
from grader import word_tokens
from llm import LLM, count_tokens


def code_tokens(context: str) -> int:
    return sum(count_tokens(chunk) for is_code, chunk in _split_fenced_blocks(context) if is_code)


def measure(item: dict, raw: str, raw_tokens: int, raw_emb, comp: LLMLingua2Compressor, embedder) -> dict:
    quotes = tuple(e["quote"] for e in item.get("evidence") or [] if e.get("quote"))
    started = time.perf_counter()
    res = comp.compress(PromptParts(system="", context=raw, question=item["question"], evidence=quotes))
    ctx = res.context
    ctx_tokens = count_tokens(ctx)
    ent = entity_retention(item.get("key_entities", []), word_tokens(ctx))
    sim = None
    if embedder is not None:
        sim = 1.0 if ctx == raw else round(cosine(raw_emb, embed_long(embedder, ctx)[0]), 4)
    ev = item_retention(ctx, list(quotes))
    return {
        "qid": item["id"], "qtype": item["type"], "ratio": comp.retain_ratio,
        "status": res.info.get("status"), "compress_sec": round(time.perf_counter() - started, 3),
        "ctx_tokens_raw": raw_tokens, "ctx_tokens": ctx_tokens,
        "reduction_pct": round(100 * (1 - ctx_tokens / raw_tokens), 2) if raw_tokens else 0.0,
        "entity_retention": ent, "semantic_sim": sim,
        "semantic_loss": round(max(1 - sim, 1 - ent), 4) if sim is not None and ent is not None else None,
        "evidence_retention": ev["retention"] if ev else None,
        "answer_core": answer_core_in_context(ctx, item),
    }


def aggregate(rows: list[dict]) -> dict:
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None

    raw = sum(r["ctx_tokens_raw"] for r in rows)
    losses = [r["semantic_loss"] for r in rows if r["semantic_loss"] is not None]
    return {
        "n": len(rows),
        "reduction_pct": round(100 * (1 - sum(r["ctx_tokens"] for r in rows) / raw), 2) if raw else None,
        "semantic_loss": mean(losses),
        "within_5pct": round(sum(x <= 0.05 for x in losses) / len(losses), 4) if losses else None,
        "entity_retention": mean(r["entity_retention"] for r in rows),
        "evidence_retention": mean(r["evidence_retention"] for r in rows),
        "answer_core_rate": mean(float(r["answer_core"]) for r in rows),
        "fallback": sum(1 for r in rows if (r["status"] or "").startswith("fallback")),
    }


def main():
    ap = argparse.ArgumentParser(description="LLMLingua-2 압축률 – 손실 곡선 (압축만, 답변 없음)")
    ap.add_argument("--split", default="dev", help="dev | test | all")
    ap.add_argument("--ids", help="문항 번호 (쉼표 구분)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ratios", default="0.9,0.8,0.7,0.6,0.5,0.4,0.3,0.2", help="retain_ratio 목록")
    ap.add_argument("--semantic", action="store_true", help="의미 손실도 계산 (임베딩 모델 필요)")
    ap.add_argument("--out", type=Path, help="결과 폴더 (기본: results/curves/<시각>)")
    args = ap.parse_args()

    ratios = [float(x) for x in args.ratios.split(",") if x.strip()]
    items = load_items(args.split, args.limit, args.ids.split(",") if args.ids else None)
    if not items:
        sys.exit(f"문항이 없습니다 (split={args.split})")
    out = args.out or CFG.results_dir / "curves" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    corpus = load_corpus()
    embedder = LLM(role="embed") if args.semantic else None
    comps = [LLMLingua2Compressor(retain_ratio=r) for r in ratios]
    print(f"문항 {len(items)}개 x r {ratios}  tokenizer={CFG.tokenizer}  semantic={args.semantic}  ->  {out.as_posix()}",
          flush=True)

    rows, ceiling_raw, ceiling_code = [], 0, 0
    with open(out / "rows.jsonl", "w", encoding="utf-8") as f:
        for i, item in enumerate(items, 1):
            raw = build_context(corpus, item)
            raw_tokens = count_tokens(raw)
            ceiling_raw += raw_tokens
            ceiling_code += code_tokens(raw)
            raw_emb = embed_long(embedder, raw)[0] if embedder else None
            for comp in comps:
                row = measure(item, raw, raw_tokens, raw_emb, comp, embedder)
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
            print(f"  [{i}/{len(items)}] {item['id']}", flush=True)

    summary = {
        "time": datetime.now().isoformat(timespec="seconds"), "git_head": git_head(),
        "eval_dir": CFG.eval_dir.as_posix(), "split": args.split, "n_items": len(items),
        "tokenizer": CFG.tokenizer, "semantic": args.semantic,
        "embed_model": CFG.embed_model if args.semantic else None,
        "compressor": {k: v for k, v in comps[0].config().items() if k != "retain_ratio"},
        "code_ceiling_pct": round(100 * (1 - ceiling_code / ceiling_raw), 2) if ceiling_raw else None,
        "by_ratio": {}, "by_type": {},
    }
    for r in ratios:
        rs = [x for x in rows if x["ratio"] == r]
        summary["by_ratio"][str(r)] = aggregate(rs)
        for t in dict.fromkeys(x["qtype"] for x in rs):
            summary["by_type"].setdefault(t, {})[str(r)] = aggregate([x for x in rs if x["qtype"] == t])
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    def fmt(x, p=3):
        return "-" if x is None else f"{x:.{p}f}"

    print(f"\n코드 블록 보존 시 절감률 상한: {summary['code_ceiling_pct']}%")
    print(f"{'r':>5}{'절감%':>8}{'의미손실':>9}{'≤5%':>7}{'엔티티':>8}{'근거':>7}{'정답핵심어':>9}{'대체':>5}")
    for r, s in summary["by_ratio"].items():
        print(f"{r:>5}{fmt(s['reduction_pct'], 1):>8}{fmt(s['semantic_loss']):>9}{fmt(s['within_5pct'], 2):>7}"
              f"{fmt(s['entity_retention']):>8}{fmt(s['evidence_retention']):>7}{fmt(s['answer_core_rate'], 2):>9}"
              f"{s['fallback']:>5}")
    print(f"\n유형별 절감% / 근거 보존율")
    for t, by in summary["by_type"].items():
        print(f"  {t:<10}" + "  ".join(f"r{r}: {fmt(s['reduction_pct'], 1)}/{fmt(s['evidence_retention'], 2)}"
                                       for r, s in by.items()))
    print(f"\n저장: {out.as_posix()} (rows.jsonl, summary.json)")


if __name__ == "__main__":
    main()
