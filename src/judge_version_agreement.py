"""
채점 버전 비교: 사람 라벨 시트(judge_check_test.csv)에서 fact_judge_v2 와 v3 를 같은 judge 로 다시 판정해
사람 라벨 대비 일치율을 비교한다 (per_fact, fact 하나당 judge 호출 1회).

    python src/judge_version_agreement.py docs/results/judge_check_test.csv \\
        --out docs/results/judge_version_agreement_v2_v3.md

- 시트 행에는 accept_alternatives 가 없다. 그래서 v3 는 v2 와 글자 그대로 같은 프롬프트를 보낸다
  (test_fact_judge_v3 로 확인). 이 비교로 확인하는 것은 "대안이 없을 때 v3 가 v2 보다 나쁘지 않은가" 까지다.
  대안 블록이 붙은 판정의 정확도는 이 시트로 잴 수 없다 (multiturn-v2 검수에서 대안 행을 따로 라벨링해야 한다).
- 응답 캐시를 쓰지 않고 v2·v3 를 각각 실제로 호출한다 (같은 프롬프트의 반복 호출 변동도 함께 보인다).
- 결과: 행별 판정 jsonl (--rows) 과 요약 md (--out).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grader import (FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_PROMPT_VERSION, FACT_JUDGE_V3_PROMPT_HASH,
                    FACT_JUDGE_V3_VERSION, _judge_single_fact)

COLS = {"question": "질문", "fact": "핵심 사실", "reference": "참고 정답", "answer": "모델 답변", "human": "human"}


def read_rows(path: Path) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.DictReader(io.StringIO(text)))
    return [r for r in rows if r.get(COLS["human"], "").strip() in ("O", "X")]


def stats(pairs: list[tuple[bool, bool | None]]) -> dict:
    """(human, judge) -> 일치율, FP, FN, kappa. judge None(못 읽음)은 뺀다."""
    ok = [(h, j) for h, j in pairs if j is not None]
    n = len(ok)
    agree = sum(h == j for h, j in ok)
    fp = sum((not h) and j for h, j in ok)
    fn = sum(h and (not j) for h, j in ok)
    po = agree / n if n else None
    ph, pj = (sum(h for h, _ in ok) / n, sum(j for _, j in ok) / n) if n else (0, 0)
    pe = ph * pj + (1 - ph) * (1 - pj)
    kappa = (po - pe) / (1 - pe) if n and pe < 1 else None
    return {"n": n, "unread": len(pairs) - n, "agree": agree, "agreement": po, "fp": fp, "fn": fn, "kappa": kappa}


def main(argv=None):
    ap = argparse.ArgumentParser(description="fact_judge_v2 대 v3 사람 라벨 일치율")
    ap.add_argument("sheet")
    ap.add_argument("--rows", default="results/judge_version_agreement/rows.jsonl")
    ap.add_argument("--out", default="docs/results/judge_version_agreement_v2_v3.md")
    a = ap.parse_args(argv)
    from llm import LLM
    judge = LLM(role="judge")
    rows = read_rows(Path(a.sheet))
    out_rows = []
    Path(a.rows).parent.mkdir(parents=True, exist_ok=True)
    usd = 0.0
    from cost import compute_cost
    for r in rows:
        rec = {"row_id": r.get("row_id"), "human": r[COLS["human"]].strip() == "O"}
        for ver, alts in ((FACT_JUDGE_PROMPT_VERSION, None), (FACT_JUDGE_V3_VERSION, [])):
            ok, err, res = _judge_single_fact(r[COLS["question"]], r[COLS["reference"]], r[COLS["fact"]],
                                              r[COLS["answer"]], judge, alternatives=alts)
            rec[ver] = ok
            rec[ver + "_error"] = err
            usd += compute_cost(res).usd or 0.0
        out_rows.append(rec)
    with open(a.rows, "w", encoding="utf-8") as f:
        for rec in out_rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    s2 = stats([(x["human"], x[FACT_JUDGE_PROMPT_VERSION]) for x in out_rows])
    s3 = stats([(x["human"], x[FACT_JUDGE_V3_VERSION]) for x in out_rows])
    same = sum(x[FACT_JUDGE_PROMPT_VERSION] == x[FACT_JUDGE_V3_VERSION] for x in out_rows)
    fmt = lambda v: "–" if v is None else f"{v:.3f}"   # noqa: E731
    decision = ("v3 사용 (v2 보다 낮지 않음)" if s3["agreement"] is not None and s2["agreement"] is not None
                and s3["agreement"] >= s2["agreement"] else "v2 사용 (v3 가 낮음)")
    md = [
        "# 채점 버전 비교: fact_judge_v2 대 v3 (사람 라벨)", "",
        f"생성: `python src/judge_version_agreement.py {a.sheet}` ({datetime.now().isoformat(timespec='seconds')})", "",
        f"- judge: {judge.model}, per_fact, 응답 캐시 없이 v2·v3 각각 호출. 시트 {len(rows)}행 (human O/X).",
        f"- 프롬프트: v2 `{FACT_JUDGE_PROMPT_HASH}`, v3 `{FACT_JUDGE_V3_PROMPT_HASH}`. 시트에 대안이 없어 v3 는 v2 와 같은 글자의 프롬프트를 보냈다.",
        "", "| 버전 | 행 | 일치 | 일치율 | FP (사람 X, judge O) | FN (사람 O, judge X) | kappa | 못 읽음 |",
        "|---|---|---|---|---|---|---|---|",
        f"| v2 | {s2['n']} | {s2['agree']} | {fmt(s2['agreement'])} | {s2['fp']} | {s2['fn']} | {fmt(s2['kappa'])} | {s2['unread']} |",
        f"| v3 | {s3['n']} | {s3['agree']} | {fmt(s3['agreement'])} | {s3['fp']} | {s3['fn']} | {fmt(s3['kappa'])} | {s3['unread']} |",
        "", f"v2 와 v3 판정이 같은 행: {same} / {len(out_rows)} (다른 행은 같은 프롬프트의 반복 호출 변동).", "",
        f"**판정 규칙(v3 가 v2 보다 낮지 않으면 v3) 결과: {decision}.**", "",
        "한계: 이 시트에는 accept_alternatives 가 없어, 대안 블록이 붙은 판정의 정확도는 재지 못했다. "
        "multiturn-v2 검수 때 대안이 있는 key_fact 행을 사람이 라벨링해 따로 확인한다.", "",
        f"judge 비용: ${usd:.4f}",
    ]
    Path(a.out).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
