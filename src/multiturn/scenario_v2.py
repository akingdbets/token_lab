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

# setup: 이번 턴 사용자 발화에 답이 그대로 있는 항목 (사용자가 이번 턴에 정한 값, update 로 바뀐 값을 그대로 쓰기).
#        주 정확도에서 빼고 따로 집계한다 (2026-11-28 검수 결정)
FACT_TAGS = ("condition", "negation", "range", "confusable", "example", "setup")
FACT_SOURCES = ("doc", "user")          # key_fact 출처: 문서 | 사용자가 대화 중 정한 프로젝트 고유 값
USER_SHARE_MIN, USER_SHARE_MAX = 0.3, 0.5   # recall·synthesis 턴 key_fact 중 source=user 비율
MIN_USER_UPDATES = 1                    # source=user key_fact 를 가진 update 턴
MAX_KEY_FACTS = 3                       # 턴당 key_fact 최대
MAX_ASKS = 2                            # synthesis 를 뺀 턴이 묻는 사항 수 최대 (asks 필드)
MIN_TURNS, MAX_TURNS = 16, 20
MIN_COUNTS = {"new": 7, "followup": 2, "recall": 3, "synthesis": 2, "update": 2, "same_doc_new_topic": 2}
MIN_FAR_RECALL, FAR_RECALL_DISTANCE = 2, 6
MIN_WIDE_SYNTHESIS, WIDE_SYNTHESIS_TURNS = 1, 3
MIN_CONDITION_TAGS, MIN_CONFUSABLE_TAGS = 3, 2
SAME_DOC_MIN_GAP = 3
# synthesis 질문에서 답의 범위가 열린 요청 (계획·체크리스트·요약 등) 은 금지 (2026-11-28 검수 결정)
OPEN_ENDED_RES = [re.compile(p, re.I) for p in (
    r"\bplan\b", r"\bchecklist\b", r"\bsummar(y|ise|ize)\b", r"\brecap\b", r"\boverview\b", r"\boutline\b",
    r"\bwrite[- ]?up\b", r"\beverything\b", r"\bwalk me through\b")]
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


def covers(e: dict, d_turn: dict) -> bool:
    """근거 인용 e 가 턴 d 의 정보에서 왔는가: 턴 d 사용자 발화 인용, 턴 d 에 첨부한 페이지,
    또는 턴 d 의 근거 인용이 쓴 페이지 (문서 없는 followup·recall 턴이 앞 문서로 답한 정보)."""
    if isinstance(e.get("user_turn"), int):
        return e["user_turn"] == d_turn["turn"]
    page = e.get("page")
    return page is not None and (page in d_turn["evidence_pages"]
                                 or page in {x.get("page") for x in d_turn["evidence"] if isinstance(x, dict)})


def topic_warnings(s: dict) -> list[str]:
    """한 턴에 문서를 둘 이상 붙였는데 폴더(주제)가 다르면 경고 (한 턴 한 주제, 사람이 판단)."""
    out = []
    for t in s["turns"]:
        dirs = {pg.split("/")[0] if "/" in pg else "(root)" for pg in t["evidence_pages"]}
        if len(t["evidence_pages"]) >= 2 and len(dirs) >= 2:
            out.append(f"{s['scenario_id']} 턴 {t['turn']}: 서로 다른 주제 폴더의 문서 {t['evidence_pages']} 를 한 턴에 붙였습니다 (경고)")
    return out


def chain_turns(s: dict, k: int) -> list[int]:
    """턴 k 와 depends_on 을 거슬러 올라간 턴들 (grounding_pages 와 같은 범위)."""
    seen, stack = set(), [k]
    while stack:
        i = stack.pop()
        if i in seen or not 0 <= i < len(s["turns"]):
            continue
        seen.add(i)
        stack.extend(d for d in s["turns"][i].get("depends_on") or [] if isinstance(d, int))
    return sorted(seen)


