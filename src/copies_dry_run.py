"""
정답 사본 지우기 조건의 dry-run (API 호출 없음, C1 중복성 검증 준비)

압축기만 로컬로 적용해 문항마다 지운 토큰 수, 사본 검증 통과 여부, 상한 초과 여부, 조건별 유효 문항을 본다.
정확도는 보지 않으므로 이 결과로 상한을 정해도 사전 고정 원칙에 어긋나지 않는다.

    EVAL_DIR=data/evalsets/claude-v1 python src/copies_dry_run.py --split dev
    EVAL_DIR=data/evalsets/claude-v1 python src/copies_dry_run.py --split test --cap 0.4

본 분석 문항 (코드로 고정, select_items)
    type 이 fact 또는 code 이고, 압축 없는 원문에서 정답 핵심어가 잡히는 문항 (core_match.core_matches, 측정 가능)
문항 제외
    drop_all_copies 가 지운 토큰이 원문 문맥의 --cap 을 넘으면 그 문항은 모든 조건에서 뺀다
    조건별로 defined=False 나 verified=False 인 문항은 그 조건에서만 뺀다 (keep_* 는 남길 사본이 없을 수 있다)
중복도: redundancy.core_positions 와 같은 값 (none 문맥의 정답 핵심어 위치 수, 괄호는 근거 자리 밖만 센 값).
    사본 단위(copy_units)는 압축기가 지우는 단위 수라, 한 문장·코드 블록에 정답이 두 번 나오면 위치 2, 단위 1 이다
결과: 표를 출력하고 results/copies_dry_run/<split>.json 에 문항별 info 와 조건별 문항 목록을 쓴다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compressors import get_compressor
from config import CFG
from corpus import load_corpus
from core_match import ANSWER_KINDS, answer_kind
from experiment import build_context, core_matches, core_needles, load_answer_prompt, load_items
from redundancy import core_positions, evidence_words, outside_evidence

MAIN_TYPES = ("fact", "code")
MATCHED = ("matched_random_drop", "matched_random_drop_s2", "matched_random_drop_s3")
CONDITIONS = ("drop_evidence", "drop_all_copies", "keep_code_copy", "keep_prose_copy", "keep_answer_in_place",
              *MATCHED)
CAPS = (0.2, 0.3, 0.4, 0.5)


def select_items(items: list[dict], corpus) -> list[tuple[dict, str]]:
    """본 분석 문항과 그 원문 문맥."""
    out = []
    for it in items:
        if it.get("type") not in MAIN_TYPES:
            continue
        raw = build_context(corpus, it)
        if core_matches(raw, it)[0]:
            out.append((it, raw))
    return out


def main():
    ap = argparse.ArgumentParser(description="정답 사본 지우기 조건 dry-run (API 없음)")
    ap.add_argument("--split", default="dev", choices=("dev", "test", "all"))
    ap.add_argument("--cap", type=float, default=0.3, help="drop_all_copies 가 지운 토큰 비율 상한")
    ap.add_argument("--answer-prompt", default="v1")
    args = ap.parse_args()

    corpus = load_corpus()
    prompt = load_answer_prompt(args.answer_prompt)
    items = load_items(args.split, None, None)
    chosen = select_items(items, corpus)
    rows = []
    for it, raw in chosen:
        parts = prompt.parts(raw, it["question"], it.get("type"),
                             evidence=tuple(e["quote"] for e in it.get("evidence") or [] if e.get("quote")),
                             answer_core=tuple(core_needles(it)))
        row = {"qid": it["id"], "type": it["type"], "answer_kind": answer_kind(it["answer"]),
               "needles": list(parts.answer_core),
               "redundancy": core_positions(raw, it),
               "redundancy_outside": core_positions(raw, it, outside_evidence(raw, raw, evidence_words(raw, it)))}
        for name in CONDITIONS:
            row[name] = get_compressor(name).compress(parts).info
        rows.append(row)

    def frac(r):
        return r["drop_all_copies"].get("dropped_frac") or 0.0

    def ok(r, name):
        info = r[name]
        if name == "drop_evidence":
            return not info.get("unmatched_quotes")
        return bool(info.get("defined")) and bool(info.get("verified"))

    eligible = {name: [r["qid"] for r in rows if frac(r) <= args.cap and ok(r, name)] for name in CONDITIONS}
    out = {"split": args.split, "eval_dir": CFG.eval_dir.as_posix(), "cap": args.cap, "main_types": MAIN_TYPES,
           "n_split": len(items), "n_main": len(rows),
           "over_cap": {str(c): [r["qid"] for r in rows if frac(r) > c] for c in CAPS},
           "eligible": eligible,
           "eligible_by_kind": {name: {k: [r["qid"] for r in rows if r["qid"] in eligible[name] and r["answer_kind"] == k]
                                       for k in ANSWER_KINDS} for name in CONDITIONS},
           "items": rows}
    path = CFG.root / "results" / "copies_dry_run" / f"{args.split}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"## {args.split}: 문항 {len(items)}개 중 본 분석 {len(rows)}개 (type ∈ {MAIN_TYPES}, 측정 가능)\n")
    print("상한별 제외 (drop_all_copies 지운 토큰 비율): "
          + ", ".join(f">{c:.0%} {len(v)}개" for c, v in zip(CAPS, out["over_cap"].values())))
    print("\n| qid | type | 정답 유형 | 중복도 (근거 밖) | 문맥 tok | 근거 단위 | 사본 단위 (코드) | drop_all 지움 | 비율 "
          "| 검증 | keep_code | keep_prose | in_place (남긴 구절) | matched s1/s2/s3 (지움 tok) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        d = r["drop_all_copies"]

        def mark(name):
            i = r[name]
            return "-" if not i.get("defined") else ("ok" if i.get("verified") else "FAIL")

        m = "/".join(f"{mark(n)} {r[n].get('dropped_tokens', '-')}" for n in MATCHED)
        ip = r["keep_answer_in_place"]
        ip = mark("keep_answer_in_place") + (f" `{ip['kept_phrase']}`" if ip.get("kept_phrase") else "")
        print(f"| {r['qid']} | {r['type']} | {r['answer_kind']} "
              f"| {r['redundancy']['total']} ({r['redundancy_outside']['total']}) | {d['context_tokens']} | {d['evidence_units']} "
              f"| {d['copy_units']} ({d['copy_units_code']}) | {d.get('dropped_tokens', '-')} | {frac(r):.0%} "
              f"| {mark('drop_all_copies')} | {mark('keep_code_copy')} | {mark('keep_prose_copy')} | {ip} | {m} |")
    fails = [(r["qid"], n, r[n].get("reason")) for r in rows for n in CONDITIONS[1:]
             if r[n].get("defined") and not r[n].get("verified")]
    if fails:
        print("\n검증 실패")
        for qid, n, reason in fails:
            print(f"- {qid} {n}: {reason}")
    print(f"\n조건별 유효 문항 (상한 {args.cap:.0%})")
    for name, ids in eligible.items():
        by = out["eligible_by_kind"][name]
        print(f"- {name}: {len(ids)}개 (" + ", ".join(f"{k} {len(by[k])}" for k in ANSWER_KINDS) + ")")
    print(f"\n저장: {path.relative_to(CFG.root).as_posix()}")


if __name__ == "__main__":
    main()
