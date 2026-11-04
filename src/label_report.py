"""
사람 라벨 집계: 오답 분류(test_error_review.csv)와 judge 검증(judge_check_test.csv) (API 호출 없음)

    EVAL_DIR=data/evalsets/claude-v1 python src/label_report.py
    ... --recover "luna (기본)=results/runs/luna-default-20261103" --recover "반복=RUN1+RUN2+RUN3"

오답 분류 (사람 분류 1~5, 기준은 labeling_guide.md 2절)
    - 사람 분류별 건수: 압축기별, 유형별, 문항 수
    - 자동 분류(A/B/C)와의 교차표, 일치율 (사람 1 ↔ C, 사람 2·3·4 ↔ A·B, 사람 5 는 뺌)
    - 사람 분류별 회복률: --recover 로 준 run 에서 같은 (문항, 압축기) trial 이 accuracy >= 0.5 인 비율
      run 을 + 로 이으면 반복 실행으로 보고 평균한다. 정보 손실(1) 대 해석 손실(2+3+4) 은 Fisher 정확 검정
    - 메모가 있는 행: --source run(test_v1)의 답변·key_fact 판정·NOT FOUND 판정과 회복률 run 의 같은 trial
judge 검증 (human O/X, 기준은 labeling_guide.md 1절)
    - 사람 대비 정확도(일치율), Cohen's kappa, FP(사람 X·judge O)·FN(사람 O·judge X) 수와 목록
    - 압축 조건·유형·설정별 일치율
사람 라벨이 빈 행은 빼고 센다 (몇 행이 빠졌는지 적는다). 허용 값 밖이면 그 행을 알리고 멈춘다.
결과는 --out (기본 docs/results/label_report.md). 기존 파일의 수기 구간(MANUAL_BEGIN ~ MANUAL_END)은 그대로 옮긴다.
"""

from __future__ import annotations

import argparse
import json
import sys

from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge_agreement import agreement, label, read_sheet
from redundancy import fisher_p

ERROR_CLASSES = {"1": "정답 구절 삭제", "2": "연결어·조건 삭제", "3": "표기 분해",
                 "4": "정답 남음·추론 가능한데 틀림", "5": "기타"}
INFO_LOSS, INTERP_LOSS = ("1",), ("2", "3", "4")      # 정보 손실 / 해석 손실 (5 기타는 어느 쪽도 아님)
COMPRESSORS = ("llmlingua2_r50", "llmlingua2_r30", "rule>llmlingua2")
CONDS = ("none", "rule", "LL2-r50", "LL2-r30", "rule>LL2")
TYPES = ("fact", "code", "procedure", "multi")
DEFAULT_SOURCE = "results/runs/20261102-205826"         # test_v1 본실험 (오답의 출처)
DEFAULT_RECOVER = (
    "(1) 생각 끔·T0 재실행=results/reasoning_probe/current",
    "(2) 서버 기본값 [생각 켬]=results/reasoning_probe/default",
    "(3) 생각 끔·temperature 기본, 3회 평균=results/reasoning_probe/temp_default_r1"
    "+results/reasoning_probe/temp_default_r2+results/reasoning_probe/temp_default_r3",
    "luna (기본) [생각 켬]=results/runs/luna-default-20261103",
)
MANUAL_BEGIN = "<!-- 수기 시작: label_report.py 를 다시 돌려도 이 사이는 그대로 둔다 -->"
MANUAL_END = "<!-- 수기 끝 -->"


def pct(a: float, n: int) -> str:
    if not n:
        return "-"
    num = f"{a:g}" if a == int(a) else f"{a:.1f}"
    return f"{num}/{n} ({100 * a / n:.0f}%)"


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def cell(s, n=160) -> str:
    return (s or "").replace("|", "\\|").replace("\r", "").replace("\n", " ⏎ ")[:n]


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


def ok(t) -> bool:
    return t is not None and (t.get("answer_accuracy") or 0) >= 0.5


def parse_recover(specs) -> list[tuple[str, list[Path]]]:
    """'이름=RUN[+RUN...]' -> (이름, [run 경로]). run 이 여럿이면 회복 수를 평균한다 (반복 실행)."""
    return [(n, [Path(x) for x in p.split("+")]) for n, p in (r.split("=", 1) for r in specs)]


