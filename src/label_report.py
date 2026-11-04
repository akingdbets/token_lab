"""
사람 라벨 집계: 오답 분류(test_error_review.csv)와 judge 검증(judge_check_test.csv) (API 호출 없음)

    EVAL_DIR=data/evalsets/claude-v1 python src/label_report.py
    ... --recover "luna (기본)=results/runs/luna-default-20261103" --recover "terra (기본)=results/runs/terra-default-20261103"

오답 분류 (사람 분류 1~5, 기준은 labeling_guide.md 2절)
    - 사람 분류별 건수 (압축기별)
    - 자동 분류(A/B/C)와의 교차표
    - 사람 분류별 회복률: --recover 로 준 run 에서 같은 (문항, 압축기) trial 이 accuracy >= 0.5 인 비율
judge 검증 (human O/X, 기준은 labeling_guide.md 1절)
    - 사람 대비 정확도(일치율), Cohen's kappa, FP(사람 X·judge O)·FN(사람 O·judge X) 수와 목록
    - 압축 조건·유형·설정별 일치율
사람 라벨이 빈 행은 빼고 센다 (몇 행이 빠졌는지 적는다). 허용 값 밖이면 그 행을 알리고 멈춘다.
결과는 --out (기본 docs/results/label_report.md).
"""

from __future__ import annotations

import argparse
import json
import sys

from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge_agreement import agreement, label, read_sheet

ERROR_CLASSES = {"1": "정답 구절 삭제", "2": "연결어·조건 삭제", "3": "표기 분해",
                 "4": "정답 남음·추론 가능한데 틀림", "5": "기타"}
COMPRESSORS = ("llmlingua2_r50", "llmlingua2_r30", "rule>llmlingua2")
CONDS = ("none", "rule", "LL2-r50", "LL2-r30", "rule>LL2")
TYPES = ("fact", "code", "procedure", "multi")
DEFAULT_RECOVER = ("luna (기본)=results/runs/luna-default-20261103",
                   "terra (기본)=results/runs/terra-default-20261103")


def pct(a: int, n: int) -> str:
    return f"{a}/{n} ({100 * a / n:.0f}%)" if n else "-"


def error_class(v: str, where: str) -> str | None:
    v = (v or "").strip()
    if not v:
        return None
    v = v.split()[0].rstrip(".")      # "1 정답 구절 삭제" 처럼 이름을 붙여 써도 받는다
    if v not in ERROR_CLASSES:
        sys.exit(f"{where}: 사람 분류 값 '{v}' 는 1~5 가 아닙니다")
    return v


def load_trials(run: Path) -> dict:
    with open(run / "trials.jsonl", encoding="utf-8") as f:
        return {(t["qid"], t["compressor"]): t for t in map(json.loads, f) if t}


def error_section(path: Path, recover: list[tuple[str, Path]]) -> list[str]:
    rows = read_sheet(path)
    labeled = []
    for i, r in enumerate(rows, 2):
        c = error_class(r.get("사람 분류", ""), f"{path.name} {i}행 ({r['qid']} {r['압축기']})")
        if c:
            labeled.append({**r, "cls": c, "auto": (r.get("자동 분류") or "?").strip()[:1]})
    out = [f"## 1. 오답 분류 (`{path.name}`)", "",
           f"사람 분류가 채워진 행: **{len(labeled)} / {len(rows)}** (빈 행 {len(rows) - len(labeled)} 은 뺐다)", ""]
    if not labeled:
        return out + ["아직 사람 분류가 없다.", ""]
    comps = [c for c in COMPRESSORS if any(r["압축기"] == c for r in labeled)]

    out += ["### 사람 분류별 건수 (압축기별)", "",
            "| 사람 분류 | " + " | ".join(comps) + " | 합 |", "|---" * (len(comps) + 2) + "|"]
    for k, name in ERROR_CLASSES.items():
        n = [sum(r["cls"] == k and r["압축기"] == c for r in labeled) for c in comps]
        out.append(f"| {k} {name} | " + " | ".join(map(str, n)) + f" | {sum(n)} |")
    out.append("| 합 | " + " | ".join(str(sum(r["압축기"] == c for r in labeled)) for c in comps)
               + f" | {len(labeled)} |")

    autos = sorted({r["auto"] for r in labeled})
    out += ["", "### 자동 분류(A/B/C)와의 교차표", "",
            "자동 분류: A 근거 자리에 정답 핵심어 남음 / B 다른 위치에만 남음 / C 매칭 안 됨 (normalized-v2).", "",
            "| 사람 분류 \\ 자동 | " + " | ".join(autos) + " |", "|---" * (len(autos) + 1) + "|"]
    for k, name in ERROR_CLASSES.items():
        out.append(f"| {k} {name} | " + " | ".join(str(sum(r["cls"] == k and r["auto"] == a for r in labeled))
                                                     for a in autos) + " |")

    out += ["", "### 사람 분류별 회복률 (생각 켬, accuracy >= 0.5)", ""]
    runs = [(name, load_trials(p)) for name, p in recover if (p / "trials.jsonl").exists()]
    missing = [name for name, p in recover if not (p / "trials.jsonl").exists()]
    if missing:
        out += [f"run 이 없어 뺐다: {', '.join(missing)}", ""]
    if runs:
        out += ["| 사람 분류 | 오답 | " + " | ".join(name for name, _ in runs) + " |", "|---" * (len(runs) + 2) + "|"]
        for k, name in [*ERROR_CLASSES.items(), ("*", "전체")]:
            rs = [r for r in labeled if k == "*" or r["cls"] == k]
            cells = []
            for _, ts in runs:
                got = [ts.get((r["qid"], r["압축기"])) for r in rs]
                got = [t for t in got if t is not None]
                cells.append(pct(sum((t.get("answer_accuracy") or 0) >= 0.5 for t in got), len(got)))
            out.append(f"| {k if k != '*' else ''} {name} | {len(rs)} | " + " | ".join(cells) + " |")
    return out + [""]


