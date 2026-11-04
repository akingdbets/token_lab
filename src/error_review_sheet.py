"""
오답 검수 시트 보강: 정답 핵심어 위치 발췌와 HTML 보기 (API 호출 없음)

test_error_review.csv (test_v1 압축 오답 50 trial) 에 열을 더하고, 같은 내용을 한 화면에서 보는 HTML 을 만든다.
이미 채운 "사람 분류"·"메모" 는 그대로 둔다. 자동 분류(A/B/C)는 라벨링 파일에서 빼고 _key.csv 로 옮긴다
(검수자가 자동 분류를 보고 맞추지 않게).

    EVAL_DIR=data/evalsets/claude-v1 python src/error_review_sheet.py results/runs/20261102-205826

더하는 열
    문맥 내 정답 위치   압축 문맥에서 정답 핵심어(normalized-v2, core_needles)가 나온 곳마다 앞뒤 CONTEXT_WORDS 단어 발췌.
                       [코드] 은 ``` 코드 블록 안, [설명] 은 그 밖. 핵심어는 【 】 로 감싼다. 없으면 "없음"
    원문 내 정답 위치   같은 방식으로 none 문맥에서
    압축 문맥 파일·원문 문맥 파일   run 의 contexts/ 파일 경로 (저장소 기준, results/ 는 커밋되지 않음)
출력
    docs/results/test_error_review.csv       라벨링 시트 (자동 분류 열 없음)
    docs/results/test_error_review_key.csv   qid, 압축기, 자동 분류 (label_report.py 교차표용)
    docs/results/test_error_review.html      행마다 질문·정답·답변·근거 원문/압축 후·두 발췌, 핵심어 형광 표시
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core_match import _core_tokens, core_needles
from experiment import load_items
from judge_agreement import read_sheet
from redundancy import code_ranges, needle_spans

CONTEXT_WORDS = 20
SHEET_FIELDS = ["qid", "qtype", "압축기", "질문", "정답", "모델 답변", "근거 인용문 원문", "압축 후 같은 구절",
                "문맥 내 정답 위치", "원문 내 정답 위치", "압축 문맥 파일", "원문 문맥 파일", "사람 분류", "메모"]
KEY_FIELDS = ["qid", "압축기", "자동 분류"]
_WORD = re.compile(r"\S+")


def core_spans(text: str, item: dict) -> list[tuple[int, int]]:
    """정답 핵심어가 나온 (시작, 끝) 문자 위치. 여러 핵심어의 겹치는 위치는 하나로 합친다."""
    toks = _core_tokens(text)
    spans = sorted(sp for n in core_needles(item) for sp in needle_spans(text, n, toks))
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def excerpts(text: str, item: dict, words: int = CONTEXT_WORDS) -> list[dict]:
    """핵심어 위치마다 {where: 코드|설명, before, match, after}. 가까운 위치는 한 발췌로 합친다."""
    spans = core_spans(text, item)
    code = code_ranges(text)
    ws = [(m.start(), m.end()) for m in _WORD.finditer(text)]
    out = []
    for s, e in spans:
        i = next((k for k, (a, b) in enumerate(ws) if b > s), len(ws))
        j = next((k for k, (a, b) in enumerate(ws) if b >= e), len(ws) - 1)
        lo = ws[max(0, i - words)][0] if ws else 0
        hi = ws[min(len(ws) - 1, j + words)][1] if ws else len(text)
        where = "코드" if any(a <= s < b for a, b in code) else "설명"
        if out and lo <= out[-1]["hi"] and out[-1]["where"] == where:     # 겹치는 발췌는 합친다
            out[-1]["hi"] = max(out[-1]["hi"], hi)
            out[-1]["spans"].append((s, e))
            continue
        out.append({"where": where, "lo": lo, "hi": hi, "spans": [(s, e)]})
    for x in out:
        x["text"] = text[x["lo"]:x["hi"]]
        x["marks"] = [(s - x["lo"], e - x["lo"]) for s, e in x["spans"]]
    return out


def plain(x: dict) -> str:
    t, last, parts = x["text"], 0, []
    for s, e in x["marks"]:
        parts += [t[last:s], "【", t[s:e], "】"]
        last = e
    parts.append(t[last:])
    return f"[{x['where']}] …" + re.sub(r"\s+", " ", "".join(parts)).strip() + "…"


def cell(exs: list[dict]) -> str:
    if not exs:
        return "없음"
    head = f"({len(exs)}곳) " if len(exs) > 1 else ""
    return head + "\n".join(plain(x) for x in exs)


def marked_html(text: str, marks: list[tuple[int, int]]) -> str:
    last, out = 0, []
    for s, e in marks:
        out += [html.escape(text[last:s]), "<mark>", html.escape(text[s:e]), "</mark>"]
        last = e
    out.append(html.escape(text[last:]))
    return "".join(out)


def hl(text: str, item: dict) -> str:
    return marked_html(text, core_spans(text, item)) if text else ""


def excerpt_html(exs: list[dict], n_label: str) -> str:
    if not exs:
        return '<p class="none">없음</p>'
    return (f'<p class="count">{len(exs)}곳 ({n_label})</p>'
            + "".join(f'<div class="ex"><span class="tag {"code" if x["where"] == "코드" else "prose"}">{x["where"]}</span>'
                      f'<pre>…{marked_html(x["text"], x["marks"])}…</pre></div>' for x in exs))


def page(rows: list[dict], run: str) -> str:
    cards = []
    for i, r in enumerate(rows, 1):
        it = r["_item"]
        quotes = r["근거 인용문 원문"].split("\n")
        comps = r["압축 후 같은 구절"].split("\n")
        pairs = "".join(f'<div class="pair"><div><h4>근거 원문</h4><pre>{hl(q, it)}</pre></div>'
                        f'<div><h4>압축 후</h4><pre>{hl(c, it)}</pre></div></div>'
                        for q, c in zip(quotes, comps + [""] * (len(quotes) - len(comps))))
        cards.append(f"""
