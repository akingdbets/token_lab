"""
멀티턴 파일럿 결과 문서 생성 (docs/results/multiturn_pilot_v1.md)

    python src/multiturn/pilot_report.py \
        --run results/runs/mt_20261123-233727 \
        --reference-run results/runs/mt_20261123-232847 \
        --sequential results/runs/mt_20261124-002939 \
        --out docs/results/multiturn_pilot_v1.md

표의 수치는 전부 summary.json / turn_trials.jsonl / sequential_chains.jsonl 에서 뽑는다.
원인 분석·한계 같은 해석 문장만 이 파일에 고정 문구로 둔다 (수치를 손으로 옮기지 않는다).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _pct(v, signed=True, nd=1):
    if v is None:
        return "–"
    return f"{v:+.{nd}f}%" if signed else f"{v:.{nd}f}%"


def _num(v, nd=1):
    return "–" if v is None else f"{v:.{nd}f}"


def _yn(v):
    return "–" if v is None else ("✓" if v else "✗")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


# ---------------- 표 ----------------

def config_section(s: dict, ref_run: str | None) -> list[str]:
    c = s["config"]
    r = c["replay"]
    seg = c.get("execution_segments") or []
    lines = ["## 설정", "",
             "| 항목 | 값 |", "|---|---|",
             f"| 답변 모델 | {r['model']} (reasoning_effort={r['reasoning_effort']}, temperature={r['temperature']}, "
             f"출력 한도 {r['max_completion_tokens']}) |",
             f"| 채점 | {c['judge']['model']} ({c['judge']['mode']}) |",
             f"| 답변 지시문 | {c['prompt']['version']} ({c['prompt']['sha256']}) |",
             f"| 시나리오 | " + ", ".join(f"{k} ({v['turns']}턴, {v['status']})" for k, v in c["scenarios"].items()) + " |",
             f"| sample | {r['samples']} (기준 궤적 sample {r['reference_sample']}) |",
             f"| 기록 예산 | {', '.join(map(str, r['history_budgets']))} (keep_recent {r['keep_recent']}) |",
             f"| 요약 | {r.get('summary_model') or '–'} (조건 {', '.join(r.get('summary_reasoning_effort') or []) or '–'}, "
             f"출력 한도 {r.get('summary_max_tokens') or '–'}) |",
             f"| 비열등 마진 | {r['margin']} (부트스트랩 {r['boot']}회) |",
             f"| 토크나이저 | {c['tokenizer']} |",
             f"| 실행 구간 | " + "; ".join(
                 f"concurrency {g['concurrency']} · trial {g['trials_submitted']} + 체인 {g.get('chains_submitted', 0)}"
                 + (" (사후 기록)" if g.get("backfilled") else "") for g in seg) + " |"]
    if ref_run:
        lines.append(f"| 기준 궤적 run | `{ref_run}` |")
    lines.append("")
    return lines


def main_table(s: dict) -> list[str]:
    comps = s["compressors"]
    lines = ["## 전체 표 (none 대비)", "",
             "sim = 직전 턴 접두부를 캐시 읽기로 본 비용 (주 지표), sim_write = 미스 부분을 캐시 쓰기 단가로 (luna 실측과 일치, "
             "캐시 검증 절), nocache = 캐시 0%. 양수가 절감.", "",
             "| 압축기 | 입력 절감 | 총 토큰 절감 | sim | sim_write | nocache | 접두부 공유 | 유지율 | 비열등 (턴 / 시나리오) "
             "| 추론 토큰 | 요약 호출 | 요약 비용 | 재압축 | 요약 실패율 | overflow |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    none_prefix = None
    for b in comps.values():
        none_prefix = b["all"]["cache"]["none"]["prefix_share_mean"]
        none_reason = b["all"]["reasoning_tokens"]["none_mean"]
        break
    if none_prefix is not None:
        lines.append(f"| none | – | – | – | – | – | {none_prefix * 100:.1f}% | – | – | {none_reason:.1f} | – | – | – | – | – |")
    for name, b in comps.items():
        a = b["all"]
        ni = a.get("non_inferiority") or {}
        nic = a.get("non_inferiority_cluster") or {}
        lines.append(
            f"| {name} | {_pct(a['input_reduction_pct'], False)} | {_pct(a['total_token_reduction_pct'], False)} "
            f"| {_pct(a['cost_reduction_pct_sim'])} | {_pct(a.get('cost_reduction_pct_sim_write'))} "
            f"| {_pct(a.get('cost_reduction_pct_nocache'))} | {a['cache']['compressed']['prefix_share_mean'] * 100:.1f}% "
            f"| {_pct(a['retention_pct'], False)} | {_yn(ni.get('non_inferior'))} / {_yn(nic.get('non_inferior'))} "
            f"| {_num(a['reasoning_tokens']['compressed_mean'])} | {a.get('summary_calls') or 0} "
            f"| ${a.get('compress_cost_usd') or 0:.4f} | {a.get('recompress_count') or 0} "
            f"| {_pct((a.get('summary_failed_rate') or 0) * 100, False)} | {_pct((a.get('overflow_rate') or 0) * 100, False)} |")
    idle = [name for name, b in comps.items()
            if ("summary" in name) and not (b["all"].get("summary_calls") or 0)]
    if idle:
        lines += ["", "요약 호출이 0회인 요약형 조건 (기록이 예산을 넘은 적이 없어 요약 단계가 한 번도 돌지 않음. "
                      "결과는 요약 없는 앞 단계와 같다): " + ", ".join(f"`{x}`" for x in idle) + "."]
    n = s["noise_none_vs_none"]["all"]["paired_bootstrap_turn"]
    lines += ["", f"none 대 none 변동폭 (sample 0 대 나머지, {n['n_pairs']}쌍): 정확도 차이 {n['diff']:+.3f}, "
                  f"95% CI [{n['diff_ci'][0]:+.3f}, {n['diff_ci'][1]:+.3f}].", ""]
    return lines


def prefix_compare(s: dict) -> list[str]:
    comps = s["compressors"]
    rows = defaultdict(dict)
    for name, b in comps.items():
        for fam in ("rolling_summary", "frozen_summary"):
            if name.startswith(fam + "("):
                budget = name[len(fam) + 1:name.index(")")]
                sre = name.split("[sre=")[1].rstrip("]") if "[sre=" in name else "-"
                rows[(budget, sre)][fam] = b["all"]["cache"]["compressed"]["prefix_share_mean"]
    if not rows:
        return []
    lines = ["## frozen 대 rolling 접두부 공유율", "",
             "| 예산 | 요약 추론 | rolling | frozen | frozen 이 높은가 |", "|---|---|---|---|---|"]
    for (budget, sre), v in sorted(rows.items(), key=lambda x: (int(x[0][0]), x[0][1])):
        r, f = v.get("rolling_summary"), v.get("frozen_summary")
        lines.append(f"| {budget} | {sre} | {_pct(r * 100 if r is not None else None, False)} "
                     f"| {_pct(f * 100 if f is not None else None, False)} "
                     f"| {_yn(None if r is None or f is None else f > r)} |")
    return lines + [""]


def turn_type_table(rows: list[dict], comps: list[str]) -> list[str]:
    acc, nf = defaultdict(list), defaultdict(list)
    for r in rows:
        if r.get("summary_failed"):
            continue
        acc[(r["compressor"], r["turn_type"])].append(r["answer_accuracy"])
        nf[(r["compressor"], r["turn_type"])].append(1 if r.get("not_found") else 0)
    types = ("new", "followup", "recall", "synthesis")
    lines = ["## turn_type 별 정확도 (not_found 비율)", "",
             "| 압축기 | " + " | ".join(types) + " |", "|---|" + "---|" * len(types)]
    for c in ["none"] + comps:
        cells = []
        for t in types:
            a = _mean(acc.get((c, t), []))
            n = _mean(nf.get((c, t), []))
            cells.append("–" if a is None else f"{a:.2f} ({n * 100:.0f}%)")
        lines.append(f"| {c} | " + " | ".join(cells) + " |")
    return lines + [""]


def failure_table(rows: list[dict], samples: int) -> list[str]:
    fail = defaultdict(list)
    for r in rows:
        if r["compressor"] == "none":
            continue
        if r.get("summary_failed") or (r["answer_accuracy"] is not None and r["answer_accuracy"] < 1.0):
            fail[(r["scenario_id"], r["turn"], r["turn_type"], r["compressor"])].append(r)
    lines = ["## 정확도가 1.0 아래로 떨어진 턴", "",
             f"평균 정확도는 sample {samples}개 평균 (맞은 sample 포함). NOT FOUND 는 그중 NOT FOUND 답변 수.", "",
             "| 시나리오 | 턴 | turn_type | 압축기 | 평균 정확도 | 틀린 sample | NOT FOUND | 요약 실패 |",
             "|---|---|---|---|---|---|---|---|"]
    for (sid, k, tt, c), rs in sorted(fail.items()):
        accs = [0.0 if x.get("summary_failed") else x["answer_accuracy"] for x in rs]
        mean = (sum(accs) + (samples - len(rs))) / samples
        lines.append(f"| {sid} | {k} | {tt} | {c} | {mean:.2f} | {len(rs)} | {sum(1 for x in rs if x.get('not_found'))} "
                     f"| {sum(1 for x in rs if x.get('summary_failed'))} |")
    return lines + [""]


def reasoning_section(s: dict) -> list[str]:
    lines = ["## 압축 전후 추론 토큰", "",
             "| 압축기 | none 평균 | 압축 후 평균 | 변화 | 출력 전체 평균 (none → 압축) |", "|---|---|---|---|---|"]
    for name, b in s["compressors"].items():
        rt, ct = b["all"]["reasoning_tokens"], b["all"]["completion_tokens"]
        ch = 100 * (rt["compressed_mean"] / rt["none_mean"] - 1) if rt["none_mean"] else None
        lines.append(f"| {name} | {rt['none_mean']:.1f} | {rt['compressed_mean']:.1f} | {_pct(ch)} "
                     f"| {ct['none_mean']:.1f} → {ct['compressed_mean']:.1f} |")
    lines += ["", "기록이 잘리거나 문서가 깎이면 모델이 근거를 찾느라 추론이 늘어, 출력 비용이 입력 절감의 일부를 상쇄한다.", ""]
    return lines


def cache_section(seq_rows: list[dict]) -> list[str]:
    if not seq_rows:
        return []
    comps = list(dict.fromkeys(r["compressor"] for r in seq_rows))
    base = {}
    lines = ["## 캐시 실측 검증 (`--sequential-chains`)", "",
             "응답 캐시를 끄고 턴 순서대로 한 번에 하나씩 보냈다 (시나리오 3개, sample 0, 채점 없음).", "",
             "| 압축기 | 시뮬레이션 적중률 | 실측 적중률 | 실측/시뮬레이션 (턴 평균) | 실측 캐시 쓰기 토큰 | 실측 비용 | sim | sim_write "
             "| 실측 절감 | sim 절감 | sim_write 절감 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in comps:
        rs = [r for r in seq_rows if r["compressor"] == c and not r.get("summary_failed")]
        p = sum(r["prompt_tokens"] for r in rs)
        sim = sum(r.get("sim_cached_tokens") or 0 for r in rs)
        meas = sum(r["cached_tokens"] or 0 for r in rs)
        w = sum(r.get("cache_write_tokens") or 0 for r in rs)
        m_usd = sum(r["cost_measured"]["usd"] for r in rs)
        s_usd = sum(r["cost_sim"]["usd_read"] for r in rs)
        sw_usd = sum(r["cost_sim"]["usd_write"] for r in rs)
        ratio = _mean([r["cached_tokens"] / r["sim_cached_tokens"] for r in rs if r.get("sim_cached_tokens")])
        if not base:
            base = {"m": m_usd, "s": s_usd, "w": sw_usd}
        red = lambda b, v: 100 * (1 - v / b) if b else None   # noqa: E731
        lines.append(f"| {c} | {sim / p * 100:.1f}% | {meas / p * 100:.1f}% | {_num(ratio, 3)} | {w:,} | ${m_usd:.5f} "
                     f"| ${s_usd:.5f} | ${sw_usd:.5f} | {_pct(red(base['m'], m_usd))} | {_pct(red(base['s'], s_usd))} "
                     f"| {_pct(red(base['w'], sw_usd))} |")
    lines += ["", "### 턴별 (시뮬레이션 캐시 토큰 / 실측 cached_tokens / 실측 cache_write_tokens)", "",
              "| 시나리오 | 턴 | " + " | ".join(comps) + " |", "|---|---|" + "---|" * len(comps)]
    by = {(r["compressor"], r["scenario_id"], r["turn"]): r for r in seq_rows}
    keys = sorted({(r["scenario_id"], r["turn"]) for r in seq_rows})
    for sid, k in keys:
        cells = []
        for c in comps:
            r = by.get((c, sid, k))
            cells.append("–" if r is None else f"{r.get('sim_cached_tokens') or 0} / {r['cached_tokens']} / {r.get('cache_write_tokens')}")
        lines.append(f"| {sid} | {k} | " + " | ".join(cells) + " |")
    below = [(r["compressor"], r["scenario_id"], r["turn"]) for r in seq_rows
             if r.get("cached_tokens") is not None and r["cached_tokens"] < (r.get("sim_cached_tokens") or 0) - 10]
    lines += ["", f"실측이 시뮬레이션보다 10토큰 넘게 적은 턴: {len(below)}개.", ""]
    return lines


# ---------------- 고정 해석 문구 ----------------

LLMLINGUA_ANALYSIS = """## llmlingua2 followup 하락 원인