def judge_section(sheet: Path, key: Path) -> list[str]:
    rows = read_sheet(sheet)
    keys = {r["row_id"]: r for r in read_sheet(key)}
    pairs = []
    for i, r in enumerate(rows, 2):
        v = (r.get("human") or "").strip()
        if not v:
            continue
        h = label(v)
        if h is None:
            sys.exit(f"{sheet.name} {i}행 ({r['row_id']}): human 값 '{v}' 는 O/X 가 아닙니다")
        k = keys.get(r["row_id"])
        if k is None:
            sys.exit(f"{key.name} 에 {r['row_id']} 가 없습니다")
        pairs.append({**r, "h": h, "j": label(k["judge"]), "partial": k.get("partial") == "1"})
    out = [f"## 2. judge 검증 (`{sheet.name}`)", "",
           f"human 이 채워진 행: **{len(pairs)} / {len(rows)}** (빈 행 {len(rows) - len(pairs)} 은 뺐다)", ""]
    if not pairs:
        return out + ["아직 사람 라벨이 없다.", ""]

    def stat_row(name, ps):
        s = agreement([(p["h"], p["j"]) for p in ps])
        if not s["n"]:
            return f"| {name} | 0 | - | - | - | - |"
        # 한쪽이 한 값뿐이면(예: judge YES 행만) κ 는 정의상 0 이라 뜻이 없다
        one_sided = len({p["h"] for p in ps}) < 2 or len({p["j"] for p in ps}) < 2
        k = "-" if s["kappa"] is None or one_sided else f"{s['kappa']:.3f}"
        return f"| {name} | {s['n']} | {s['agreement']:.3f} ({s['agree']}/{s['n']}) | {s['fp']} | {s['fn']} | {k} |"

    head = ["| 구분 | n | 정확도 (일치율) | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's κ |",
            "|---|---|---|---|---|---|"]
    out += ["### 전체", "", *head, stat_row("전체", pairs),
            stat_row("judge YES 행", [p for p in pairs if p["j"]]), stat_row("judge NO 행", [p for p in pairs if not p["j"]]),
            stat_row("부분 점수 문항", [p for p in pairs if p["partial"]]), "",
            "- judge YES 행의 정확도 = judge 가 O 라고 한 것 중 사람도 O 인 비율 (정밀도). NO 행도 같다.",
            "- 시트는 judge YES 40 / NO 40 으로 층화 추출했다. 실제 판정 분포(YES 95%)와 다르므로 전체 정확도는 "
            "이 표본에서의 값이다.", ""]
    for title, col, order in (("압축 조건별", "압축 조건", CONDS), ("유형별", "유형", TYPES),
                              ("설정별", "설정", sorted({p["설정"] for p in pairs}))):
        out += [f"### {title}", "", *head]
        out += [stat_row(v, [p for p in pairs if p[col] == v]) for v in order]
        out.append("")
    for name, want in (("FP (사람 X, judge O)", (False, True)), ("FN (사람 O, judge X)", (True, False))):
        ps = [p for p in pairs if (p["h"], p["j"]) == want]
        out += [f"### {name}: {len(ps)}", ""]
        if ps:
            out += ["| row_id | qid | 유형 | 설정 | 압축 조건 | 핵심 사실 | 모델 답변 | 메모 |", "|---|---|---|---|---|---|---|---|"]
            for p in sorted(ps, key=lambda p: p["row_id"]):
                cell = lambda s, n=120: (s or "").replace("|", "\\|").replace("\n", " ")[:n]  # noqa: E731
                out.append(f"| {p['row_id']} | {p['qid']} | {p['유형']} | {p['설정']} | {p['압축 조건']} | "
                           f"{cell(p['핵심 사실'])} | {cell(p['모델 답변'])} | {cell(p.get('메모'), 80)} |")
            out.append("")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--errors", default="docs/results/test_error_review.csv")
    ap.add_argument("--judge-sheet", default="docs/results/judge_check_test.csv")
    ap.add_argument("--judge-key", default="docs/results/judge_check_test_key.csv")
    ap.add_argument("--recover", action="append", metavar="이름=RUN_DIR",
                    help=f"회복률을 볼 run (여러 번). 기본: {', '.join(DEFAULT_RECOVER)}")
    ap.add_argument("--out", default="docs/results/label_report.md")
    args = ap.parse_args()
    recover = [(n, Path(p)) for n, p in (r.split("=", 1) for r in (args.recover or DEFAULT_RECOVER))]
    lines = ["# 사람 라벨 집계", "",
             f"`python src/label_report.py` 로 만든다 ({datetime.now():%Y-%m-%d %H:%M}). "
             "라벨 기준은 [labeling_guide.md](labeling_guide.md).", "",
             *error_section(Path(args.errors), recover), *judge_section(Path(args.judge_sheet), Path(args.judge_key))]
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