<section class="card" id="r{i}">
  <header><span class="num">{i}</span><b>{html.escape(r['qid'])}</b><span class="pill">{html.escape(r['qtype'])}</span>
    <span class="pill comp">{html.escape(r['압축기'])}</span><a href="#r{i}">#</a></header>
  <dl>
    <dt>질문</dt><dd>{html.escape(r['질문'])}</dd>
    <dt>정답</dt><dd>{hl(r['정답'], it)}</dd>
    <dt>핵심어</dt><dd>{', '.join('<mark>' + html.escape(n) + '</mark>' for n in core_needles(it))}</dd>
    <dt>모델 답변</dt><dd><pre>{hl(r['모델 답변'], it)}</pre></dd>
  </dl>
  {pairs}
  <div class="pair">
    <div><h4>원문 내 정답 위치</h4>{excerpt_html(r['_raw_ex'], 'none 문맥')}<p class="file">{html.escape(r['원문 문맥 파일'])}</p></div>
    <div><h4>문맥 내 정답 위치</h4>{excerpt_html(r['_comp_ex'], '압축 문맥')}<p class="file">{html.escape(r['압축 문맥 파일'])}</p></div>
  </div>
  <p class="label">CSV <code>사람 분류</code>: 1 정답 구절 삭제 · 2 연결어·조건 삭제 · 3 표기 분해 · 4 정답 남음·추론 가능한데 틀림 · 5 기타</p>