def recovery(runs: list[dict], keys) -> tuple[float, int]:
    """keys 의 trial 중 accuracy >= 0.5 인 수 (run 이 여럿이면 평균), trial 수."""
    got = [sum(ok(ts.get(k)) for k in keys) for ts in runs]
    return (sum(got) / len(got) if got else 0), len(keys)


def error_section(path: Path, recover, key: Path | None = None, source: Path | None = None) -> list[str]:
    """자동 분류는 key(qid, 압축기, 자동 분류)에서 읽는다. 없으면 시트의 자동 분류 열 (예전 시트).
    recover: [(이름, run 경로 또는 [run 경로...])]. source: 오답이 나온 run (메모 행의 judge 판정을 보여 준다)."""
    rows = read_sheet(path)
    auto = ({(r["qid"], r["압축기"]): r["자동 분류"] for r in read_sheet(key)} if key and key.exists() else {})
    labeled = []
    for i, r in enumerate(rows, 2):
        c = error_class(r.get("사람 분류", ""), f"{path.name} {i}행 ({r['qid']} {r['압축기']})")
        if c:
            a = auto.get((r["qid"], r["압축기"])) or r.get("자동 분류") or "?"
            labeled.append({**r, "cls": c, "auto": a.strip()[:1]})
    out = [f"## 1. 오답 분류 (`{path.name}`)", "",
           f"사람 분류가 채워진 행: **{len(labeled)} / {len(rows)}** (빈 행 {len(rows) - len(labeled)} 은 뺐다)", ""]
    if not labeled:
        return out + ["아직 사람 분류가 없다.", ""]
    comps = [c for c in COMPRESSORS if any(r["압축기"] == c for r in labeled)]
    types = [t for t in TYPES if any(r.get("qtype") == t for r in labeled)]

    def table(title, col, values):
        res = [f"### {title}", "",
               "| 사람 분류 | " + " | ".join(values) + " | 합 |", "|---" * (len(values) + 2) + "|"]
        for k, name in ERROR_CLASSES.items():
            n = [sum(r["cls"] == k and r.get(col) == v for r in labeled) for v in values]
            res.append(f"| {k} {name} | " + " | ".join(map(str, n)) + f" | {sum(n)} |")
        return res + ["| 합 | " + " | ".join(str(sum(r.get(col) == v for r in labeled)) for v in values)
                      + f" | {len(labeled)} |", ""]

    out += table("사람 분류별 건수 (압축기별)", "압축기", comps)
    out += table("사람 분류별 건수 (유형별)", "qtype", types)

    by_q: dict[str, list[str]] = {}
    for r in labeled:
        by_q.setdefault(r["qid"], []).append(r["cls"])
    out += ["### 사람 분류별 문항 수", "",
            f"trial 은 (문항, 압축기) 쌍이다. 문항은 {len(by_q)} 개다. "
            "한 문항이 압축기마다 다른 분류를 받으면 각 분류에 한 번씩 센다.", "",
            "| 사람 분류 | trial | 문항 |", "|---|---|---|"]
    for k, name in ERROR_CLASSES.items():
        out.append(f"| {k} {name} | {sum(r['cls'] == k for r in labeled)} | {sum(k in v for v in by_q.values())} |")
    mixed = [q for q, v in by_q.items() if len(set(v)) > 1]
    out += ["", f"압축기마다 분류가 다른 문항 {len(mixed)} 개: " + (", ".join(
        f"{q} (" + ", ".join(f"{r['압축기']} {r['cls']}" for r in labeled if r["qid"] == q) + ")"
        for q in mixed) or "없음"), ""]

    autos = sorted({r["auto"] for r in labeled})
    out += ["## 2. 자동 분류(A/B/C)와의 교차표", "",
            "자동 분류: A 근거 자리에 정답 핵심어 남음 / B 다른 위치에만 남음 / C 매칭 안 됨 (normalized-v2).", "",
            "| 사람 분류 \\ 자동 | " + " | ".join(autos) + " | 합 |", "|---" * (len(autos) + 2) + "|"]
    for k, name in ERROR_CLASSES.items():
        n = [sum(r["cls"] == k and r["auto"] == a for r in labeled) for a in autos]
        out.append(f"| {k} {name} | " + " | ".join(map(str, n)) + f" | {sum(n)} |")
    scored = [r for r in labeled if r["cls"] != "5" and r["auto"] in ("A", "B", "C")]
    agree = [r for r in scored if (r["cls"] == "1") == (r["auto"] == "C")]
    n1 = [r for r in scored if r["cls"] == "1"]
    n234 = [r for r in scored if r["cls"] != "1"]
    out += ["", "**일치율.** 자동 분류는 정답 문자열이 압축 문맥에 남았는지만 본다. 그래서 사람 1(정답 구절 삭제)은 자동 C 와, "
            "사람 2·3·4(정답은 남음)는 자동 A·B 와 맞대어 센다. 사람 5(기타)는 뺀다.", "",
            f"- 일치: **{pct(len(agree), len(scored))}**",
            f"- 사람 1 중 자동 C: {pct(sum(r['auto'] == 'C' for r in n1), len(n1))}",
            f"- 사람 2·3·4 중 자동 A·B: {pct(sum(r['auto'] != 'C' for r in n234), len(n234))}", ""]
    if len(agree) < len(scored):
        out += ["어긋난 trial:", "", "| qid | 압축기 | 사람 | 자동 |", "|---|---|---|---|"]
        out += [f"| {r['qid']} | {r['압축기']} | {r['cls']} | {r['auto']} |" for r in scored if r not in agree]
        out.append("")

    runs = []
    for name, ps in recover:
        ps = ps if isinstance(ps, list) else [ps]
        if all((p / "trials.jsonl").exists() for p in ps):
            runs.append((name, [load_trials(p) for p in ps]))
        else:
            out += [f"run 이 없어 뺐다: {name}", ""]
    out += ["## 3. 사람 분류별 회복률", "",
            "같은 압축 문맥에서 답변 설정만 바꿨을 때 그 trial 이 accuracy >= 0.5 가 된 비율이다. "
            "[생각 켬] 이 붙은 열이 생각 토큰을 쓰는 설정이다.", ""]
    if runs:
        out += ["| 사람 분류 | 오답 | " + " | ".join(name for name, _ in runs) + " |", "|---" * (len(runs) + 2) + "|"]
        groups = [*((f"{k} {n}", (k,)) for k, n in ERROR_CLASSES.items()),
                  ("**정보 손실 (1)**", INFO_LOSS), ("**해석 손실 (2+3+4)**", INTERP_LOSS),
                  ("전체", tuple(ERROR_CLASSES))]
        for title, ks in groups:
            keys = [(r["qid"], r["압축기"]) for r in labeled if r["cls"] in ks]
            out.append(f"| {title} | {len(keys)} | " + " | ".join(pct(*recovery(ts, keys)) for _, ts in runs) + " |")
        info = [(r["qid"], r["압축기"]) for r in labeled if r["cls"] in INFO_LOSS]
        interp = [(r["qid"], r["압축기"]) for r in labeled if r["cls"] in INTERP_LOSS]
        out += ["", "### 정보 손실 대 해석 손실 (Fisher 정확 검정, 양측)", "",
                "| 설정 | 정보 손실 (1) | 해석 손실 (2+3+4) | 차이 | Fisher p |", "|---|---|---|---|---|"]
        for name, ts in runs:
            a, m1 = recovery(ts, info)
            b, m2 = recovery(ts, interp)
            p = fmt_p(fisher_p(int(a), m1 - int(a), int(b), m2 - int(b))) if len(ts) == 1 else "- (반복 평균)"
            diff = f"{100 * (b / m2 - a / m1):+.0f}%p" if m1 and m2 else "-"
            out.append(f"| {name} | {pct(a, m1)} | {pct(b, m2)} | {diff} | {p} |")
        out += ["", "반복 평균인 열은 같은 trial 을 여러 번 센 것이라 독립 표본이 아니다. 그래서 Fisher 검정을 하지 않았다.", "",
                "### 분류별 회복 trial 목록", ""]
        for name, ts in runs:
            out.append(f"- **{name}**")
            for k, n in ERROR_CLASSES.items():
                keys = [(r["qid"], r["압축기"]) for r in labeled if r["cls"] == k]
                hit = [f"{q} {c}" + (f" ×{sum(ok(t.get((q, c))) for t in ts)}" if len(ts) > 1 else "")
                       for q, c in keys if any(ok(t.get((q, c))) for t in ts)]
                out.append(f"  - {k} {n}: {len(hit)} / {len(keys)}" + (f": {', '.join(hit)}" if hit else ""))
        out.append("")
    return out + memo_section(labeled, source, runs)