def is_symbol_entity(e: str) -> bool:
    """한두 글자 기호 entity ('/', '{}' 등). 정규화 매칭이 기호를 다루지 못해 근거 확인·누설 검사에서 빼고 경고만 한다."""
    e = e.strip()
    return len(e) <= 2 and not any(ch.isalnum() for ch in e)


def leak_entities(t: dict) -> list[str]:
    """standalone_question 에는 있고 원래 question 에는 없는 key_entity (답 누설)."""
    from core_match import find_normalized
    sq, q = t.get("standalone_question") or "", t.get("question") or ""
    return [e for e in t.get("key_entities") or [] if isinstance(e, str) and e.strip() and not is_symbol_entity(e)
            and find_normalized(sq, e) is not None and find_normalized(q, e) is None]


def fact_sources(t: dict) -> list[str | None]:
    return [(m or {}).get("source") if isinstance(m, dict) else None for m in t.get("fact_meta") or []]


def user_share(s: dict) -> tuple[int, int]:
    """(recall·synthesis 턴 key_fact 중 source=user 수, 전체 수)."""
    src = [x for t in s["turns"] if t.get("turn_type") in ("recall", "synthesis") for x in fact_sources(t)]
    return sum(1 for x in src if x == "user"), len(src)


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
        chain = set(chain_turns(s, k))
        for e in t.get("alt_evidence") or []:
            if not (isinstance(e, dict) and isinstance(e.get("quote"), str)
                    and (isinstance(e.get("page"), str) or isinstance(e.get("user_turn"), int))
                    and isinstance(e.get("fact_idx"), int) and isinstance(e.get("alt_idx"), int)):
                errs.append(f"{p}: alt_evidence 항목은 {{quote, page | user_turn, fact_idx, alt_idx}}")
                continue
            if isinstance(e.get("user_turn"), int):     # 앞 대화 근거 대안 (문서 근거는 check_grounding_v2)
                ut = e["user_turn"]
                if ut not in chain:
                    errs.append(f"{p}: 대안 근거 사용자 발화 턴 {ut} 이 depends_on 사슬 밖입니다")
                    continue
                if _squash(e["quote"]) not in _squash(turns[ut]["question"]):
                    errs.append(f"{p}: 대안 근거 인용문이 턴 {ut} 질문에 없음: {e['quote'][:60]!r}")
                    continue
            alt_cov.add((e["fact_idx"], e["alt_idx"]))
        if len(t["key_facts"]) > MAX_KEY_FACTS:
            errs.append(f"{p}: key_facts {len(t['key_facts'])}개 (최대 {MAX_KEY_FACTS})")
        asks = t.get("asks")
        if not (isinstance(asks, list) and asks and all(isinstance(x, str) and x.strip() for x in asks)):
            errs.append(f"{p}: asks (이 턴이 묻는 사항 목록) 가 없습니다")
        elif tt != "synthesis" and len(asks) > MAX_ASKS:
            errs.append(f"{p}: {tt} 턴이 {len(asks)}가지를 묻습니다 (synthesis 외 최대 {MAX_ASKS})")
        leaks = leak_entities(t)
        if leaks:
            errs.append(f"{p}: standalone_question 에 원래 질문에 없던 key_entity {leaks} (답 누설)")
        ev_kind = {}                                    # fact_idx -> {"doc", "user"}
        for e in t["evidence"]:
            if not isinstance(e, dict):
                continue
            if isinstance(e.get("user_turn"), int):
                ut = e["user_turn"]
                ev_kind.setdefault(e.get("fact_idx"), set()).add("user")
                if ut not in chain:
                    errs.append(f"{p}: 사용자 발화 인용 턴 {ut} 이 이 턴과 depends_on 사슬 밖입니다")
                elif _squash(e.get("quote") or "") not in _squash(turns[ut]["question"]):
                    errs.append(f"{p}: 사용자 발화 인용문이 턴 {ut} 질문에 없음: {str(e.get('quote'))[:60]!r}")
            elif isinstance(e.get("page"), str):
                ev_kind.setdefault(e.get("fact_idx"), set()).add("doc")
        same_turn_user = {e.get("fact_idx") for e in t["evidence"]
                          if isinstance(e, dict) and e.get("user_turn") == k}
        n_main = 0
        for i, m in enumerate(meta):
            if not (isinstance(m, dict) and isinstance(m.get("accept_alternatives"), list)
                    and isinstance(m.get("tags"), list)):
                errs.append(f"{p}: fact_meta[{i}] 는 {{accept_alternatives: [], tags: [], source}}")
                continue
            setup = "setup" in m["tags"]
            n_main += not setup
            if m.get("source") == "user" and i in same_turn_user and not setup:
                errs.append(f"{p}: fact {i} 는 이번 턴 사용자 발화가 답입니다 (tags 에 setup 필요)")
            if setup and not (m.get("source") == "user" and i in same_turn_user):
                errs.append(f"{p}: fact {i} 의 setup 태그는 이번 턴 사용자 발화 인용이 있는 source=user 항목에만")
            if m.get("source") not in FACT_SOURCES:
                errs.append(f"{p}: fact_meta[{i}].source 는 {FACT_SOURCES} 중 하나")
            elif m["source"] not in ev_kind.get(i, set()):
                errs.append(f"{p}: fact {i} (source={m['source']}) 에 "
                            f"{'사용자 발화' if m['source'] == 'user' else '문서'} 근거 인용이 없습니다")
            bad = [x for x in m["tags"] if x not in FACT_TAGS]
            if bad:
                errs.append(f"{p}: fact_meta[{i}] 알 수 없는 태그 {bad} (허용 {FACT_TAGS})")
            n_cond += any(x in ("condition", "negation", "range") for x in m["tags"])
            n_conf += "confusable" in m["tags"]
            for j, _ in enumerate(m["accept_alternatives"]):
                if (i, j) not in alt_cov:
                    errs.append(f"{p}: fact {i} 의 대안 {j} 에 근거 인용(alt_evidence)이 없습니다")
        if meta and n_main == 0:
            errs.append(f"{p}: setup 이 아닌 key_fact 가 없습니다 (최소 1개)")
        if tt == "synthesis":
            if isinstance(asks, list) and len(asks) != len(t["key_facts"]):
                errs.append(f"{p}: synthesis 는 asks 와 key_facts 가 1:1 이어야 합니다 (asks {len(asks)}, key_facts {len(t['key_facts'])})")
            for rx in OPEN_ENDED_RES:
                mm = rx.search(t["question"])
                if mm:
                    errs.append(f"{p}: synthesis 질문이 답의 범위가 열린 요청입니다 ({mm.group(0)!r})")
        for d in sorted(set(x for x in t["depends_on"] if isinstance(x, int) and 0 <= x < k)):
            if not any(covers(e, turns[d]) for e in t["evidence"] if isinstance(e, dict)):
                errs.append(f"{p}: depends_on 턴 {d} 의 정보(사용자 발화·문서)를 근거로 한 key_fact 가 없습니다")
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
                    if "page" in e and e.get("page") not in src_pages:
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
    nu, nt = user_share(s)
    if nt and not USER_SHARE_MIN <= nu / nt <= USER_SHARE_MAX:
        errs.append(f"{sid}: recall·synthesis key_fact 중 source=user {nu}/{nt} = {nu / nt:.0%} "
                    f"(규칙 {USER_SHARE_MIN:.0%}~{USER_SHARE_MAX:.0%})")
    n_user_upd = sum(1 for t in turns if t.get("turn_type") == "update" and "user" in fact_sources(t))
    if n_user_upd < MIN_USER_UPDATES:
        errs.append(f"{sid}: source=user key_fact 를 가진 update 턴 {n_user_upd}개 (최소 {MIN_USER_UPDATES})")
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


