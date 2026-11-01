"""
문서 중복도와 압축 강건성: 압축이 근거를 지워도 맞히는 것이 정답이 문맥 여러 곳에 있어서인지 (API 호출 없음)

저장된 문맥(contexts/<qid>.<압축기>.md)과 trials.jsonl, 평가셋만 쓴다.

    EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/<run_id> [<run_id2> ...] [--json out.json]

여러 run 을 주면 trial 을 합친다 (같은 설정을 반복한 run 묶음용). 중복도는 첫 run 의 none 문맥으로 잰다.

1. 중복도: none 문맥에서 정답 핵심어가 나오는 위치 수 (experiment.core_matches 와 같은 매칭, CORE_MATCH_VERSION)
       짧은 답    정답이 나오는 위치 수
       긴 답      key_entities 마다 위치 수를 세고, 절반 규칙(ceil(n/2) 개)을 채우는 데 필요한 k 번째로 많은 개체의
                  위치 수. "핵심어 있음" 판정을 깨려면 지워야 하는 최소 위치 수에 가깝다
       설명 문장 / 코드 블록 은 위치가 ``` 펜스 안이면 코드, 밖이면 설명 (제목·목록·인라인 코드는 설명).
       긴 답의 설명·코드 값은 그 위치만으로 k 번째 값을 다시 구한 것이라 합이 전체와 다를 수 있다
       0 = none 에서도 안 잡힘 (정답을 문장으로 바꿔 쓴 문항). 이 지표로 못 재므로 비교에서 따로 둔다
       근거 밖 = 근거 인용문 자리(none 문맥에서 인용문이 가장 잘 맞는 구간)가 아닌 위치만 센 값
2. trial 상태 (근거 보존율은 evidence_retention.item_retention, 경계는 memory_suspect.EVIDENCE_LOW)
       a  근거 보존율 >= EVIDENCE_LOW                      근거 인용문이 남음
       b  근거 보존율 <  EVIDENCE_LOW, 핵심어 있음          근거는 사라졌지만 핵심어가 다른 위치에 남음
          남은 위치는 근거 자리 밖에서만 센다: code / prose / both (코드만으로도 설명만으로도 채움) /
          mixed (둘을 합쳐야 채움) / evidence (근거 자리에 남은 것을 빼면 못 채움: 인용문은 지워졌는데 정답 단어만 남음)
          압축 문맥의 위치는 none 문맥과 단어 정렬(difflib, 압축은 지우기만 하므로)해서 근거 자리인지 본다
       c  근거 보존율 <  EVIDENCE_LOW, 핵심어 없음
3. 중복도 1 vs 2 이상으로 나눠 압축기별·유형별 정확도. 정답(accuracy >= 0.5) trial 수의 Fisher 정확 검정(양측)도 낸다.
   여러 run 을 합치면 같은 문항의 trial 이 독립이 아니라 p 는 참고값이다
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import json
import re
from math import comb
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_retention import item_retention
from experiment import (CORE_MATCH_VERSION, _core_tokens, _strip_article, core_matches, is_not_found,
                        iter_normalized, load_items)
from grader import is_short, word_tokens
from memory_suspect import EVIDENCE_LOW

_WORD = re.compile(r"[a-z0-9_]+")  # grader.word_tokens 와 같은 토큰 (위치 포함)
STATES = ("a", "b", "c")
WHERE = ("code", "prose", "both", "mixed", "evidence")


def code_ranges(context: str) -> list[tuple[int, int]]:
    """``` 펜스 코드 블록의 (시작, 끝) 문자 위치. 닫히지 않은 펜스는 문맥 끝까지."""
    ranges, start, pos = [], None, 0
    for line in context.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            if start is None:
                start = pos
            else:
                ranges.append((start, pos + len(line)))
                start = None
        pos += len(line)
    if start is not None:
        ranges.append((start, pos))
    return ranges


def needle_spans(context: str, needle: str, toks: list | None = None) -> list[tuple[int, int]]:
    """needle 이 나오는 위치들. core_matches 와 같이 정규화 매칭 또는 단어 연속 일치, 겹치는 위치는 하나로 센다."""
    needle = _strip_article(needle)
    spans = list(iter_normalized(context, needle, toks))
    want = word_tokens(needle)
    if want:
        words = list(_WORD.finditer(context.lower()))
        for i in range(len(words) - len(want) + 1):
            if [m.group() for m in words[i:i + len(want)]] == want:
                s, e = words[i].start(), words[i + len(want) - 1].end()
                if not any(s < b and a < e for a, b in spans):
                    spans.append((s, e))
    return sorted(spans)


def quote_window(quote: list[str], ctx: list[str]) -> tuple[int, int] | None:
    """인용문이 ctx 단어열에서 가장 잘 맞는 구간 [시작, 끝) (evidence_retention.quote_kept 와 같은 점수)."""
    if not quote or not ctx:
        return None
    # (점수, 구간 시작). 0 행은 어디서든 시작할 수 있다
    prev = [(0, j) for j in range(len(ctx) + 1)]
    best = (0, 0, 0)
    for q in quote:
        cur = [(0, 0)] * (len(ctx) + 1)
        cur[0] = (0, 0)
        for j, c in enumerate(ctx, 1):
            cands = [prev[j], (cur[j - 1][0] - 1, cur[j - 1][1]), (0, j)]
            if q == c:
                cands.append((prev[j - 1][0] + 1, prev[j - 1][1] if prev[j - 1][0] > 0 else j - 1))
            cur[j] = max(cands, key=lambda x: x[0])
            if q == c and cur[j][0] > best[0]:
                best = (cur[j][0], cur[j][1], j)
        prev = cur
    return (best[1], best[2]) if best[0] > 0 else None


def evidence_words(raw: str, item: dict) -> set[int]:
    """none 문맥에서 근거 인용문 자리의 단어 번호들."""
    ctx = word_tokens(raw)
    out = set()
    for e in item.get("evidence") or []:
        w = quote_window(word_tokens(e.get("quote") or ""), ctx)
        if w:
            out.update(range(*w))
    return out


class WordMap:
    """문맥 문자 위치 → 단어 번호, 그리고 압축 문맥 단어 번호 → none 문맥 단어 번호."""

    def __init__(self, context: str, raw: str | None = None):
        self.starts = [m.start() for m in _WORD.finditer(context.lower())]
        self.to_raw = None
        if raw is not None:
            a, b = word_tokens(context), word_tokens(raw)
            self.to_raw = {}
            for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
                for k in range(blk.size):
                    self.to_raw[blk.a + k] = blk.b + k
            self.mapped = sorted(self.to_raw)

    def raw_words(self, char_pos: int) -> list[int]:
        """char_pos 의 단어에 대응하는 none 문맥 단어 번호. 정렬에서 빠진 단어(압축이 식별자를 쪼갬 등)는
        앞뒤로 가장 가까운 정렬된 단어 둘."""
        i = bisect.bisect_right(self.starts, char_pos) - 1
        if self.to_raw is None:
            return [i]
        if i in self.to_raw:
            return [self.to_raw[i]]
        k = bisect.bisect_left(self.mapped, i)
        return [self.to_raw[self.mapped[j]] for j in (k - 1, k) if 0 <= j < len(self.mapped)]


def core_positions(context: str, item: dict, keep=None) -> dict:
    """정답 핵심어 위치 수: total / prose / code (짧은 답은 정답, 긴 답은 절반 규칙의 k 번째 개체 값).
    keep(문자 위치) 가 주어지면 그 위치만 센다."""
    toks, code = _core_tokens(context), code_ranges(context)

    def count(needle):
        spans = [sp for sp in needle_spans(context, needle, toks) if keep is None or keep(sp[0])]
        c = sum(any(a <= s < b for a, b in code) for s, _ in spans)
        return {"total": len(spans), "code": c, "prose": len(spans) - c}

    answer = item["answer"]
    if is_short(answer):
        return count(answer)
    ents = [e for e in (item.get("key_entities") or [answer]) if _core_tokens(e)]
    if not ents:
        return {"total": 0, "code": 0, "prose": 0}
    per = [count(e) for e in ents]
    k = -(-len(ents) // 2)
    return {key: sorted((p[key] for p in per), reverse=True)[k - 1] for key in ("total", "code", "prose")}


def outside_evidence(context: str, raw: str, ev_words: set[int]):
    """문자 위치가 근거 자리 밖인지 판정하는 함수 (context 가 raw 면 정렬 없이)."""
    wm = WordMap(context, None if context == raw else raw)

    def keep(char_pos):
        return not any(w in ev_words for w in wm.raw_words(char_pos))
    return keep


def where_left(pos: dict) -> str:
    if pos["code"] and pos["prose"]:
        return "both"
    if pos["code"]:
        return "code"
    if pos["prose"]:
        return "prose"
    return "mixed" if pos["total"] else "evidence"


def trial_state(item: dict, context: str, raw: str, ev_words: set[int]) -> dict:
    quotes = [e["quote"] for e in item.get("evidence") or [] if e.get("quote")]
    ev = item_retention(context, quotes)
    evidence = ev["retention"] if ev else None
    core = core_matches(context, item)[0]
    if evidence is not None and evidence >= EVIDENCE_LOW:
        return {"state": "a", "evidence": evidence, "core": core, "where": None}
    if not core:
        return {"state": "c", "evidence": evidence, "core": False, "where": None}
    pos = core_positions(context, item, outside_evidence(context, raw, ev_words))
    return {"state": "b", "evidence": evidence, "core": True, "where": where_left(pos)}


def group(redundancy: int) -> str:
    return "0" if redundancy == 0 else "1" if redundancy == 1 else "2+"


def load_rows(run_dirs: list[Path], items: dict) -> tuple[dict, list[dict]]:
    """(문항별 중복도, trial 행). 중복도는 첫 run 의 none 문맥 (없으면 그 문항이 있는 다음 run)."""
    red, raws, rows = {}, {}, []
    for run in run_dirs:
        for line in (run / "trials.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            t = json.loads(line)
            item = items.get(t["qid"])
            if item is None:
                sys.exit(f"평가셋에 없는 문항입니다: {t['qid']} (EVAL_DIR 확인)")
            if t["qid"] not in red:
                raw_file = run / "contexts" / f"{t['qid']}.none.md"
                if not raw_file.exists():
                    sys.exit(f"none 문맥 파일이 없습니다: {raw_file}")
                raw = raw_file.read_text(encoding="utf-8")
                ev_words = evidence_words(raw, item)
                out = core_positions(raw, item, outside_evidence(raw, raw, ev_words))
                raws[t["qid"]] = (raw, ev_words)
                red[t["qid"]] = {"qid": t["qid"], "qtype": t["qtype"], "short": is_short(item["answer"]),
                                 **core_positions(raw, item), "outside": out["total"]}
            ctx = run / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md"
            if not ctx.exists():
                sys.exit(f"문맥 파일이 없습니다: {ctx}")
            rows.append({"run_id": run.name, "qid": t["qid"], "qtype": t["qtype"], "compressor": t["compressor"],
                         "answer_accuracy": t.get("answer_accuracy"),
                         "not_found": is_not_found(t.get("response") or ""),
                         **trial_state(item, ctx.read_text(encoding="utf-8"), *raws[t["qid"]])})
    for r in rows:
        r["redundancy"] = red[r["qid"]]["total"]
        r["group"] = group(r["redundancy"])
    return red, rows


def stats(rs: list[dict]) -> dict:
    acc = [r["answer_accuracy"] for r in rs if r["answer_accuracy"] is not None]
    return {"trials": len(rs), "items": len({r["qid"] for r in rs}),
            "accuracy": round(sum(acc) / len(acc), 4) if acc else None,
            "not_found_rate": round(sum(r["not_found"] for r in rs) / len(rs), 4) if rs else None,
            "correct": sum((r["answer_accuracy"] or 0) >= 0.5 for r in rs)}


def fisher_p(a: int, b: int, c: int, d: int) -> float:
    """2x2 [[a, b], [c, d]] 의 Fisher 정확 검정 양측 p (확률이 관측값 이하인 표의 합)."""
    r1, c1, n = a + b, a + c, a + b + c + d

    def prob(x):
        return comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)
    obs = prob(a)
    return min(1.0, sum(prob(x) for x in range(max(0, r1 + c1 - n), min(r1, c1) + 1) if prob(x) <= obs * (1 + 1e-9)))


def _f(x, digits=3):
    return "-" if x is None else f"{x:.{digits}f}"


def report(red: dict, rows: list[dict], runs: list[Path]) -> tuple[str, dict]:
    comps = list(dict.fromkeys(r["compressor"] for r in rows))
    qtypes = sorted({r["qtype"] for r in rows})
    out = {"runs": [r.as_posix() for r in runs], "core_match_version": CORE_MATCH_VERSION,
           "evidence_low": EVIDENCE_LOW, "redundancy": red, "states": {}, "by_group": {}, "by_qtype": {}}
    L = [f"## {', '.join(r.name for r in runs)}  ({CORE_MATCH_VERSION}, 근거 남음 >= {EVIDENCE_LOW})", ""]

    # 1. 중복도
    L += ["### 1. 문항별 중복도 (none 문맥)", "",
          "| 중복도 | 문항 수 | 설명에만 | 코드에만 | 둘 다 | 근거 밖 0 (근거 자리에만 있음) |", "|---|---|---|---|---|---|"]
    for g in ("0", "1", "2+"):
        qs = [q for q in red.values() if group(q["total"]) == g]
        L.append(f"| {g} | {len(qs)} | {sum(q['prose'] > 0 and not q['code'] for q in qs)} "
                 f"| {sum(q['code'] > 0 and not q['prose'] for q in qs)} | {sum(q['code'] > 0 and q['prose'] > 0 for q in qs)} "
                 f"| {sum(q['outside'] == 0 for q in qs)} |")
    L += ["", "| qid | 유형 | 답 | 위치 수 | 설명 | 코드 | 근거 밖 |", "|---|---|---|---|---|---|---|"]
    for q in sorted(red.values(), key=lambda q: (-q["total"], q["qid"])):
        L.append(f"| {q['qid']} | {q['qtype']} | {'짧은' if q['short'] else '긴'} | {q['total']} | {q['prose']} | {q['code']} | {q['outside']} |")

    # 2. 상태
    L += ["", "### 2. trial 상태별 (a 근거 남음 / b 근거 없음·핵심어 남음 / c 둘 다 없음)", "",
          "| 압축기 | 상태 | trial | 문항 | 정확도 | NOT FOUND | b 남은 위치 code/prose/both/mixed/evidence |",
          "|---|---|---|---|---|---|---|"]
    for c in comps:
        out["states"][c] = {}
        for s in STATES:
            rs = [r for r in rows if r["compressor"] == c and r["state"] == s]
            st = stats(rs)
            if s == "b":
                st["where"] = {w: stats([r for r in rs if r["where"] == w]) for w in WHERE}
            out["states"][c][s] = st
            if not rs:
                continue
            where = "/".join(str(st["where"][w]["trials"]) for w in WHERE) if s == "b" else ""
            L.append(f"| {c} | {s} | {st['trials']} | {st['items']} | {_f(st['accuracy'])} "
                     f"| {_f(st['not_found_rate'])} | {where} |")
    b_rows = [r for r in rows if r["state"] == "b"]
    if b_rows:
        L += ["", "b 상태의 남은 위치별 (모든 압축기 합계)", "", "| 남은 위치 | trial | 정확도 | NOT FOUND |", "|---|---|---|---|"]
        for w in WHERE:
            st = stats([r for r in b_rows if r["where"] == w])
            if st["trials"]:
                L.append(f"| {w} | {st['trials']} | {_f(st['accuracy'])} | {_f(st['not_found_rate'])} |")

    # 3. 중복도 그룹별
    def acc(c, g, qt=None):
        return stats([r for r in rows if r["compressor"] == c and r["group"] == g and (qt is None or r["qtype"] == qt)])

    L += ["", "### 3. 중복도 1 vs 2 이상 정확도 (괄호는 none 대비 차이, p 는 정답 trial 수의 Fisher 1 vs 2+)", "",
          "| 압축기 | 중복도 0 | 중복도 1 | 중복도 2+ | 정답 1 / 2+ | p |", "|---|---|---|---|---|---|"]
    for c in comps:
        cells = []
        for g in ("0", "1", "2+"):
            st, base = acc(c, g), acc("none", g)
            out["by_group"].setdefault(c, {})[g] = st
            d = "" if c == "none" or st["accuracy"] is None or base["accuracy"] is None \
                else f" ({st['accuracy'] - base['accuracy']:+.3f})"
            cells.append(f"{_f(st['accuracy'])}{d}, n={st['items']}" if st["trials"] else "-")
        g1, g2 = out["by_group"][c]["1"], out["by_group"][c]["2+"]
        pv = fisher_p(g1["correct"], g1["trials"] - g1["correct"], g2["correct"], g2["trials"] - g2["correct"]) \
            if g1["trials"] and g2["trials"] else None
        out["by_group"][c]["fisher_p"] = pv
        L.append(f"| {c} | " + " | ".join(cells) + f" | {g1['correct']}/{g1['trials']} / {g2['correct']}/{g2['trials']} "
                 f"| {_f(pv)} |")
    L += ["", "근거가 사라진 trial (b + c) 만: 중복도별 정확도 (trial 수)", "",
          "| 압축기 | 중복도 1 | 중복도 2+ | p |", "|---|---|---|---|"]
    for c in comps:
        gone = {g: stats([r for r in rows if r["compressor"] == c and r["group"] == g and r["state"] != "a"])
                for g in ("1", "2+")}
        if not gone["1"]["trials"] and not gone["2+"]["trials"]:
            continue
        pv = fisher_p(gone["1"]["correct"], gone["1"]["trials"] - gone["1"]["correct"],
                      gone["2+"]["correct"], gone["2+"]["trials"] - gone["2+"]["correct"]) \
            if gone["1"]["trials"] and gone["2+"]["trials"] else None
        out["by_group"][c]["evidence_gone"] = {**gone, "fisher_p": pv}
        L.append(f"| {c} | {_f(gone['1']['accuracy'])} ({gone['1']['trials']}) "
                 f"| {_f(gone['2+']['accuracy'])} ({gone['2+']['trials']}) | {_f(pv)} |")
    L += ["", "유형별 (중복도 0 제외, 칸 = 1 / 2+ 정확도, 아래 n 은 문항 수)", "",
          "| 유형 | n (1 / 2+) | " + " | ".join(comps) + " |", "|---|---|" + "---|" * len(comps)]
    for qt in qtypes:
        n1 = acc(comps[0], "1", qt)["items"]
        n2 = acc(comps[0], "2+", qt)["items"]
        cells = []
        for c in comps:
            a1, a2 = acc(c, "1", qt), acc(c, "2+", qt)
            out["by_qtype"].setdefault(c, {})[qt] = {"1": a1, "2+": a2}
            cells.append(f"{_f(a1['accuracy'], 2)} / {_f(a2['accuracy'], 2)}")
        L.append(f"| {qt} | {n1} / {n2} | " + " | ".join(cells) + " |")
    return "\n".join(L), out


def main():
    ap = argparse.ArgumentParser(description="문서 중복도와 압축 강건성 (저장된 run 만 사용)")
    ap.add_argument("run_dirs", nargs="+", type=Path, help="results/runs/<run_id> (여러 개면 trial 을 합친다)")
    ap.add_argument("--json", type=Path, help="문항·trial 값을 쓸 파일 (기본: 쓰지 않음)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    items = {it["id"]: it for it in load_items("all", None, None)}
    red, rows = load_rows(args.run_dirs, items)
    text, out = report(red, rows, args.run_dirs)
    print(text)
    if args.json:
        out["trials"] = rows
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