`per_message(llmlingua2)` 가 실제로 압축한 범위를 trajectory 의 `messages_sent` 로 확인했다. 과거 user 메시지의 `<documentation>`
블록만 압축됐고, assistant 답변과 질문·형식 줄은 원문과 같다 (설계대로, 답변 압축 버그 아님).

| 턴 | 빠진 key_fact | 원문 | 압축본 |
|---|---|---|---|
| mt02 턴 1 | The server logs nothing about the real error | "The client still gets a `500 Internal Server Error`, but the server logs **nothing** about the real error." | "client gets 500 Server real error" (문장이 통째로 빠짐. force_tokens 에 no·not·never 는 있지만 nothing 은 없다) |
| mt03 턴 1 | Return a Response such as JSONResponse directly / not validated or filtered by the response model | "To keep using your response model *and* change the status dynamically, declare a `Response` parameter…" | "response model change status declare Response parameter" (조건이 깎임. 모델이 다른 정당한 해법인 Response 주입을 고름) |

on_arrival(llmlingua2) 는 현재 턴 문서도 압축하므로 new 턴에서도 틀린다. 예: mt03 턴 0 의 "below 200" 이 "200" 으로 깎여
"200, 204, 205, 304" 로 답했다.
"""

LIMITS = """## 파일럿 한계

