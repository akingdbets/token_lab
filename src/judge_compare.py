"""
judge 조합 비교 (같은 답변을 여러 judge 모델 x 모드로 채점한 결과)

rejudge.py 로 만든 재채점 결과 jsonl 들을 모아
    1) 조합별 평균 정확도, type 별 평균, 재요청·폴백 횟수, 판정 시간 표를 출력하고
    2) 사람 라벨링 시트 (key_fact 한 줄에 하나, judge 판정 O/X 열 포함)를 만들고
    3) 결과 요약 md (표 + 실행 환경)를 쓴다.

사용법

    python src/judge_compare.py \\
        --combo j7b_batch=results/judge_compare_v2/j7b_batch.jsonl \\
        --combo j7b_perfact=results/judge_compare_v2/j7b_per_fact.jsonl \\
        --combo j14b_batch=results/judge_compare_v2/j14b_batch.jsonl \\
        --combo j14b_perfact=results/judge_compare_v2/j14b_per_fact.jsonl \\
        --answers results/judge_compare_v2/answers.jsonl \\
        --sheet docs/results/judge_check_v2.csv --md docs/results/judge_compare_v2.md

시트 열
    qid, assignee, type, fact_idx, key_fact, answer, human, note, <조합 이름>...
    - answer 는 채점 대상 답변 (none 답변), 정답이 아니다
    - fact_idx 는 0 부터 (grader 의 index 와 같음)
    - human·note 는 비워 둔다 (O/X). 사람은 judge 열을 숨기고 라벨링한다 -> judge_agreement.py
    - assignee 는 A/B/C/D 에 행 수가 고르게 가도록 문항 단위로 배정 (한 문항은 한 사람). 행은 qid 순
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from experiment import TYPES, _mean
from grader import FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_PROMPT_VERSION

ASSIGNEES = ("A", "B", "C", "D")


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def combo_stats(rows: list[dict]) -> dict:
    types = [t for t in TYPES if any(r["qtype"] == t for r in rows)]
    by_type = {t: _mean(r["answer_accuracy"] for r in rows if r["qtype"] == t) for t in types}
    modes = [r.get("judge_mode") for r in rows]
    return {
        "n": len(rows),
        "accuracy": _mean(r["answer_accuracy"] for r in rows),
        "accuracy_judged": _mean(r["answer_accuracy_judged"] for r in rows),
        "type_avg": _mean(by_type.values()),
        "by_type": by_type,
        "n_by_type": {t: sum(r["qtype"] == t for r in rows) for t in types},
        "retries": sum(r.get("judge_retries", 0) for r in rows),
        "fallbacks": modes.count("per_fact_fallback"),
        "calls": sum(r.get("judge_calls", 0) for r in rows),
        "judge_sec": sum(r.get("judge_sec", 0.0) for r in rows),
        "judge_model": rows[0].get("judge_model") if rows else None,
    }


def stats_table(stats: dict[str, dict]) -> str:
    types = list(next(iter(stats.values()))["by_type"])
    n_by_type = next(iter(stats.values()))["n_by_type"]
    head = (["조합", "평균 정확도", "type 균등"] + [f"{t} (n={n_by_type[t]})" for t in types]
            + ["재요청", "폴백", "judge 호출", "판정 시간(초)"])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, s in stats.items():
        cells = ([name, f"{s['accuracy']:.3f}", f"{s['type_avg']:.3f}"]
                 + [f"{s['by_type'][t]:.3f}" for t in types]
                 + [str(s["retries"]), str(s["fallbacks"]), str(s["calls"]), f"{s['judge_sec']:.1f}"])
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def assign_balanced(qids: list[str], counts: dict[str, int]) -> dict[str, str]:
    """담당자별 행 수가 고르게 (문항은 쪼개지 않음). key_fact 가 많은 문항부터 행이 가장 적은 담당자에게.
    같으면 qid 순서, 담당자 순서. 문항마다 fact 수가 달라 qid 순서대로 끊으면 고르게 나눠지지 않는다."""
    load = {a: 0 for a in ASSIGNEES}
    out = {}
    for q in sorted(qids, key=lambda q: (-counts[q], q)):
        a = min(ASSIGNEES, key=lambda a: (load[a], a))
        out[q] = a
        load[a] += counts[q]
    return out


def build_sheet(answers: list[dict], combos: dict[str, list[dict]], path: Path) -> list[dict]:
    judged = {name: {r["qid"]: r for r in rows} for name, rows in combos.items()}
    ans = sorted(answers, key=lambda r: r["qid"])
    assignee = assign_balanced([a["qid"] for a in ans], {a["qid"]: len(a["key_facts"]) for a in ans})
    out = []
    for a in ans:
        for i, fact in enumerate(a["key_facts"]):
            row = {"qid": a["qid"], "assignee": assignee[a["qid"]], "type": a["qtype"], "fact_idx": i,
                   "key_fact": fact, "answer": a["response"], "human": "", "note": ""}
            for name, by_qid in judged.items():
                fr = by_qid[a["qid"]]["fact_results"]
                if fr[i]["fact"] != fact:
                    sys.exit(f"{name} {a['qid']} fact {i} 문장이 답변 파일과 다릅니다")
                row[name] = "O" if fr[i]["satisfied"] else "X"
            out.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Excel 에서 한글이 깨지지 않게 BOM 포함 UTF-8
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    return out


def environment(models: list[str]) -> dict:
    env = {}
    try:
        env["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                           text=True, check=True).stdout.strip()
        # 실행 시점에 커밋되지 않은 src 변경 (있으면 결과가 위 커밋 코드와 다를 수 있음)
        env["git_dirty"] = [l[3:] for l in subprocess.run(
            ["git", "status", "--porcelain", "--", "src"], capture_output=True, text=True,
            check=True).stdout.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        env["git_commit"], env["git_dirty"] = None, []
    base = CFG.judge_base_url.rstrip("/")
    try:
        env["ollama_version"] = requests.get(f"{base}/api/version", timeout=10).json().get("version")
        tags = requests.get(f"{base}/api/tags", timeout=10).json().get("models", [])
        env["model_digests"] = {m: next((t["digest"] for t in tags if t["name"] == m), None) for m in models}
    except requests.RequestException:
        env["ollama_version"], env["model_digests"] = None, {m: None for m in models}
    env["fact_judge"] = f"{FACT_JUDGE_PROMPT_VERSION} ({FACT_JUDGE_PROMPT_HASH})"
    return env


def main():
    ap = argparse.ArgumentParser(description="judge 조합 비교 표 + 사람 라벨링 시트")
    ap.add_argument("--combo", action="append", required=True, metavar="NAME=PATH",
                    help="조합 이름=rejudge 결과 jsonl (여러 번)")
    ap.add_argument("--answers", required=True, help="rejudge --save-answers 로 만든 답변 jsonl")
    ap.add_argument("--sheet", help="사람 라벨링 시트 csv 경로")
    ap.add_argument("--md", help="결과 요약 md 경로")
    args = ap.parse_args()

    combos = {}
    for c in args.combo:
        name, _, path = c.partition("=")
        combos[name] = load_jsonl(Path(path))
    answers = load_jsonl(Path(args.answers))
    if any(r.get("split") == "test" for r in answers):
        sys.exit("답변에 test 문항이 있습니다 (dev 만 비교)")
    qids = {a["qid"] for a in answers}
    for name, rows in combos.items():
        if {r["qid"] for r in rows} != qids or len(rows) != len(qids):
            sys.exit(f"{name}: 문항이 답변 파일과 다릅니다 ({len(rows)}행)")

    stats = {name: combo_stats(rows) for name, rows in combos.items()}
    table = stats_table(stats)
    print(table)

    n_rows = None
    if args.sheet:
        sheet = build_sheet(answers, combos, Path(args.sheet))
        n_rows = len(sheet)
        per = {a: sum(r["assignee"] == a for r in sheet) for a in ASSIGNEES}
        print(f"\n라벨링 시트: {args.sheet}  key_fact {n_rows}행 ({len(qids)}문항)  "
              + "  ".join(f"{a} {n}" for a, n in per.items()))

    if args.md:
        env = environment(sorted({s["judge_model"] for s in stats.values()}))
        n_nf = sum(bool(a.get("not_found")) for a in answers)
        src = sorted({(a.get("answer_source") or "").split(":", 1)[0] for a in answers})
        lines = [
            "# judge 조합 비교 v2 (dev)",
            "",
            f"같은 none 답변 {len(answers)}개(dev)를 judge 모델 2개 x 모드 2개로 채점한 결과. "
            f"채점 기준은 현재 `qa_dev.json` 의 key_facts ({sum(len(a['key_facts']) for a in answers)}개).",
            "",
            "- 정확도 = 충족 key_fact 수 / 전체 key_fact 수 의 문항 평균. 답변이 NOT FOUND 면 0 "
            f"(NOT FOUND {n_nf}문항)",
            "- batch: 한 번에 모든 fact 판정 (응답 index 가 어긋나면 1회 재요청, 그래도 안 되면 fact 별 폴백). "
            "per_fact: fact 하나당 호출 1회",
            "- 판정 시간은 judge 호출 벽시계 시간 합계 (모델 로딩 포함 가능)",
            "",
            "## 결과",
            "",
            table,
            "",
            "## 답변",
            "",
            "- c0148: 질문 수정 후 재생성한 답변 (run `20261012-143736`, `results/runs/20261012-143736/trials.jsonl`)",
            "- 나머지 34문항: `data/evalsets/claude-v1/review/review_dev_v1.csv` 의 `none_answer` "
            "(run `20261011-154540`)",
            "- 답변 생성 설정: qwen2.5:7b, temperature 0, seed 42, answer_prompt v1",
            "- 합친 답변: `results/judge_compare_v2/answers.jsonl` (커밋 안 함)",
            "",
            "## 사람 라벨링",
            "",
        ]
        if n_rows:
            names = list(combos)
            split = [r for r in sheet if len({r[c] for c in names}) > 1]
            lines += [
                f"- 시트: `{args.sheet}` (key_fact {n_rows}행). human 열에 O/X, judge 열은 숨기고 라벨링",
                "- 일치율·false positive·false negative·Cohen's kappa: "
                f"`python src/judge_agreement.py {args.sheet}`",
                f"- judge 조합끼리 판정이 갈린 key_fact: {len(split)}/{n_rows}행 (사람 라벨로 어느 쪽이 맞는지 가린다)",
                "",
                "| qid | type | fact_idx | " + " | ".join(names) + " | key_fact |",
                "|---|---|---|" + "---|" * len(names) + "---|",
            ]
            lines += [f"| {r['qid']} | {r['type']} | {r['fact_idx']} | "
                      + " | ".join(r[c] for c in names) + f" | {r['key_fact'].replace('|', '/')} |"
                      for r in split]
            lines.append("")
        lines += [
            "## 실행 환경",
            "",
            f"- git commit: `{env['git_commit']}`"
            + (f" + 커밋 전 변경 {', '.join(f'`{p}`' for p in env['git_dirty'])}" if env["git_dirty"] else ""),
            f"- Ollama: {env['ollama_version']}",
        ]
        lines += [f"- {m}: `{d}`" for m, d in env["model_digests"].items()]
        lines += [f"- key_facts judge 프롬프트: {env['fact_judge']}",
                  f"- judge 설정: temperature {CFG.temperature}, seed {CFG.seed}, num_ctx {CFG.num_ctx}",
                  ""]
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text("\n".join(lines), encoding="utf-8")
        print(f"요약: {args.md}")


if __name__ == "__main__":
    main()