def memo_section(labeled, source: Path | None, runs) -> list[str]:
    """메모가 있는 행: test_v1 답변·key_fact 판정·NOT FOUND 판정과, 회복률 run 의 같은 trial."""
    memo = [r for r in labeled if (r.get("메모") or "").strip()]
    out = ["## 4. 메모가 있는 행의 원자료", ""]
    if not memo:
        return out + ["메모가 있는 행이 없다.", ""]
    src = load_trials(source) if source and (source / "trials.jsonl").exists() else {}
    for r in memo:
        k = (r["qid"], r["압축기"])
        t = src.get(k)
        out += [f"### {r['qid']} {r['압축기']} (사람 분류 {r['cls']})", "", f"- 메모: {cell(r['메모'], 300)}"]
        if t is None:
            out += ["- test_v1 trial 을 찾지 못했다", ""]
            continue
        facts = "; ".join(f"\"{cell(f['fact'], 200)}\" → {f['satisfied']}" for f in t.get("fact_results") or [])
        out += [f"- 질문: {cell(t.get('question'), 300)}",
                f"- 정답: `{cell(t.get('answer'), 200)}`",
                f"- test_v1 답변: `{cell(t.get('response'), 300)}`",
                f"- key_fact 판정 ({t.get('judge_prompt_version')}, {t.get('judge_mode')}): {facts}",
                f"- answer_accuracy {t.get('answer_accuracy')} · not_found {t.get('not_found')} · "
                f"예전 채점(grade): correct {t.get('correct')}, 방법 {t.get('grade_method')}, "
                f"문자열 일치 {t.get('match')}, YES/NO judge {t.get('judge')}",
                "", "| run | 답변 | accuracy |", "|---|---|---|"]
        for name, ts in runs:
            for i, d in enumerate(ts, 1):
                u = d.get(k)
                if u is not None:
                    tag = f" #{i}" if len(ts) > 1 else ""
                    out.append(f"| {name}{tag} | `{cell(u.get('response'), 200)}` | {u.get('answer_accuracy')} |")
        out.append("")
    return out


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
    out = [f"## 5. judge 검증 (`{sheet.name}`)", "",
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
                out.append(f"| {p['row_id']} | {p['qid']} | {p['유형']} | {p['설정']} | {p['압축 조건']} | "
                           f"{cell(p['핵심 사실'], 120)} | {cell(p['모델 답변'], 120)} | {cell(p.get('메모'), 80)} |")
            out.append("")
    return out


def manual_block(path: Path) -> list[str]:
    """기존 보고서의 수기 구간 (표식 포함). 없으면 빈 수기 구간."""
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if MANUAL_BEGIN in text and MANUAL_END in text:
            body = text.split(MANUAL_BEGIN, 1)[1].split(MANUAL_END, 1)[0]
            return [MANUAL_BEGIN + body + MANUAL_END, ""]
    return [MANUAL_BEGIN, "", MANUAL_END, ""]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--errors", default="docs/results/test_error_review.csv")
    ap.add_argument("--errors-key", default="docs/results/test_error_review_key.csv", help="자동 분류 (error_review_sheet.py)")
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="오답이 나온 run (메모 행의 judge 판정)")
    ap.add_argument("--judge-sheet", default="docs/results/judge_check_test.csv")
    ap.add_argument("--judge-key", default="docs/results/judge_check_test_key.csv")
    ap.add_argument("--recover", action="append", metavar="이름=RUN_DIR[+RUN_DIR...]",
                    help="회복률을 볼 run (여러 번). + 로 이으면 반복 실행 평균. 기본: " + " / ".join(DEFAULT_RECOVER))
    ap.add_argument("--out", default="docs/results/label_report.md")
    args = ap.parse_args()
    out = Path(args.out)
    lines = ["# 사람 라벨 집계", "",
             f"`python src/label_report.py` 로 만든다 ({datetime.now():%Y-%m-%d %H:%M}). "
             "라벨 기준은 [labeling_guide.md](labeling_guide.md). 1~5절은 스크립트가 만들고, 아래 수기 구간은 사람이 쓴다.", "",
             *manual_block(out),
             *error_section(Path(args.errors), parse_recover(args.recover or DEFAULT_RECOVER), Path(args.errors_key),
                            Path(args.source)),
             *judge_section(Path(args.judge_sheet), Path(args.judge_key))]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