- 시나리오 3개 × 9턴 (27턴). 시나리오 군집 부트스트랩은 단위가 3개라 참고용이다.
- 기준 궤적 정확도가 27턴 모두 1.0 이고 none 대 none 변동이 0 이다 (천장 효과). 비열등 판정은 사실상 "한 번이라도 틀렸는가" 다.
- 시나리오는 초안(`status: draft`)이고 사람 검수 전이다.
- 9턴 대화의 기록은 최대 약 6.5k 토큰이라 예산 8000 의 요약형(그리고 `on_arrival(rule)>frozen_summary(8000)`)은 요약이 한 번도
  일어나지 않았다. 장기 대화용 조합을 검증하려면 더 긴 시나리오가 필요하다.
- mt03 턴 1 의 key_fact 는 "JSONResponse 를 직접 반환" 하나만 정답으로 본다. 문서에는 응답 모델을 유지하며 상태를 바꾸는
  `Response` 파라미터 주입도 정당한 해법으로 나온다. per_message(llmlingua2)·on_arrival(llmlingua2) 의 이 턴 감점 일부는
  정보 손실이 아니라 key_fact 가 다른 정당한 해법을 오답 처리한 결과다. 검수 때 key_fact 를 고친다.
- 캐시 실측 검증은 시나리오 3개 × sample 1 이고, 같은 요청이 다른 체인·이전 실행에 있으면 서버 캐시가 체인 밖에서 적중한다
  (on_arrival 은 25분 전 replay 실행분, per_message(rule) 는 직전 on_arrival 체인과 같은 요청). 그래서 실측 적중률이 시뮬레이션보다
  높게 나온 압축기가 있다. none 은 체인 밖 요청이 없어 시뮬레이션과 턴마다 2토큰 안쪽으로 맞았고, 실측 비용이 sim_write 와 같았다.
