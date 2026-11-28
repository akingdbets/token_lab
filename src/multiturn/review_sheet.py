"""
multiturn-v2 시나리오 검수 시트 (API 호출 없음)

    python src/multiturn/review_sheet.py data/evalsets/multiturn-v2/*.json --name multiturn_v2_samples

출력
    docs/review/<name>.csv    행 = 턴. 검수 칸(standalone_same_fact, verdict, memo, reviewer)은 비어 있다
    docs/review/<name>.html   같은 내용을 보기 쉬운 한 장으로. 브라우저에서 검수 칸을 채우면 그 브라우저에 저장되고,
                              "CSV 내려받기" 로 채운 시트를 받는다 (CSV 를 바꿔 커밋)

검수 칸
    standalone_same_fact   standalone_question 이 원래 질문과 같은 사실을 묻는가: 예 / 아니오
    alt_judge_label        대안(accept_alternatives)이 있는 fact 의 judge(fact_judge_v3) 판정이 맞는가: 맞음 / 틀림
                           (대안 블록이 붙은 판정은 80행 비교로 잴 수 없어 검수 때 사람 라벨로 따로 확인한다)
    verdict                OK / 수정 필요 / 제외
    memo, reviewer
자동 검사 결과(근거 확인·규칙 위반)와 closed-book 결과를 함께 보여 준다. 판정은 사람이 한다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CFG  # noqa: E402

COLUMNS = ["row_id", "scenario_id", "turn", "turn_type", "type", "depends_on", "recall_distance", "evidence_pages",
           "question", "asks", "standalone_question", "answer", "key_facts", "evidence", "update_info",
           "closed_book_knowledge", "closed_book_grounded", "alt_judgments", "auto_check", "suspect", "review_flags",
           "standalone_same_fact", "alt_judge_label", "verdict", "memo", "reviewer"]
REVIEW_COLS = ("standalone_same_fact", "alt_judge_label", "verdict", "memo", "reviewer")


def _facts(t: dict) -> str:
    out = []
    for i, f in enumerate(t["key_facts"]):
        m = (t.get("fact_meta") or [{}] * len(t["key_facts"]))[i] or {}
        tags = " [" + ", ".join([f"source={m.get('source', '?')}"] + list(m.get("tags") or [])) + "]"
        alts = "".join(f"\n    대안: {a}" for a in m.get("accept_alternatives") or [])
        out.append(f"[{i}] {f}{tags}{alts}")
    return "\n".join(out)


def _evidence(t: dict) -> str:
    rows = [f"[{e['fact_idx']}] " + (f"{e['page']}: " if "page" in e else f"(사용자 발화, 턴 {e.get('user_turn')}): ")
            + e["quote"] for e in t["evidence"]]
    rows += [f"[{e['fact_idx']} 대안 {e['alt_idx']}] {e['page']}: {e['quote']}" for e in t.get("alt_evidence") or []]
    return "\n".join(rows)


def _update_info(t: dict) -> str:
    if t["turn_type"] == "update":
        ch = "; ".join(f"{c.get('what')}: {c.get('from')} → {c.get('to')}" for c in t.get("changes") or [])
        return f"변경 {ch} / 영향 턴 {t.get('affects')}"
    if t["turn_type"] == "same_doc_new_topic":
        return f"source_turn {t.get('source_turn')}"
    return ""


def _closed_book(t: dict, kind: str) -> str:
    cb = t.get(f"closed_book_{kind}")
    if not cb:
        return "(검사 전)"
    acc = cb.get("accuracy")
    verdict = ("맞힘" if cb.get("correct") else "UNKNOWN" if cb.get("unknown") else "NOT FOUND" if cb.get("not_found")
               else f"정확도 {acc}")
    return f"{verdict} | 답: {cb.get('response', '')[:300]}"


def _alt_judgments(t: dict) -> str:
    """대안이 있는 fact 의 closed-book 판정 (fact_judge_v3, 대안 블록이 붙은 프롬프트). 없으면 빈 칸."""
    out = []
    for i, m in enumerate(t.get("fact_meta") or []):
        if not (m or {}).get("accept_alternatives"):
            continue
        for kind in ("knowledge", "grounded"):
            cb = t.get(f"closed_book_{kind}") or {}
            fr = cb.get("fact_results") or []
            if i < len(fr) and not cb.get("judge_skipped"):
                out.append(f"[{i}] {kind}: {'충족' if fr[i] else '불충족'} (답: {cb.get('response', '')[:160]})")
    return "\n".join(out)


def rows_for(s: dict, errors_by_turn: dict) -> list[dict]:
    from multiturn.scenario_v2 import suspect_reasons
    out = []
    for t in s["turns"]:
        out.append({
            "row_id": f"{s['scenario_id']}#{t['turn']:02d}", "scenario_id": s["scenario_id"], "turn": t["turn"],
            "turn_type": t["turn_type"], "type": t["type"], "depends_on": ",".join(map(str, t["depends_on"])),
            "recall_distance": t.get("recall_distance"), "evidence_pages": ", ".join(t["evidence_pages"]),
            "question": t["question"], "asks": " / ".join(t.get("asks") or []),
            "standalone_question": t.get("standalone_question", ""), "answer": t["answer"],
            "key_facts": _facts(t), "evidence": _evidence(t), "update_info": _update_info(t),
            "closed_book_knowledge": _closed_book(t, "knowledge"), "closed_book_grounded": _closed_book(t, "grounded"),
            "alt_judgments": _alt_judgments(t),
            "suspect": "\n".join(suspect_reasons(s, t)),
            "review_flags": "; ".join(((t.get("review") or {}).get("flags") or [])
                                      + ([t["review"]["note"]] if (t.get("review") or {}).get("note") else [])),
            "auto_check": "\n".join(errors_by_turn.get(t["turn"], [])) or "OK",
            # 이미 받은 검수 값 (시나리오 JSON 의 review 필드) 은 채워 둔다
            **{c: str((t.get("review") or {}).get(c, "")) for c in REVIEW_COLS},
        })
    return out


def errors_by_turn(s: dict, corpus) -> tuple[dict, list[str]]:
    from multiturn.scenario_v2 import check_grounding_v2, topic_warnings, validate_scenario_v2
    by, whole, warns = {}, [], []
    for e in validate_scenario_v2(s) + check_grounding_v2(s, corpus, warns) + warns + topic_warnings(s):
        marker = f"{s['scenario_id']} 턴 "
        if e.startswith(marker):
            k = int(e[len(marker):].split(":")[0].split(" ")[0])
            by.setdefault(k, []).append(e[len(marker):])
        else:
            whole.append(e)
    return by, whole


TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>multiturn-v2 검수</title>
<style>
:root{--bg:#f6f6f3;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e2e1dc;--acc:#2f5bd3;--warn:#b5551d;--ok:#1f8a4c;--tag:#eef1fb;--code:#f1f0ec}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--card:#212125;--ink:#ececea;--mute:#9b9b96;--line:#34343a;--acc:#7c9cff;--warn:#f0a070;--ok:#4cc27f;--tag:#262c40;--code:#2a2a2f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif}
.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
.bar{max-width:1000px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
h1{font-size:17px;margin:0 8px 0 0} main{max-width:1000px;margin:0 auto;padding:12px 16px 80px}
select,button,input,textarea{font:inherit;color:inherit}
select,input{padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card)}
button{padding:5px 12px;border:1px solid var(--acc);border-radius:6px;background:var(--acc);color:#fff;cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:12px 0}
.head{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline;margin-bottom:6px}
.id{font-weight:600}.pill{font-size:12px;padding:1px 8px;border-radius:99px;background:var(--tag)}
.k{color:var(--mute);font-size:13px;margin-top:8px}.v{white-space:pre-wrap;word-break:break-word}
.v.code{background:var(--code);border-radius:6px;padding:6px 8px;font:13px/1.5 ui-monospace,Consolas,monospace}
.warn{color:var(--warn)}.okc{color:var(--ok)}
.rev{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line)}
.rev label{font-size:14px}.rev textarea{width:100%;min-height:44px;border:1px solid var(--line);border-radius:6px;background:var(--card);padding:6px}
.scen{font-size:16px;margin:26px 0 4px}.note{color:var(--mute);font-size:13px}
</style></head><body>
<div class="top"><div class="bar"><h1>multiturn-v2 검수</h1>
<label>검수자 <input id="who" size="6" placeholder="A"></label>
<label>시나리오 <select id="scn"><option value="">전체</option></select></label>
<label>보기 <select id="flt"><option value="">전체</option><option value="todo">미검수만</option><option value="warn">자동 검사 경고만</option><option value="sus">의심 턴만</option></select></label>
<span id="cnt" class="note"></span><button id="dl">CSV 내려받기</button></div></div>
<main><p class="note">턴마다 (1) standalone_question 이 원래 질문과 같은 사실을 묻는지, (2) 판정(OK / 수정 필요 / 제외)과 메모를 적는다.
입력은 이 브라우저에 자동 저장된다. 모델 성능을 보고 제외하지 않는다 (근거 오류·closed-book 이 아닌 이유는 메모에 적는다).</p>
<div id="list"></div></main>
<script>
const ROWS = __ROWS__; const COLS = __COLS__; const WHOLE = __WHOLE__; const KEY = "mt2review:" + __NAME__;
let st = {}; try { st = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { st = {}; }
for (const r of ROWS) { for (const c of ["standalone_same_fact", "alt_judge_label", "verdict", "memo"]) {
  if (r[c] && !(st[r.row_id] || {})[c]) { st[r.row_id] = st[r.row_id] || {}; st[r.row_id][c] = r[c]; } } }
const scnEl = document.getElementById("scn");
for (const id of [...new Set(ROWS.map(r => r.scenario_id))]) { const o = document.createElement("option"); o.value = o.textContent = id; scnEl.appendChild(o); }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const whoEl = document.getElementById("who"); whoEl.value = st.__who || ""; whoEl.oninput = () => { st.__who = whoEl.value; save(); };
function field(k, v, code) { return v ? `<div class="k">${k}</div><div class="v${code ? " code" : ""}">${esc(v)}</div>` : ""; }
function render() {
  const f = document.getElementById("flt").value, sc = scnEl.value; let html = "", last = "", done = 0;
  for (const r of ROWS) {
    const s = st[r.row_id] || {}; if (s.verdict) done++;
    if (sc && r.scenario_id !== sc) continue;
    if (f === "todo" && s.verdict) continue; if (f === "warn" && r.auto_check === "OK") continue; if (f === "sus" && !r.suspect) continue;
    if (r.scenario_id !== last) { last = r.scenario_id; html += `<div class="scen">${esc(last)}</div>` + (WHOLE[last] || []).map(w => `<div class="note warn">${esc(w)}</div>`).join(""); }
    const opt = (name, vals) => vals.map(v => `<label><input type="radio" name="${name}-${r.row_id}" value="${v}" ${s[name] === v ? "checked" : ""} data-id="${r.row_id}" data-k="${name}"> ${v}</label>`).join(" ");
    html += `<div class="card"><div class="head"><span class="id">턴 ${r.turn}</span><span class="pill">${esc(r.turn_type)}</span><span class="pill">${esc(r.type)}</span>
      <span class="note">depends_on [${esc(r.depends_on)}] · 거리 ${esc(r.recall_distance)}${r.evidence_pages ? " · 첨부 " + esc(r.evidence_pages) : ""}</span></div>
      ${field("질문", r.question)}${field("standalone_question (closed-book 용)", r.standalone_question)}${field("정답", r.answer)}
      ${field("key_facts [태그] / 대안", r.key_facts, true)}${field("근거 인용", r.evidence, true)}${field("update / same_doc", r.update_info)}
      ${field("묻는 사항 (asks)", r.asks)}${field("closed-book knowledge (사전 지식, UNKNOWN 허용)", r.closed_book_knowledge)}
      ${field("closed-book grounded (실험 지시문, NOT FOUND 규칙)", r.closed_book_grounded)}${field("대안 붙은 판정 (fact_judge_v3)", r.alt_judgments)}${r.suspect ? `<div class="k">먼저 볼 점 (자동 점검)</div><div class="v warn">${esc(r.suspect)}</div>` : ""}${field("검수 표시", r.review_flags)}<div class="k">자동 검사</div><div class="v ${r.auto_check === "OK" ? "okc" : "warn"}">${esc(r.auto_check)}</div>
      <div class="rev"><span>같은 사실을 묻는가: ${opt("standalone_same_fact", ["예", "아니오"])}</span>
      ${r.alt_judgments ? `<span>대안 판정이 맞는가: ${opt("alt_judge_label", ["맞음", "틀림"])}</span>` : ""}
      <span>판정: ${opt("verdict", ["OK", "수정 필요", "제외"])}</span>
      <textarea placeholder="메모" data-id="${r.row_id}" data-k="memo">${esc(s.memo || "")}</textarea></div></div>`;
  }
  document.getElementById("list").innerHTML = html;
  document.getElementById("cnt").textContent = `판정 ${done} / ${ROWS.length}`;
}
document.addEventListener("input", e => { const id = e.target.dataset.id, k = e.target.dataset.k; if (!id) return;
  st[id] = st[id] || {}; st[id][k] = e.target.value; st[id].reviewer = st.__who || ""; save();
  if (k === "verdict") { const s = window.scrollY; render(); window.scrollTo(0, s); } });
document.getElementById("flt").onchange = render; scnEl.onchange = render;
document.getElementById("dl").onclick = () => {
  const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
  const lines = [COLS.join(",")].concat(ROWS.map(r => COLS.map(c => q((st[r.row_id] || {})[c] ?? r[c])).join(",")));
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], {type: "text/csv"}));
  a.download = __NAME__ + ".csv"; a.click(); };
render();
</script></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="multiturn-v2 검수 시트")
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--name", default="multiturn_v2_review")
    ap.add_argument("--out-dir", default=str(CFG.root / "docs" / "review"))
    a = ap.parse_args(argv)
    from corpus import load_corpus
    corpus = load_corpus()
    rows, whole = [], {}
    for path in a.scenarios:
        s = json.loads(Path(path).read_text(encoding="utf-8"))
        by, w = errors_by_turn(s, corpus)
        rows += rows_for(s, by)
        whole[s["scenario_id"]] = w
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{a.name}.csv", "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=COLUMNS)
        wr.writeheader()
        wr.writerows(rows)
    page = (TEMPLATE.replace("__ROWS__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__COLS__", json.dumps(COLUMNS)).replace("__WHOLE__", json.dumps(whole, ensure_ascii=False))
            .replace("__NAME__", json.dumps(a.name)))
    (out / f"{a.name}.html").write_text(page, encoding="utf-8")
    print(f"저장: {out / (a.name + '.csv')}, {out / (a.name + '.html')} ({len(rows)}행)")


if __name__ == "__main__":
    main()
