"""
multiturn-v2 시나리오 점검 보고 (API 호출 없음)

    python src/multiturn/scenario_report.py data/evalsets/multiturn-v2/*.json --out docs/experiments/multiturn_v2/samples_report.md

시나리오마다
    - 턴 유형 분포, recall 거리, 마지막 턴 기록 토큰 (tiktoken, 과거 답변 자리에 참고 정답)
    - 자동 검사 (validate_scenario_v2, check_grounding_v2) 오류 수와 경고
    - key_fact 출처 (source=doc | user), recall·synthesis 의 user 비율, 문서 예시 값(example 태그) 비율
    - 턴당 질문 수: asks 개수, 질문의 물음표 수, key_fact 수
    - closed-book 두 종류 (knowledge: 사전 지식, grounded: 실험 지시문으로 NOT FOUND 대신 정답) 를 턴 유형별·출처별로
    - standalone_question 누설 (검사기 오류로 잡히므로 0 이어야 함)
    - 비율 압축 강도 r25/r50/r75 의 overflow 턴 비율 (기록 4k 이상 턴)
    - confusable 태그 key_fact 목록, same_doc_new_topic 의 소제목 비교, update 턴
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

KINDS = ("knowledge", "grounded")


def _cb(t: dict, kind: str) -> dict:
    return t.get(f"closed_book_{kind}") or {}


def analyse(s: dict, corpus, prompt, count) -> dict:
    from multiturn.scenario_v2 import (check_grounding_v2, fact_sources, ratio_overflow, rule_report,
                                       validate_scenario_v2)
    rep = rule_report(s, corpus)
    ro = ratio_overflow(s, corpus, prompt, count)
    cb = {}                     # turn_type -> [턴 수, knowledge 맞힘, grounded 맞힘]
    by_src = {}                 # (kind, source) -> [fact 수, 충족 수]
    for t in s["turns"]:
        c = cb.setdefault(t["turn_type"], [0, 0, 0])
        c[0] += 1
        for j, kind in enumerate(KINDS, 1):
            c[j] += bool(_cb(t, kind).get("correct"))
            fr = _cb(t, kind).get("fact_results") or []
            for i, src in enumerate(fact_sources(t)):
                if i < len(fr):
                    d = by_src.setdefault((kind, src), [0, 0])
                    d[0] += 1
                    d[1] += bool(fr[i])
    warns = []
    grounding = check_grounding_v2(s, corpus, warns)
    return {"id": s["scenario_id"], "title": s["title"], "rep": rep, "ratio": ro, "validate": validate_scenario_v2(s),
            "grounding": grounding, "warnings": warns, "cb": cb, "cb_by_source": by_src,
            "grounded_not_found": sum(1 for t in s["turns"] if _cb(t, "grounded").get("not_found")),
            "knowledge_unknown": sum(1 for t in s["turns"] if _cb(t, "knowledge").get("unknown")),
            "prompt": (s.get("generation") or {}).get("prompt"), "turn_types": [t["turn_type"] for t in s["turns"]]}


def _pct(a, b):
    return f"{a}/{b} ({a / b:.0%})" if b else "–"


def to_md(results: list[dict]) -> str:
    L = ["# multiturn-v2 샘플 점검", "", "자동 생성: `python src/multiturn/scenario_report.py` (API 호출 없음).", ""]
    L += ["생성 프롬프트: " + ", ".join(f"{r['id']} `{r['prompt']}`" for r in results), ""]
    L += ["## 턴 유형 분포와 기록", "", "| 시나리오 | 턴 | new | followup | recall | synthesis | update | same_doc | recall 거리 | "
          "3턴 이상 synthesis | 마지막 턴 기록 | 스키마 오류 | 근거 확인 실패 | 경고 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        tc = r["rep"]["type_counts"]
        L.append(f"| {r['id']} | {r['rep']['turns']} | {tc['new']} | {tc['followup']} | {tc['recall']} | {tc['synthesis']} "
                 f"| {tc['update']} | {tc['same_doc_new_topic']} | {', '.join(map(str, r['rep']['recall_distances']))} "
                 f"| 턴 {', '.join(map(str, r['rep']['wide_synthesis']))} | {r['ratio']['final_history']:,} "
                 f"| {len(r['validate'])} | {len(r['grounding'])} | {len(r['warnings'])} |")
    L += ["", "스키마 오류·근거 확인 실패·경고 내용:", ""]
    L += [f"- {e}" for r in results for e in r["validate"] + r["grounding"] + r["warnings"]] or ["- 없음"]
    L += ["", "## 출처와 질문 크기", "",
          "| 시나리오 | key_fact doc / user | recall·synthesis 중 user | user 값을 바꾸는 update | doc 중 example 태그 "
          "| 턴당 asks 평균 (synthesis 외 최대) | 물음표 2개 이상 턴 | 턴당 key_fact 평균 (최대) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in results:
        rp = r["rep"]
        fs, (nu, nt), (ne, nd) = rp["facts_by_source"], rp["user_share_recall_synthesis"], rp["doc_example_facts"]
        asks_ns = [a for a, tt in zip(rp["asks"], r["turn_types"]) if tt != "synthesis"]
        kf = rp["key_fact_counts"]
        L.append(f"| {r['id']} | {fs['doc']} / {fs['user']} | {_pct(nu, nt)} "
                 f"| 턴 {', '.join(str(u['turn']) for u in rp['updates'] if u['user_source']) or '없음'} | {_pct(ne, nd)} "
                 f"| {sum(rp['asks']) / len(rp['asks']):.2f} ({max(asks_ns)}) "
                 f"| {sum(1 for q in rp['question_marks'] if q >= 2)} | {sum(kf) / len(kf):.2f} ({max(kf)}) |")
    L += ["", "asks 는 생성 모델이 적은 '묻는 사항' 목록, 물음표 수는 질문 문장에서 센 교차 확인용 값이다.", ""]
    L += ["## closed-book 두 종류", "",
          "- knowledge: 싱글턴 CLOSED_BOOK_PROMPT (모르면 UNKNOWN). 사전 지식으로 맞히는지.",
          "- grounded: 실험 답변 지시문 mt_answer_v2 (NOT FOUND 규칙) 로 문서·기록 없이. **압축 결과를 오염시키는 쪽.**",
          "- 채점 fact_judge_v3 (per_fact), 맞힘 = 정확도 1.0.", "",
          "| 시나리오 | 유형 | 턴 | knowledge 맞힘 | grounded 맞힘 |", "|---|---|---|---|---|"]
    for r in results:
        for tt, (n, k, g) in r["cb"].items():
            L.append(f"| {r['id']} | {tt} | {n} | {k} | {g} |")
        n = sum(v[0] for v in r["cb"].values())
        k, g = sum(v[1] for v in r["cb"].values()), sum(v[2] for v in r["cb"].values())
        L.append(f"| {r['id']} | **전체** | {n} | **{_pct(k, n)}** | **{_pct(g, n)}** |")
    L += ["", "| 시나리오 | knowledge UNKNOWN | grounded NOT FOUND |", "|---|---|---|"]
    for r in results:
        L.append(f"| {r['id']} | {r['knowledge_unknown']} | {r['grounded_not_found']} |")
    L += ["", "key_fact 단위 충족률 (출처별):", "", "| 시나리오 | 검사 | source=doc | source=user |", "|---|---|---|---|"]
    for r in results:
        for kind in KINDS:
            d, u = r["cb_by_source"].get((kind, "doc"), [0, 0]), r["cb_by_source"].get((kind, "user"), [0, 0])
            L.append(f"| {r['id']} | {kind} | {_pct(d[1], d[0])} | {_pct(u[1], u[0])} |")
    L += ["", "## standalone_question 누설 (원래 질문에 없던 key_entity)", ""]
    leaks = [(r["id"], x) for r in results for x in r["rep"]["leaks"]]
    L += [f"- {sid} 턴 {x['turn']}: {x['entities']}" for sid, x in leaks] or ["- 없음 (검사기 오류로 잡는다)"]
    L += ["", "## source=user key_fact", "", "| 시나리오 | 턴 | 유형 | key_fact |", "|---|---|---|---|"]
    for r in results:
        for u in r["rep"]["user_facts"]:
            L.append(f"| {r['id']} | {u['turn']} | {u['turn_type']} | {u['fact']} |")
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
    L += ["", "## update 턴", "", "| 시나리오 | 턴 | 변경 | 영향 턴 | user 값 |", "|---|---|---|---|---|"]
    for r in results:
        for u in r["rep"]["updates"]:
            ch = "; ".join(f"{c['what']}: {c['from']} → {c['to']}" for c in u["changes"] or [])
            L.append(f"| {r['id']} | {u['turn']} | {ch} | {u['affects']} | {'예' if u['user_source'] else '아니오'} |")
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