def check_grounding_v2(s: dict, corpus, warnings: list | None = None) -> list[str]:
    """v1 check_grounding 과 같은 확인을 하되
    - 사용자 발화 인용({quote, user_turn}) 은 validate_scenario_v2 가 확인하므로 건너뛴다
    - key_entity 는 근거 페이지 + 이 턴과 depends_on 사슬 턴들의 사용자 질문에서 찾는다 (사용자 고유 값)
    - 한두 글자 기호 entity 는 오류가 아니라 warnings 에 넣는다 (정규화 매칭이 기호를 다루지 못함)"""
    from core_match import find_normalized

    errs = []
    turns = s["turns"]
    for t in turns:
        p = f"{s['scenario_id']} 턴 {t['turn']}"
        pages = grounding_pages(s, t["turn"])
        for page in t["evidence_pages"]:
            try:
                corpus.get(page)
            except KeyError:
                errs.append(f"{p}: 코퍼스에 없는 페이지 {page}")
        texts = {}
        for page in pages:
            try:
                texts[page] = corpus.get(page).text
            except KeyError:
                pass
        for e in t["evidence"]:
            if "page" not in e:
                continue
            if e["page"] not in pages:
                errs.append(f"{p}: 인용 페이지 {e['page']} 가 근거 페이지 {pages} 밖")
            elif _squash(e["quote"]) not in _squash(texts.get(e["page"], "")):
                errs.append(f"{p}: 인용문이 {e['page']} 에 없음: {e['quote'][:60]!r}")
        joined = "\n".join(list(texts.values()) + [turns[i]["question"] for i in chain_turns(s, t["turn"])])
        for ent in t["key_entities"]:
            if is_symbol_entity(ent):
                if warnings is not None:
                    warnings.append(f"{p}: key_entity {ent!r} 는 기호뿐이라 근거 확인에서 뺌 (경고)")
                continue
            if find_normalized(joined, ent) is None:
                errs.append(f"{p}: key_entity {ent!r} 가 근거 페이지·사용자 발화에 없음")
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
        "updates": [{"turn": t["turn"], "changes": t.get("changes"), "affects": t.get("affects"),
                     "user_source": "user" in fact_sources(t)}
                    for t in turns if t["turn_type"] == "update"],
        "same_doc": [],
        # 출처 (source=doc | user)
        "facts_by_source": {src: sum(1 for t in turns for x in fact_sources(t) if x == src) for src in FACT_SOURCES},
        "user_share_recall_synthesis": user_share(s),
        "user_facts": [{"turn": t["turn"], "turn_type": t["turn_type"], "fact": t["key_facts"][i]}
                       for t in turns for i, x in enumerate(fact_sources(t)) if x == "user"],
        # 문서 고유 예시 값 (example 태그, 생성 모델이 붙인 것)
        "doc_example_facts": (sum(1 for t in turns for i, m in enumerate(t.get("fact_meta") or [])
                                  if m.get("source") == "doc" and "example" in m.get("tags", [])),
                              sum(1 for t in turns for x in fact_sources(t) if x == "doc")),
        # 턴당 질문 수: asks 길이 (생성 모델이 적은 것) 와 질문의 물음표 수 (교차 확인)
        "asks": [len(t.get("asks") or []) for t in turns],
        "question_marks": [t["question"].count("?") for t in turns],
        "key_fact_counts": [len(t["key_facts"]) for t in turns],
        "leaks": [{"turn": t["turn"], "entities": leak_entities(t)} for t in turns if leak_entities(t)],
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
                                               if e.get("page") == page}),
                    "sections": sorted({section_of(text, e["quote"]) or "?" for e in t["evidence"] if e.get("page") == page}),
                })
    return rep


