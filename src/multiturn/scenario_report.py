"""
multiturn-v2 시나리오 점검 보고 (API 호출 없음)

    python src/multiturn/scenario_report.py data/evalsets/multiturn-v2/*.json --out docs/experiments/multiturn_v2/samples_report.md

시나리오마다
    - 턴 유형 분포, recall 거리, 마지막 턴 기록 토큰 (tiktoken, 과거 답변 자리에 참고 정답)
    - 자동 검사 (validate_scenario_v2, check_grounding_v2) 오류 수
    - closed-book: 맞힌 턴 수 (유형별), standalone_question 이 원래 질문에 없는 key_entity 를 새로 담은 턴 (답 누설 의심)
    - 비율 압축 강도 r25/r50/r75 의 overflow 턴 비율 (기록 4k 이상 턴)
    - confusable 태그 key_fact 목록, same_doc_new_topic 의 소제목 비교
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def leak_entities(t: dict) -> list[str]:
    from core_match import find_normalized
    return [e for e in t.get("key_entities") or [] if len(e) >= 3
            and find_normalized(t["standalone_question"], e) is not None
            and find_normalized(t["question"], e) is None]


def analyse(s: dict, corpus, prompt, count) -> dict:
    from multiturn.scenario_v2 import check_grounding_v2, ratio_overflow, rule_report, validate_scenario_v2
    rep = rule_report(s, corpus)
    ro = ratio_overflow(s, corpus, prompt, count)
    cb = {}
    for t in s["turns"]:
        c = cb.setdefault(t["turn_type"], [0, 0])
        c[0] += 1
        c[1] += bool((t.get("closed_book") or {}).get("correct"))
    return {"id": s["scenario_id"], "title": s["title"], "rep": rep, "ratio": ro,
            "validate": validate_scenario_v2(s), "grounding": check_grounding_v2(s, corpus), "cb": cb,
            "leaks": [(t["turn"], t["turn_type"], leak_entities(t), bool((t.get("closed_book") or {}).get("correct")))
                      for t in s["turns"] if leak_entities(t)]}


def to_md(results: list[dict]) -> str:
    L = ["# multiturn-v2 샘플 점검", "", "자동 생성: `python src/multiturn/scenario_report.py` (API 호출 없음).", ""]
    L += ["## 턴 유형 분포와 기록", "", "| 시나리오 | 턴 | new | followup | recall | synthesis | update | same_doc | recall 거리 | "
          "3턴 이상 synthesis | 마지막 턴 기록 | 스키마 오류 | 근거 확인 실패 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        tc = r["rep"]["type_counts"]
        L.append(f"| {r['id']} | {r['rep']['turns']} | {tc['new']} | {tc['followup']} | {tc['recall']} | {tc['synthesis']} "
                 f"| {tc['update']} | {tc['same_doc_new_topic']} | {', '.join(map(str, r['rep']['recall_distances']))} "
                 f"| 턴 {', '.join(map(str, r['rep']['wide_synthesis']))} | {r['ratio']['final_history']:,} "
                 f"| {len(r['validate'])} | {len(r['grounding'])} |")
    L += ["", "근거 확인 실패 내용:", ""] + [f"- {e}" for r in results for e in r["grounding"]] + [""]
    L += ["## closed-book (문서·대화 없이 standalone_question)", "", "| 시나리오 | 유형 | 턴 | 맞힘 |", "|---|---|---|---|"]
    for r in results:
        for tt, (n, c) in r["cb"].items():
            L.append(f"| {r['id']} | {tt} | {n} | {c} |")
        tot = sum(v[0] for v in r["cb"].values()), sum(v[1] for v in r["cb"].values())
        L.append(f"| {r['id']} | **전체** | {tot[0]} | **{tot[1]}** |")
    L += ["", "standalone_question 이 원래 질문에 없는 key_entity 를 새로 담은 턴 (답 누설 의심):", "",
          "| 시나리오 | 턴 | 유형 | 새로 담은 key_entity | closed-book 맞힘 |", "|---|---|---|---|---|"]
    for r in results:
        for k, tt, ents, ok in r["leaks"]:
            L.append(f"| {r['id']} | {k} | {tt} | {', '.join(ents)} | {'예' if ok else '아니오'} |")
    L += ["", "## 비율 압축 강도의 overflow (기록 4k 이상 턴)", "",
          "예산 = ⌈r × 과거 기록⌉. 최근 1턴(keep_recent)만으로 예산을 넘으면 overflow. 과거 답변 자리에 참고 정답을 넣어 셌다.", "",
          "| 시나리오 | 센 턴 | r25 | r50 | r75 |", "|---|---|---|---|---|"]
    for r in results:
        ro = r["ratio"]
        f = lambda v: "–" if v is None else f"{v * 100:.0f}%"   # noqa: E731
        L.append(f"| {r['id']} | {ro['turns_counted']} | {f(ro['r25_overflow_rate'])} | {f(ro['r50_overflow_rate'])} "
                 f"| {f(ro['r75_overflow_rate'])} |")
    L += ["", "## confusable 태그 key_fact", "", "| 시나리오 | 턴 | key_fact |", "|---|---|---|"]
    for r in results:
        for c in r["rep"]["confusable_facts"]:
            L.append(f"| {r['id']} | {c['turn']} | {c['fact']} |")
    L += ["", "## same_doc_new_topic 소제목", "", "| 시나리오 | 턴 | source_turn | 페이지 | 첨부 때 물은 소제목 | 이번에 묻는 소제목 | 다른가 |",
          "|---|---|---|---|---|---|---|"]
    for r in results:
        for d in r["rep"]["same_doc"]:
            diff = not (set(d["sections"]) & set(d["source_sections"]))
            L.append(f"| {r['id']} | {d['turn']} | {d['source_turn']} | {d['page']} | {'; '.join(d['source_sections'])} "
                     f"| {'; '.join(d['sections'])} | {'예' if diff else '아니오'} |")
    L += ["", "## update 턴", "", "| 시나리오 | 턴 | 변경 | 영향 턴 |", "|---|---|---|---|"]
    for r in results:
        for u in r["rep"]["updates"]:
            ch = "; ".join(f"{c['what']}: {c['from']} → {c['to']}" for c in u["changes"] or [])
            L.append(f"| {r['id']} | {u['turn']} | {ch} | {u['affects']} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="multiturn-v2 시나리오 점검 보고")
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--out", default="docs/experiments/multiturn_v2/samples_report.md")
    a = ap.parse_args(argv)
    from corpus import load_corpus
    from llm import count_tokens
    from multiturn.prompt import load_mt_prompt
    corpus, prompt = load_corpus(), load_mt_prompt("v2")
    results = [analyse(json.loads(Path(p).read_text(encoding="utf-8")), corpus, prompt, count_tokens) for p in a.scenarios]
    md = to_md(results)
    Path(a.out).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
