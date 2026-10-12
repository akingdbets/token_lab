"""
judge 판정과 사람 라벨 비교

judge_compare.py 로 만든 라벨링 시트에서 human 열(O/X)이 채워진 행만 골라
judge 조합(j 로 시작하는 열)마다 사람 대비 일치율, false positive, false negative, Cohen's kappa 를 낸다.

    false positive  사람 X, judge O  (judge 가 후하게 줌)
    false negative  사람 O, judge X  (judge 가 짜게 줌)

사용법

    python src/judge_agreement.py docs/results/judge_check_v2.csv
    python src/judge_agreement.py docs/results/judge_check_v2.csv --by-type

human 이 빈 행은 제외하고 몇 행이 빠졌는지 표시한다. O/X 외의 값이 있으면 그 행을 알려 주고 멈춘다.
시트를 Excel 이 CP949 로 다시 저장해도 읽는다.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

LABELS = {"O": True, "X": False}


def read_sheet(path: Path) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit(f"인코딩을 알 수 없습니다 (utf-8 / cp949 아님): {path}")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def label(v: str) -> bool | None:
    v = (v or "").strip().upper()
    return LABELS.get(v) if v else None


def agreement(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs = [(사람, judge)]."""
    n = len(pairs)
    if not n:
        return {"n": 0}
    agree = sum(h == j for h, j in pairs)
    fp = sum((not h) and j for h, j in pairs)
    fn = sum(h and (not j) for h, j in pairs)
    po = agree / n
    ph, pj = sum(h for h, _ in pairs) / n, sum(j for _, j in pairs) / n
    pe = ph * pj + (1 - ph) * (1 - pj)
    kappa = None if pe == 1 else (po - pe) / (1 - pe)
    return {"n": n, "agree": agree, "agreement": po, "fp": fp, "fn": fn, "kappa": kappa}


def fmt_row(name: str, s: dict) -> str:
    if not s["n"]:
        return f"| {name} | 0 | - | - | - | - |"
    k = "-" if s["kappa"] is None else f"{s['kappa']:.3f}"
    return (f"| {name} | {s['n']} | {s['agreement']:.3f} ({s['agree']}/{s['n']}) | "
            f"{s['fp']} | {s['fn']} | {k} |")


def main():
    ap = argparse.ArgumentParser(description="judge 판정 vs 사람 라벨 (일치율, FP, FN, Cohen's kappa)")
    ap.add_argument("sheet", help="라벨링 시트 csv (human 열 O/X)")
    ap.add_argument("--by-type", action="store_true", help="문항 type 별로도 출력")
    args = ap.parse_args()

    rows = read_sheet(Path(args.sheet))
    if not rows or "human" not in rows[0]:
        sys.exit("human 열이 없습니다")
    combos = [c for c in rows[0] if c.startswith("j")]
    if not combos:
        sys.exit("judge 열(j 로 시작)이 없습니다")

    bad = []
    for i, r in enumerate(rows, 2):
        for c in ["human", *combos]:
            v = (r.get(c) or "").strip()
            if v and v.upper() not in LABELS:
                bad.append(f"{i}행 {r.get('qid')} {c}={v!r}")
    if bad:
        sys.exit("O/X 가 아닌 값:\n  " + "\n  ".join(bad))

    labeled = [r for r in rows if label(r["human"]) is not None]
    print(f"시트: {args.sheet}  전체 {len(rows)}행, human 라벨 {len(labeled)}행, "
          f"빈 행 {len(rows) - len(labeled)}개 제외")
    if not labeled:
        return
    n_o = sum(label(r["human"]) for r in labeled)
    print(f"사람 라벨: O {n_o}, X {len(labeled) - n_o}\n")

    groups = [("전체", labeled)]
    if args.by_type:
        types = list(dict.fromkeys(r.get("type") for r in labeled))
        groups += [(t, [r for r in labeled if r.get("type") == t]) for t in types]

    for title, rs in groups:
        print(f"[{title}]")
        print("| 조합 | n | 일치율 | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's kappa |")
        print("|---|---|---|---|---|---|")
        for c in combos:
            pairs = [(label(r["human"]), label(r[c])) for r in rs if label(r[c]) is not None]
            print(fmt_row(c, agreement(pairs)))
        print()


if __name__ == "__main__":
    main()