RATIOS = (0.25, 0.5, 0.75)
MIN_HISTORY_FOR_RATIO = 4000


def ratio_overflow(s: dict, corpus, prompt, token_counter, ratios=RATIOS, keep_recent: int = 1,
                   min_history: int = MIN_HISTORY_FOR_RATIO) -> dict:
    """비율 압축 강도에서 overflow 가 생기는 턴 비율 (예산형 압축기 기준, 구현 전 설계 점검용).
    턴 k 의 예산 = ceil(r × 과거 기록 원문 토큰). 최근 keep_recent 턴은 넘쳐도 남기므로, 그 턴만으로 예산을 넘으면 overflow.
    과거 답변 자리에는 시나리오의 참고 정답(answer)을 넣는다 (실제 모델 답변 길이와 다를 수 있다).
    기록이 min_history 토큰 이상인 턴만 센다."""
    import math

    from multiturn.history_compressors.base import split_turns
    from multiturn.history_compressors.budget import history_tokens

    past, rows = [], []
    for t in s["turns"]:
        hist = history_tokens(past, token_counter)
        if past and hist >= min_history:
            recent = split_turns(past)[-keep_recent:] if keep_recent else []
            recent_tokens = history_tokens([m for tr in recent for m in tr], token_counter)
            rows.append({"turn": t["turn"], "history": hist, "recent": recent_tokens,
                         **{f"r{int(r * 100)}": recent_tokens > math.ceil(r * hist) for r in ratios}})
        past = past + [{"role": "user", "content": prompt.user_message(t, corpus)},
                       {"role": "assistant", "content": t["answer"]}]
    final = history_tokens(past[:-2], token_counter) if len(past) >= 2 else 0
    n = len(rows)
    return {"turns_counted": n, "final_history": final,
            **{f"r{int(r * 100)}_overflow_rate": (sum(x[f"r{int(r * 100)}"] for x in rows) / n if n else None)
               for r in ratios},
            "rows": rows}


