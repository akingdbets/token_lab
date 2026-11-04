"""
judge 검증 세트(judge_check_test.csv)를 라벨링하기 쉬운 HTML 한 장으로 만든다 (API 호출 없음)

    python src/judge_check_viewer.py            # -> docs/results/judge_check_test.html

- judge 판정(_key.csv)은 읽지 않는다. 화면에도 없다 (블라인드).
- 브라우저에서 담당자를 고르고 O/X·메모를 채운다. 입력은 그 브라우저에 자동 저장된다.
- 다 채우면 "CSV 내려받기" 로 시트 전체(다른 담당자 라벨 포함)를 받아 judge_check_test.csv 를 바꾼다.
- 이미 시트에 있는 라벨(예: D 담당 20행)은 처음 열 때 채워져 있다.
"""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge_agreement import read_sheet

COLUMNS = ["row_id", "담당자", "qid", "유형", "설정", "압축 조건", "fact_idx", "질문", "핵심 사실", "참고 정답",
           "모델 답변", "human", "메모"]

TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>judge 검증 라벨링</title>
<style>
:root{--bg:#f6f6f3;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e2e1dc;--acc:#2f5bd3;--o:#1f8a4c;--x:#c2412d;
--obg:#e6f4ec;--xbg:#fbe9e6;--fact:#fff7d6;--code:#f1f0ec}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--card:#212125;--ink:#ececea;--mute:#9b9b96;
--line:#34343a;--acc:#7c9cff;--o:#4cc27f;--x:#f07a66;--obg:#1d3527;--xbg:#3a2220;--fact:#3a3420;--code:#2a2a2f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif}
.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
.bar{max-width:980px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
h1{font-size:17px;margin:0 8px 0 0}
select,button,textarea{font:inherit;color:inherit}
select{padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card)}
.prog{flex:1;min-width:160px;display:flex;align-items:center;gap:8px;font-size:13px;color:var(--mute)}
.track{flex:1;height:6px;background:var(--line);border-radius:3px;overflow:hidden}.fill{height:100%;background:var(--acc);width:0}
.btn{padding:5px 12px;border:1px solid var(--line);border-radius:6px;background:var(--card);cursor:pointer}
.btn.pri{background:var(--acc);border-color:var(--acc);color:#fff}
label.chk{font-size:13px;color:var(--mute);display:flex;gap:4px;align-items:center}
main{max-width:980px;margin:0 auto;padding:16px}
.guide{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin-bottom:16px;font-size:14px}
.guide summary{cursor:pointer;font-weight:600}.guide ul{margin:6px 0 0 18px;padding:0}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px;scroll-margin-top:80px}
.card.O{border-left-color:var(--o)}.card.X{border-left-color:var(--x)}.card.cur{outline:2px solid var(--acc);outline-offset:2px}
.card.ro{opacity:.82}
.head{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px;font-size:13px;color:var(--mute)}
.head b{color:var(--ink);font-size:15px}.pill{border:1px solid var(--line);border-radius:999px;padding:0 8px}
.k{font-size:12px;font-weight:600;color:var(--mute);margin:10px 0 2px;letter-spacing:.02em}
.q{margin:0}.fact{background:var(--fact);border-radius:6px;padding:8px 10px;font-weight:600}
.ref{color:var(--mute);margin:0}
.ans{background:var(--code);border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;margin:0;font:14px/1.55 ui-monospace,Consolas,"D2Coding",monospace;max-height:340px;overflow:auto}
.act{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start;margin-top:12px}
.ox{display:flex;gap:6px}.ox button{width:56px;height:40px;font-size:18px;font-weight:700;border:2px solid var(--line);border-radius:8px;background:var(--card);cursor:pointer}
.ox .o.on{background:var(--obg);border-color:var(--o);color:var(--o)}.ox .x.on{background:var(--xbg);border-color:var(--x);color:var(--x)}
textarea{flex:1;min-width:220px;min-height:40px;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--card);resize:vertical}
.hint{font-size:12px;color:var(--mute);margin-top:6px}.empty{color:var(--mute);text-align:center;padding:40px}
kbd{border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;font-size:12px}
@media (max-width:600px){.top{padding:8px 16px}h1{width:100%}.prog{min-width:100%}}
</style></head><body>
<div class="top"><div class="bar">
  <h1>judge 검증 라벨링</h1>
  <label>담당자 <select id="who"></select></label>
  <label class="chk"><input type="checkbox" id="todo"> 안 채운 행만</label>
  <div class="prog"><span id="cnt"></span><div class="track"><div class="fill" id="fill"></div></div></div>
  <button class="btn pri" id="dl">CSV 내려받기</button>
