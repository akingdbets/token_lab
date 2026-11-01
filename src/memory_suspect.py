"""
기억 의존 의심(memory_suspect)을 두 축으로 소급 분류 (API 호출 없음)

저장된 압축 문맥(contexts/<qid>.<압축기>.md)과 평가셋으로 trial 마다 두 가지를 본다.
    1. 정답 핵심어가 압축 문맥에 있는가   experiment.answer_core_in_context (CORE_MATCH_VERSION)
    2. 근거 인용문이 얼마나 남았는가      evidence_retention.item_retention

    EVAL_DIR=data/evalsets/claude-v1 python src/memory_suspect.py results/runs/<run_id> [<run_id2> ...]

분류 (위에서부터 먼저 걸리는 것)
    unmeasurable     압축 없는 원문(none 문맥)에서도 정답 핵심어가 안 잡힘. 정답을 문장으로 바꿔 쓴 문항이라 이 지표로 못 잰다
    not_correct      answer_accuracy < 0.5 (또는 없음). 의심 대상이 아니다
    core_present     압축 문맥에 정답 핵심어가 있다 (표기만 바뀐 것 포함)
    evidence_kept    핵심어는 없지만 근거 보존율 >= EVIDENCE_LOW (표현만 바뀌었을 가능성)
    evidence_low     EVIDENCE_ABSENT <= 근거 보존율 < EVIDENCE_LOW
    evidence_absent  근거 보존율 < EVIDENCE_ABSENT
memory_suspect (헤드라인) = evidence_absent. 강한 주장이라 오판이 적은 쪽으로 잡는다
memory_suspect_sensitive (민감도) = evidence_absent + evidence_low
경계값: none 은 174문항 모두 근거 보존율 0.9 이상, 근거 줄을 지운 drop_evidence 는 0~0.9 에 넓게 퍼지고 중앙값이 0.25 다
(비슷한 문장·코드가 문맥 다른 곳에 남아 단어 단위 부분 점수를 받는다). 둘 사이에 빈 구간이 없어 drop_evidence 중앙값을
"근거 없음"으로, 근거 보존율 스크립트 기본값 0.5 를 민감도 경계로 둔다.
결과: 압축기별 표를 출력하고 첫 run 폴더에 memory_suspect_v2.json 을 쓴다 (trials.jsonl 과 기존 memory_suspect.json 은 그대로).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_retention import item_retention
from experiment import CORE_MATCH_VERSION, answer_core_in_context_strict, core_matches, load_items

EVIDENCE_ABSENT = 0.25
EVIDENCE_LOW = 0.5
LABELS = ("unmeasurable", "not_correct", "core_present", "evidence_kept", "evidence_low", "evidence_absent")


def classify(item: dict, context: str, raw_context: str, answer_accuracy: float | None) -> dict:
    """trial 하나의 두 축 분류. raw_context 는 압축 전 원문(none 문맥)."""
    core, found = core_matches(context, item)
    measurable = core_matches(raw_context, item)[0]
    quotes = [e["quote"] for e in item.get("evidence") or [] if e.get("quote")]
    ev = item_retention(context, quotes)
    evidence = ev["retention"] if ev else None
    if not measurable:
        label = "unmeasurable"
    elif answer_accuracy is None or answer_accuracy < 0.5:
        label = "not_correct"
    elif core:
        label = "core_present"
    elif evidence is None or evidence >= EVIDENCE_LOW:
        label = "evidence_kept"
    elif evidence >= EVIDENCE_ABSENT:
        label = "evidence_low"
    else:
        label = "evidence_absent"
    return {"label": label, "measurable": measurable, "core": core, "found": found, "evidence": evidence,
            "memory_suspect": label == "evidence_absent",
            "memory_suspect_sensitive": label in ("evidence_absent", "evidence_low")}


def main():
    ap = argparse.ArgumentParser(description="기존 run 에 memory_suspect 두 축 분류 소급")
    ap.add_argument("run_dirs", nargs="+", type=Path, help="results/runs/<run_id> (여러 개면 합친다)")
    args = ap.parse_args()

    items = {it["id"]: it for it in load_items("all", None, None)}
    rows = []
    for run in args.run_dirs:
        for line in (run / "trials.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            t = json.loads(line)
            ctx_file = run / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md"
            raw_file = run / "contexts" / f"{t['qid']}.none.md"
            for f in (ctx_file, raw_file):
                if not f.exists():
                    sys.exit(f"문맥 파일이 없습니다: {f}")
            item, ctx = items[t["qid"]], ctx_file.read_text(encoding="utf-8")
            r = classify(item, ctx, raw_file.read_text(encoding="utf-8"), t.get("answer_accuracy"))
            strict = answer_core_in_context_strict(ctx, item)
            rows.append({"run_id": t["run_id"], "qid": t["qid"], "qtype": t["qtype"], "compressor": t["compressor"],
                         "answer_accuracy": t.get("answer_accuracy"), **r,
                         "memory_suspect_strict": not strict and (t.get("answer_accuracy") or 0) >= 0.5,
                         "response": (t.get("response") or "").strip()[:120]})

    summary = {}
    for comp in dict.fromkeys(r["compressor"] for r in rows):
        rs = [r for r in rows if r["compressor"] == comp]
        s = {"n": len(rs), "measurable": sum(r["measurable"] for r in rs)}
        s.update({k: sum(r["label"] == k for r in rs) for k in LABELS})
        s["memory_suspect"] = s["evidence_absent"]
        s["memory_suspect_sensitive"] = s["evidence_absent"] + s["evidence_low"]
        s["memory_suspect_strict"] = sum(r["memory_suspect_strict"] for r in rs)
        summary[comp] = s
    out = {"runs": [r.as_posix() for r in args.run_dirs], "core_match_version": CORE_MATCH_VERSION,
           "evidence_absent": EVIDENCE_ABSENT, "evidence_low": EVIDENCE_LOW, "summary": summary,
           "items": [r for r in rows if r["label"] not in ("core_present", "not_correct") or r["memory_suspect_strict"]]}
    path = args.run_dirs[0] / "memory_suspect_v2.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"## {', '.join(r.name for r in args.run_dirs)}  ({CORE_MATCH_VERSION}, 근거 없음 < {EVIDENCE_ABSENT}, "
          f"낮음 < {EVIDENCE_LOW})\n")
    print("| 압축기 | n | 측정 가능 | 핵심어 있음 | 근거 남음 | 근거 낮음 | 근거 없음 (헤드라인) | 민감도 (<0.5) | 이전 방식 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for comp, s in summary.items():
        print(f"| {comp} | {s['n']} | {s['measurable']} | {s['core_present']} | {s['evidence_kept']} | {s['evidence_low']} "
              f"| {s['memory_suspect']} | {s['memory_suspect_sensitive']} | {s['memory_suspect_strict']} |")
    flagged = [r for r in rows if r["label"] in ("evidence_low", "evidence_absent")]
    if flagged:
        print("\n| qid | 압축기 | 분류 | 근거 보존율 | 답변 |\n|---|---|---|---|---|")
        for r in flagged:
            print(f"| {r['qid']} | {r['compressor']} | {r['label']} | {r['evidence']} | "
                  f"{r['response'][:60].replace('|', '/')} |")
    print(f"\n저장: {path.as_posix()}")


if __name__ == "__main__":
    main()