VAGUE_RES = [re.compile(p, re.I) for p in (r"\bsuitable\b", r"\bappropriate\b", r"\bbest practice", r"\bconsider\b",
                                             r"\bas needed\b", r"\bsomething like\b", r"\bproperly\b")]


def suspect_reasons(s: dict, t: dict) -> list[str]:
    """검수 때 먼저 볼 의심 사유 (자동 점검, 판정은 사람이 한다)."""
    out = []
    tt, k = t["turn_type"], t["turn"]
    if len(t["question"]) > 400:
        out.append(f"질문이 김 ({len(t['question'])}자)")
    if tt != "synthesis" and t["question"].count("?") >= 3:
        out.append(f"물음표 {t['question'].count('?')}개")
    for i, f in enumerate(t["key_facts"]):
        for rx in VAGUE_RES:
            m = rx.search(f)
            if m:
                out.append(f"정답이 열려 있을 수 있음: fact {i} {m.group(0)!r}")
                break
    for e in t["evidence"]:
        if "page" in e and len(e["quote"].strip()) < 20:
            out.append(f"근거 인용이 짧음: fact {e['fact_idx']} {e['quote']!r}")
    if any((m or {}).get("accept_alternatives") for m in t.get("fact_meta") or []):
        out.append("대안 판정 확인 (alt_judge_label)")
    turns = s["turns"]
    for d in sorted(set(t["depends_on"])):
        evs = [e for e in t["evidence"] if isinstance(e, dict) and covers(e, turns[d])]
        direct = [e for e in evs if e.get("user_turn") == d or e.get("page") in turns[d]["evidence_pages"]]
        if evs and not direct:
            out.append(f"턴 {d} 의존은 간접 채점 (턴 {d} 가 인용한 페이지만 같음)")
        if evs and all("setup" in ((t["fact_meta"][e["fact_idx"]] or {}).get("tags") or [])
                       for e in evs if 0 <= e["fact_idx"] < len(t["fact_meta"])):
            out.append(f"턴 {d} 의존은 setup 항목으로만 채점")
    g = t.get("closed_book_grounded") or {}
    if (g.get("accuracy_main") or 0) > 0:
        out.append(f"grounded 에서 기억으로 답함 (정확도 {g.get('accuracy_main'):.2f})")
    kn = t.get("closed_book_knowledge") or {}
    if kn.get("correct") and tt in ("recall", "synthesis"):
        out.append("recall·synthesis 인데 knowledge 로 맞힘")
    if tt == "update" and len(t["key_facts"]) - sum("setup" in (m.get("tags") or []) for m in t["fact_meta"]) < 1:
        out.append("update 턴에 setup 외 항목 없음")
    return out