</div></div>
<main>
<details class="guide" open><summary>라벨 기준 (labeling_guide.md 1절)</summary>
<p><b>모델 답변이 이 핵심 사실을 의미상 전달했으면 O, 아니면 X.</b></p>
<ul><li>표현이 달라도 의미가 같으면 <b>O</b></li><li>관련 단어만 있고 사실을 말하지 않으면 <b>X</b></li><li>사실과 모순되면 <b>X</b></li>
<li>답변의 다른 부분이 틀렸더라도 이 핵심 사실을 전달했으면 O (사실 하나씩 본다)</li>
<li>사실을 말하면서 "문서에 없다"는 말을 덧붙여도, 사실을 전달했으면 O</li>
<li>한 행씩 독립으로 본다. 판단이 어려우면 가장 가까운 값을 넣고 메모에 이유를 쓴다</li></ul>
<p class="hint">judge 판정은 이 화면에 없다 (블라인드). 단축키: <kbd>O</kbd> / <kbd>X</kbd> 라벨 후 다음 행, <kbd>J</kbd>/<kbd>K</kbd> 다음/이전, <kbd>M</kbd> 메모 칸.
입력은 이 브라우저에 자동 저장된다. 끝나면 <b>CSV 내려받기</b>로 받은 파일로 <code>docs/results/judge_check_test.csv</code> 를 바꾼다.</p>
</details>
<div id="list"></div>
</main>
<script>
const ROWS = __ROWS__;
const COLS = __COLS__;
const KEY = "judge_check_test_labels_v1";
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
for (const r of ROWS) { const s = saved[r.row_id]; if (s) { r.human = s.human; r["메모"] = s.memo; } }
const save = () => { try { const o = {}; for (const r of ROWS) o[r.row_id] = {human: r.human, memo: r["메모"]};
  localStorage.setItem(KEY, JSON.stringify(o)); } catch (e) {} };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const who = document.getElementById("who"), todo = document.getElementById("todo"), list = document.getElementById("list");
const people = [...new Set(ROWS.map(r => r["담당자"]))].sort();
who.innerHTML = people.map(p => `<option value="${p}">${p} (${ROWS.filter(r => r["담당자"] === p).length}행)</option>`).join("")
  + `<option value="*">전체</option>`;