</section>""")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>오답 검수 보기</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --fg:#1d1d1b; --muted:#6b6b66; --line:#e3e2dd; --mark:#ffe680; --code:#eef3ff; --prose:#eef8ee; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#18181a; --card:#222225; --fg:#ececea; --muted:#a0a09a; --line:#38383b;
  --mark:#7a6500; --code:#25304a; --prose:#243a27; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 system-ui, sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:22px; margin:0 0 6px; }} .intro {{ color:var(--muted); margin:0 0 20px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin:0 0 18px; }}
.card header {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:10px; }}
.card header a {{ margin-left:auto; color:var(--muted); text-decoration:none; }}
.num {{ font-variant-numeric:tabular-nums; color:var(--muted); min-width:2ch; }}
.pill {{ border:1px solid var(--line); border-radius:99px; padding:0 8px; font-size:13px; color:var(--muted); }}
dl {{ display:grid; grid-template-columns:7em 1fr; gap:4px 12px; margin:0 0 12px; }} dt {{ color:var(--muted); }} dd {{ margin:0; }}
pre {{ white-space:pre-wrap; word-break:break-word; margin:0; font:13px/1.5 ui-monospace, Consolas, monospace; }}
mark {{ background:var(--mark); color:inherit; border-radius:2px; padding:0 1px; }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:10px 0; }}
.pair > div {{ border:1px solid var(--line); border-radius:8px; padding:8px 10px; min-width:0; }}
h4 {{ margin:0 0 6px; font-size:13px; color:var(--muted); font-weight:600; }}
.ex {{ margin:0 0 8px; }} .tag {{ font-size:12px; border-radius:4px; padding:0 6px; }}
.tag.code {{ background:var(--code); }} .tag.prose {{ background:var(--prose); }}
.count, .file, .none, .label {{ color:var(--muted); font-size:12px; margin:4px 0; }} .file {{ word-break:break-all; }}
@media (max-width:720px) {{ .pair {{ grid-template-columns:1fr; }} dl {{ grid-template-columns:1fr; }} }}
</style></head>
<body><main>
<h1>test_v1 압축 오답 검수 ({len(rows)} trial)</h1>
<p class="intro">run <code>{html.escape(run)}</code>. 정답 핵심어(normalized-v2)를 <mark>형광</mark>으로 표시했다.
이 화면을 보며 <code>test_error_review.csv</code> 의 <b>사람 분류</b>만 채운다. 기준은 <code>labeling_guide.md</code> 2절.</p>
{''.join(cards)}
</main></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="test_v1 run 폴더 (contexts/ 가 있는 곳)")
    ap.add_argument("--sheet", default="docs/results/test_error_review.csv")
    ap.add_argument("--key", default="docs/results/test_error_review_key.csv")
    ap.add_argument("--html", default="docs/results/test_error_review.html")
    args = ap.parse_args()
    run = Path(args.run)
    items = {it["id"]: it for it in load_items("test", None, None)}
    rows = read_sheet(Path(args.sheet))
    key_rows = {(r["qid"], r["압축기"]): r for r in read_sheet(Path(args.key))} if Path(args.key).exists() else {}
    for r in rows:
        it = items[r["qid"]]
        comp_path = run / "contexts" / f"{r['qid']}.{r['압축기'].replace('>', '+')}.md"
        raw_path = run / "contexts" / f"{r['qid']}.none.md"
        r["_item"] = it
        r["_comp_ex"] = excerpts(comp_path.read_text(encoding="utf-8"), it)
        r["_raw_ex"] = excerpts(raw_path.read_text(encoding="utf-8"), it)
        r["문맥 내 정답 위치"] = cell(r["_comp_ex"])
        r["원문 내 정답 위치"] = cell(r["_raw_ex"])
        r["압축 문맥 파일"] = comp_path.as_posix()
        r["원문 문맥 파일"] = raw_path.as_posix()
        if "자동 분류" in r:                       # 처음 한 번: 라벨링 파일에서 _key.csv 로 옮긴다
            key_rows[(r["qid"], r["압축기"])] = {"qid": r["qid"], "압축기": r["압축기"], "자동 분류": r["자동 분류"]}
    with open(args.sheet, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(args.key, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KEY_FIELDS)
        w.writeheader()
        w.writerows(key_rows[(r["qid"], r["압축기"])] for r in rows)
    Path(args.html).write_text(page(rows, run.name), encoding="utf-8")
    none_comp = sum(not r["_comp_ex"] for r in rows)
    none_raw = sum(not r["_raw_ex"] for r in rows)
    print(f"행 {len(rows)}, 압축 문맥에 핵심어 없음 {none_comp}, 원문에도 없음 {none_raw}, "
          f"사람 분류 채워진 행 {sum(bool((r.get('사람 분류') or '').strip()) for r in rows)}")
    print("저장", args.sheet, args.key, args.html)


if __name__ == "__main__":
    main()
