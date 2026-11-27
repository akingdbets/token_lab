"""
multiturn-v2 시나리오 규칙 (schema_version 2). 설계: docs/experiments/multiturn_v2/DESIGN.md

    fill_derived(s)                 recall_distance 등 자동 계산 필드를 채운다 (손으로 쓰지 않는다)
    validate_scenario_v2(s)         -> 오류 목록. v1 검사(validate_scenario, v2 턴 유형 허용) + v2 규칙
    check_grounding_v2(s, corpus)   -> 오류 목록. v1 근거 확인 + 대안 근거 + same_doc_new_topic 소제목 + 질문 출처 단서
    section_of(text, quote)         인용문이 속한 소제목 (## / ###) 제목
    rule_report(s, corpus)          보고용 요약 (유형 분포, recall 거리, 태그, update·same_doc 확인)

규칙 위반은 오류로 돌려줄 뿐 시나리오를 고치지 않는다. 모델 성능을 보고 문항을 거르지 않는다 (README 원칙).
"""

from __future__ import annotations

import re

from multiturn.scenario import _squash, grounding_pages, validate_scenario

FACT_TAGS = ("condition", "negation", "range", "confusable")
MIN_TURNS, MAX_TURNS = 16, 20
MIN_COUNTS = {"new": 7, "followup": 2, "recall": 3, "synthesis": 2, "update": 2, "same_doc_new_topic": 2}
MIN_FAR_RECALL, FAR_RECALL_DISTANCE = 2, 6
MIN_WIDE_SYNTHESIS, WIDE_SYNTHESIS_TURNS = 1, 3
MIN_CONDITION_TAGS, MIN_CONFUSABLE_TAGS = 3, 2
SAME_DOC_MIN_GAP = 3
NO_UPDATE_IN_LAST, LATE_WINDOW = 3, 3
MAX_SAME_TYPE_RUN = 3

# 질문에 넣지 않는 출처 단서 (대화 맥락으로만 가리킨다)
SOURCE_CUE_RES = [
    re.compile(p, re.I) for p in (
        r"\btutorial\b", r"\bguide\b",
        r"\b(first|second|third|earlier|previous|last|other|that|this)\s+(doc|docs|document|documentation|page|article)\b",
        r"\bgoing back to\b", r"\bback to the\b", r"\bin the docs?\b", r"\bthe docs (about|on)\b",
        r"\bdocumentation (about|on|for)\b", r"\.md\b",
    )
]


def recall_distance(t: dict) -> int:
    return t["turn"] - min(t["depends_on"]) if t.get("depends_on") else 0


def fill_derived(s: dict) -> dict:
    for t in s["turns"]:
        t["recall_distance"] = recall_distance(t)
    return s


def _count(types, name):
    return sum(1 for x in types if x == name)