let pref = {}; try { pref = JSON.parse(localStorage.getItem(KEY + "_ui") || "{}"); } catch (e) {}
who.value = pref.who || "A"; todo.checked = !!pref.todo;
let cur = 0, shown = [];
function render() {
  try { localStorage.setItem(KEY + "_ui", JSON.stringify({who: who.value, todo: todo.checked})); } catch (e) {}
  shown = ROWS.filter(r => (who.value === "*" || r["담당자"] === who.value) && (!todo.checked || !r.human));
  list.innerHTML = shown.length ? shown.map((r, i) => `
  <section class="card ${r.human}" id="c${i}" data-i="${i}">
    <div class="head"><b>${esc(r.row_id)}</b><span>${esc(r.qid)} · 사실 ${esc(r.fact_idx)}</span>
      <span class="pill">${esc(r["유형"])}</span><span class="pill">${esc(r["설정"])}</span><span class="pill">${esc(r["압축 조건"])}</span>
      <span class="pill">담당 ${esc(r["담당자"])}</span></div>
    <div class="k">질문</div><p class="q">${esc(r["질문"])}</p>
    <div class="k">핵심 사실 (이것만 판정)</div><div class="fact">${esc(r["핵심 사실"])}</div>
    <div class="k">참고 정답</div><p class="ref">${esc(r["참고 정답"])}</p>
    <div class="k">모델 답변</div><pre class="ans">${esc(r["모델 답변"])}</pre>
    <div class="act"><div class="ox"><button class="o ${r.human === "O" ? "on" : ""}" data-v="O" title="O">O</button>
      <button class="x ${r.human === "X" ? "on" : ""}" data-v="X" title="X">X</button></div>
      <textarea placeholder="메모 (판단이 어려웠던 이유 등)">${esc(r["메모"])}</textarea></div>
  </section>`).join("") : `<p class="empty">보여 줄 행이 없다.</p>`;
  cur = Math.min(cur, Math.max(shown.length - 1, 0)); mark(false); progress();
}
function progress() {
  const mine = ROWS.filter(r => who.value === "*" || r["담당자"] === who.value), done = mine.filter(r => r.human).length;
  const o = mine.filter(r => r.human === "O").length;
  document.getElementById("cnt").textContent = `${done}/${mine.length} 채움 (O ${o} · X ${done - o})`;
  document.getElementById("fill").style.width = (mine.length ? 100 * done / mine.length : 0) + "%";
}
function mark(scroll) {
  document.querySelectorAll(".card").forEach(c => c.classList.toggle("cur", +c.dataset.i === cur));
  const c = document.getElementById("c" + cur); if (scroll && c) c.scrollIntoView({block: "start", behavior: "smooth"});
}
function setLabel(i, v) {
  const r = shown[i]; if (!r) return;
  r.human = r.human === v ? "" : v; save();
  const c = document.getElementById("c" + i);
  c.classList.remove("O", "X"); if (r.human) c.classList.add(r.human);
  c.querySelectorAll(".ox button").forEach(b => b.classList.toggle("on", b.dataset.v === r.human));
  progress();
}
list.addEventListener("click", e => {
  const b = e.target.closest(".ox button"), c = e.target.closest(".card"); if (!c) return;
  cur = +c.dataset.i; mark(false); if (b) setLabel(cur, b.dataset.v);
});
list.addEventListener("input", e => {
  if (e.target.tagName !== "TEXTAREA") return;
  const r = shown[+e.target.closest(".card").dataset.i]; r["메모"] = e.target.value; save();
});
document.addEventListener("keydown", e => {
  if (e.target.tagName === "TEXTAREA") { if (e.key === "Escape") e.target.blur(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey || e.target.tagName === "SELECT") return;
  const k = e.key.toLowerCase();
  if (k === "o" || k === "x") { setLabel(cur, k.toUpperCase()); if (cur < shown.length - 1) { cur++; mark(true); } }
  else if (k === "j") { cur = Math.min(cur + 1, shown.length - 1); mark(true); }
  else if (k === "k") { cur = Math.max(cur - 1, 0); mark(true); }
  else if (k === "m") { const t = document.querySelector(`#c${cur} textarea`); if (t) { e.preventDefault(); t.focus(); } }
  else return;
  e.preventDefault();
});
who.onchange = () => { cur = 0; render(); }; todo.onchange = () => { cur = 0; render(); };
document.getElementById("dl").onclick = () => {
  const q = v => { v = String(v ?? ""); return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const csv = "﻿" + [COLS.join(","), ...ROWS.map(r => COLS.map(c => q(r[c])).join(","))].join("\r\n") + "\r\n";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
  a.download = "judge_check_test.csv"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
render();
</script></body></html>
"""


def build(rows: list[dict]) -> str:
    data = [{c: r.get(c, "") or "" for c in COLUMNS} for r in rows]
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__ROWS__", js).replace("__COLS__", json.dumps(COLUMNS, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default="docs/results/judge_check_test.csv")
    ap.add_argument("--out", default="docs/results/judge_check_test.html")
    args = ap.parse_args()
    rows = read_sheet(Path(args.sheet))
    missing = [c for c in COLUMNS if c not in rows[0]]
    if missing:
        sys.exit(f"시트에 열이 없습니다: {missing}")
    Path(args.out).write_text(build(rows), encoding="utf-8")
    done = sum(bool((r.get("human") or "").strip()) for r in rows)
    print(f"저장: {args.out} ({len(rows)}행, 라벨 채워진 행 {done})")


if __name__ == "__main__":
    main()