"""


def build(run: Path, ref_run: Path | None, seq: Path | None) -> str:
    s = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rows = _jsonl(run / "turn_trials.jsonl")
    seq_rows = _jsonl(seq / "sequential_chains.jsonl") if seq else []
    comps = list(s["compressors"])
    out = ["# 멀티턴 파일럿 v1 결과", "",
           f"자동 생성: `python src/multiturn/pilot_report.py` (run `{run.name}`"
           + (f", 캐시 검증 `{seq.name}`" if seq else "") + "). 표의 수치는 결과 파일에서 뽑았다.", ""]
    out += config_section(s, ref_run.name if ref_run else None)
    rh = s["reference_health"]
    ah = s["answer_health"]
    out += ["## 기준 궤적과 답변 상태", "",
            f"- 기준 궤적 경고 {rh['n_warnings']}건 (빈 답변·finish_reason=length 없음이면 0).",
            f"- 답변 잘림(finish=length) 합계 {sum(v['finish_length'] for v in ah.values())}, "
            f"빈 답변 합계 {sum(v['empty_response'] for v in ah.values())}.", ""]
    out += main_table(s)
    out += prefix_compare(s)
    out += turn_type_table(rows, comps)
    out += failure_table(rows, s["config"]["replay"]["samples"])
    out += reasoning_section(s)
    out += [LLMLINGUA_ANALYSIS]
    out += cache_section(seq_rows)
    out += [LIMITS]
    return "\n".join(out).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--run", required=True)
    ap.add_argument("--reference-run")
    ap.add_argument("--sequential")
    ap.add_argument("--out", default="docs/results/multiturn_pilot_v1.md")
    a = ap.parse_args(argv)
    text = build(Path(a.run), Path(a.reference_run) if a.reference_run else None,
                 Path(a.sequential) if a.sequential else None)
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"저장: {a.out}")


if __name__ == "__main__":
    main()