def validate_scenario_v2(s: dict) -> list[str]:
    errs = list(validate_scenario(s))
    sid = s.get("scenario_id", "?")
    if s.get("schema_version") != 2:
        errs.append(f"{sid}: schema_version 은 2")
    for k, typ in (("bundle", list), ("generation", dict)):
        if not isinstance(s.get(k), typ):
            errs.append(f"{sid}: {k} 필드가 없거나 타입이 다름")
    turns = s.get("turns") or []
    n = len(turns)
    if not MIN_TURNS <= n <= MAX_TURNS:
        errs.append(f"{sid}: 턴 수 {n} (규칙 {MIN_TURNS}~{MAX_TURNS})")
    if errs and any("필드가 없거나 타입이 다름" in e for e in errs):
        return errs
    types = [t.get("turn_type") for t in turns]
    n_cond = n_conf = 0
    for t in turns:
        k, p, tt = t["turn"], f"{sid} 턴 {t['turn']}", t.get("turn_type")
        if not (isinstance(t.get("standalone_question"), str) and t["standalone_question"].strip()):
            errs.append(f"{p}: standalone_question 이 없습니다")
        meta = t.get("fact_meta")
        if not isinstance(meta, list) or len(meta) != len(t["key_facts"]):
            errs.append(f"{p}: fact_meta 길이가 key_facts 와 다릅니다")
            meta = []
        alt_cov = set()
        for e in t.get("alt_evidence") or []:
            if not (isinstance(e, dict) and isinstance(e.get("quote"), str) and isinstance(e.get("page"), str)
                    and isinstance(e.get("fact_idx"), int) and isinstance(e.get("alt_idx"), int)):
                errs.append(f"{p}: alt_evidence 항목은 {{quote, page, fact_idx, alt_idx}}")
                continue
            alt_cov.add((e["fact_idx"], e["alt_idx"]))
        for i, m in enumerate(meta):
            if not (isinstance(m, dict) and isinstance(m.get("accept_alternatives"), list)
                    and isinstance(m.get("tags"), list)):
                errs.append(f"{p}: fact_meta[{i}] 는 {{accept_alternatives: [], tags: []}}")
                continue
            bad = [x for x in m["tags"] if x not in FACT_TAGS]
            if bad:
                errs.append(f"{p}: fact_meta[{i}] 알 수 없는 태그 {bad} (허용 {FACT_TAGS})")
            n_cond += any(x in ("condition", "negation", "range") for x in m["tags"])
            n_conf += "confusable" in m["tags"]
            for j, _ in enumerate(m["accept_alternatives"]):
                if (i, j) not in alt_cov:
                    errs.append(f"{p}: fact {i} 의 대안 {j} 에 근거 인용(alt_evidence)이 없습니다")
        if t.get("recall_distance") != recall_distance(t):
            errs.append(f"{p}: recall_distance {t.get('recall_distance')} (자동 계산값 {recall_distance(t)}, fill_derived 로 채움)")
        for rx in SOURCE_CUE_RES:
            m = rx.search(t["question"])
            if m:
                errs.append(f"{p}: 질문에 출처 단서 {m.group(0)!r}")
        if tt == "update":
            ch, af = t.get("changes"), t.get("affects")
            if not (isinstance(ch, list) and ch and all(isinstance(c, dict) and {"what", "from", "to"} <= set(c) for c in ch)):
                errs.append(f"{p}: update 턴은 changes [{{what, from, to}}] 가 있어야 합니다")
            if not (isinstance(af, list) and af):
                errs.append(f"{p}: update 턴은 affects (영향 받는 뒤 턴) 가 있어야 합니다")
            else:
                for a in af:
                    if not (isinstance(a, int) and k < a < n):
                        errs.append(f"{p}: affects {a} 는 뒤 턴이어야 합니다")
                    elif k not in turns[a]["depends_on"]:
                        errs.append(f"{p}: 영향 턴 {a} 의 depends_on 에 update 턴 {k} 이 없습니다")
            if k >= n - NO_UPDATE_IN_LAST:
                errs.append(f"{p}: update 턴은 마지막 {NO_UPDATE_IN_LAST}턴 안에 둘 수 없습니다")
        if tt == "same_doc_new_topic":
            st = t.get("source_turn")
            if not (isinstance(st, int) and 0 <= st < k):
                errs.append(f"{p}: same_doc_new_topic 은 source_turn (그 문서를 첨부한 앞 턴) 이 있어야 합니다")
            else:
                if k - st < SAME_DOC_MIN_GAP:
                    errs.append(f"{p}: source_turn {st} 과 {k - st}턴 차이 (최소 {SAME_DOC_MIN_GAP})")
                if st not in t["depends_on"]:
                    errs.append(f"{p}: depends_on 에 source_turn {st} 이 없습니다")
                src_pages = turns[st]["evidence_pages"]
                if not src_pages:
                    errs.append(f"{p}: source_turn {st} 에 첨부 문서가 없습니다")
                for e in t["evidence"]:
                    if e.get("page") not in src_pages:
                        errs.append(f"{p}: 근거 페이지 {e.get('page')} 가 source_turn {st} 의 첨부 문서가 아닙니다")
        if tt != "update" and (t.get("changes") or t.get("affects")):
            errs.append(f"{p}: changes / affects 는 update 턴에만")
    # 유형별 최소 개수
    for name, mn in MIN_COUNTS.items():
        if _count(types, name) < mn:
            errs.append(f"{sid}: {name} 턴 {_count(types, name)}개 (최소 {mn})")
    far = [t for t in turns if t.get("turn_type") == "recall" and recall_distance(t) >= FAR_RECALL_DISTANCE]
    if len(far) < MIN_FAR_RECALL:
        errs.append(f"{sid}: 거리 {FAR_RECALL_DISTANCE} 이상 recall {len(far)}개 (최소 {MIN_FAR_RECALL})")
    wide = [t for t in turns if t.get("turn_type") == "synthesis" and len(set(t["depends_on"])) >= WIDE_SYNTHESIS_TURNS]
    if len(wide) < MIN_WIDE_SYNTHESIS:
        errs.append(f"{sid}: {WIDE_SYNTHESIS_TURNS}개 이상 턴을 묶는 synthesis {len(wide)}개 (최소 {MIN_WIDE_SYNTHESIS})")
    if n_cond < MIN_CONDITION_TAGS:
        errs.append(f"{sid}: condition/negation/range 태그 key_fact {n_cond}개 (최소 {MIN_CONDITION_TAGS})")
    if n_conf < MIN_CONFUSABLE_TAGS:
        errs.append(f"{sid}: confusable 태그 key_fact {n_conf}개 (최소 {MIN_CONFUSABLE_TAGS})")
    # 배치
    if types[:2] != ["new", "new"]:
        errs.append(f"{sid}: 턴 0·1 은 new 여야 합니다 ({types[:2]})")
    if n:
        thirds = [range(0, n // 3), range(n // 3, 2 * n // 3), range(2 * n // 3, n)]
        for name, rng in zip(("앞", "가운데", "뒤"), thirds):
            c = sum(1 for i in rng if turns[i]["evidence_pages"])
            if c < 2:
                errs.append(f"{sid}: {name} 1/3 구간 문서 첨부 턴 {c}개 (최소 2)")
        late = turns[n - LATE_WINDOW:]
        if not any(t.get("turn_type") == "recall" and recall_distance(t) >= FAR_RECALL_DISTANCE for t in late):
            errs.append(f"{sid}: 마지막 {LATE_WINDOW}턴 안에 거리 {FAR_RECALL_DISTANCE} 이상 recall 이 없습니다")
        if not any(t.get("turn_type") == "synthesis" for t in late):
            errs.append(f"{sid}: 마지막 {LATE_WINDOW}턴 안에 synthesis 가 없습니다")
    run, prev = 0, None
    for i, x in enumerate(types):
        run = run + 1 if x == prev else 1
        prev = x
        if run > MAX_SAME_TYPE_RUN:
            errs.append(f"{sid}: 턴 {i}: 같은 유형 {x} 이 {run}턴 연속 (최대 {MAX_SAME_TYPE_RUN})")
    return errs


_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.M)


def section_of(text: str, quote: str) -> str | None:
    """인용문이 처음 나오는 위치 바로 앞의 ## / ### 제목. 못 찾으면 None, 제목 앞이면 "(머리말)"."""
    sq = _squash(quote)
    # 공백을 접은 상태에서 위치를 찾기 위해, 원문 위치와 접은 위치를 대응시킨다
    flat, idx_map = [], []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space or not flat:
                continue
            flat.append(" ")
            idx_map.append(i)
            prev_space = True
        else:
            flat.append(ch)
            idx_map.append(i)
            prev_space = False
    pos = "".join(flat).find(sq)
    if pos < 0:
        return None
    raw_pos = idx_map[pos]
    last = "(머리말)"
    for m in _HEADING_RE.finditer(text):
        if m.start() > raw_pos:
            break
        last = m.group(2)
    return last


def _page_titles(text: str) -> list[str]:
    titles = []
    m = re.search(r"^title:\s*(.+)$", text, re.M)
    if m:
        titles.append(m.group(1).strip().strip('"'))
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        titles.append(m.group(1).strip())
    return [x for x in titles if len(x) >= 8]


def check_grounding_v2(s: dict, corpus) -> list[str]:
    from multiturn.scenario import check_grounding

    errs = list(check_grounding(s, corpus))
    turns = s["turns"]
    all_titles = set()
    for page in s.get("bundle") or []:
        try:
            all_titles.update(_page_titles(corpus.get(page).text))
        except KeyError:
            errs.append(f"{s['scenario_id']}: bundle 페이지 {page} 가 코퍼스에 없음")
    for t in turns:
        p = f"{s['scenario_id']} 턴 {t['turn']}"
        pages = grounding_pages(s, t["turn"])
        texts = {}
        for page in pages:
            try:
                texts[page] = corpus.get(page).text
            except KeyError:
                pass
        for e in t.get("alt_evidence") or []:
            if e.get("page") not in pages:
                errs.append(f"{p}: 대안 인용 페이지 {e.get('page')} 가 근거 페이지 밖")
            elif _squash(e["quote"]) not in _squash(texts.get(e["page"], "")):
                errs.append(f"{p}: 대안 인용문이 {e['page']} 에 없음: {e['quote'][:60]!r}")
        low = t["question"].lower()
        for title in all_titles:
            if title.lower() in low:
                errs.append(f"{p}: 질문에 페이지 제목 {title!r} 이 들어 있습니다 (출처 단서)")
        if t.get("turn_type") == "same_doc_new_topic" and isinstance(t.get("source_turn"), int):
            for page in turns[t["source_turn"]]["evidence_pages"]:
                text = texts.get(page)
                if text is None:
                    continue
                prev_secs = {section_of(text, e["quote"]) for e in turns[t["source_turn"]]["evidence"]
                             if e.get("page") == page}
                # 같은 페이지를 앞에서 물은 다른 턴(첨부 턴 이후 그 페이지 인용)도 비교에 넣는다
                for u in turns[t["source_turn"] + 1:t["turn"]]:
                    prev_secs |= {section_of(text, e["quote"]) for e in u["evidence"] if e.get("page") == page}
                cur = {section_of(text, e["quote"]) for e in t["evidence"] if e.get("page") == page}
                same = (cur & prev_secs) - {None}
                if same:
                    errs.append(f"{p}: same_doc_new_topic 이 앞서 물은 소제목과 같은 부분을 묻습니다 {sorted(same)}")
    return errs


def rule_report(s: dict, corpus=None) -> dict:
    """보고용: 유형 분포, recall 거리, 태그, update·same_doc 정보."""
    turns = s["turns"]
    types = [t["turn_type"] for t in turns]
    rep = {
        "scenario_id": s["scenario_id"], "turns": len(turns),
        "type_counts": {k: types.count(k) for k in ("new", "followup", "recall", "synthesis", "update",
                                                   "same_doc_new_topic")},
        "recall_distances": [recall_distance(t) for t in turns if t["turn_type"] == "recall"],
        "max_recall_distance": max([recall_distance(t) for t in turns] or [0]),
        "wide_synthesis": [t["turn"] for t in turns if t["turn_type"] == "synthesis"
                           and len(set(t["depends_on"])) >= WIDE_SYNTHESIS_TURNS],
        "tags": {tag: sum(tag in m["tags"] for t in turns for m in t.get("fact_meta") or []) for tag in FACT_TAGS},
        "confusable_facts": [{"turn": t["turn"], "fact": t["key_facts"][i]} for t in turns
                             for i, m in enumerate(t.get("fact_meta") or []) if "confusable" in m["tags"]],
        "alternatives": sum(len(m["accept_alternatives"]) for t in turns for m in t.get("fact_meta") or []),
        "updates": [{"turn": t["turn"], "changes": t.get("changes"), "affects": t.get("affects")}
                    for t in turns if t["turn_type"] == "update"],
        "same_doc": [],
    }
    if corpus is not None:
        for t in turns:
            if t["turn_type"] != "same_doc_new_topic" or not isinstance(t.get("source_turn"), int):
                continue
            src = turns[t["source_turn"]]
            for page in src["evidence_pages"]:
                try:
                    text = corpus.get(page).text
                except KeyError:
                    continue
                rep["same_doc"].append({
                    "turn": t["turn"], "source_turn": t["source_turn"], "page": page,
                    "source_sections": sorted({section_of(text, e["quote"]) or "?" for e in src["evidence"]
                                               if e["page"] == page}),
                    "sections": sorted({section_of(text, e["quote"]) or "?" for e in t["evidence"] if e["page"] == page}),
                })
    return rep
