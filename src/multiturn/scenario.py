"""
멀티턴 시나리오 (data/evalsets/multiturn-v1/*.json, 시나리오 하나 = JSON 하나)

스키마 (필드 의미는 싱글턴 평가셋과 같다. 자세한 설명은 data/evalsets/multiturn-v1/README.md)
    schema_version 2 (multiturn-v2) 는 turn_type 에 update, same_doc_new_topic 을 더 받는다. v2 전용 규칙은 multiturn/scenario_v2.py.
    schema_version 2 의 evidence 는 사용자 발화 인용 {quote, user_turn, fact_idx} 도 받는다 (근거 확인은 scenario_v2).
    schema_version 이 없으면 v1 규칙 그대로 (turn_type 4종, evidence 는 page 인용만).
    scenario_id, title, topic, status ("draft" | "reviewed")
    turns: [
        turn            0 부터 순서대로
        turn_type       new | followup | recall | synthesis
        type            fact | code | procedure | multi | default  (답변 형식 줄, 싱글턴 answer_v1 과 같음)
        question, answer, key_facts, key_entities
        evidence_pages  이 턴 사용자 메시지에 첨부할 위키 페이지 (없으면 [])
        depends_on      답하려면 필요한 이전 턴 번호 (현재·미래 턴 금지)
        evidence        [{quote, page, fact_idx}]  key_fact 마다 근거 인용문 1개 이상 (근거 확인용, 메시지에는 안 들어감)
    ]

validate_scenario(s)            -> 오류 목록 (빈 리스트면 통과)
check_grounding(s, corpus)      -> 오류 목록. quote 와 key_entity 가 근거 페이지에 실제로 있는지
    근거 페이지 = 그 턴의 evidence_pages + depends_on 을 거슬러 올라간 턴들의 evidence_pages
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

TURN_TYPES_V1 = ("new", "followup", "recall", "synthesis")
# multiturn-v2 (schema_version 2) 에서 추가: update (앞 조건을 바꿈), same_doc_new_topic (앞서 첨부한 문서의 다른 부분)
TURN_TYPES_V2 = TURN_TYPES_V1 + ("update", "same_doc_new_topic")
TURN_TYPES = TURN_TYPES_V2          # 집계·표시용 전체 목록. 검증은 시나리오의 schema_version 으로 고른다
ANSWER_TYPES = ("fact", "code", "procedure", "multi", "default")
STATUSES = ("draft", "reviewed")
MIN_RECALL = 2
MIN_SYNTHESIS = 2


def load_scenario(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_scenarios(directory: str | Path) -> list[dict]:
    """폴더의 *.json 을 scenario_id 순으로. README 등 다른 파일은 무시."""
    out = [load_scenario(p) for p in sorted(Path(directory).glob("*.json"))]
    return sorted(out, key=lambda s: s["scenario_id"])


def scenario_hash(s: dict) -> str:
    blob = json.dumps(s, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def validate_scenario(s: dict) -> list[str]:
    errs: list[str] = []
    for k in ("scenario_id", "title", "topic", "status", "turns"):
        if k not in s:
            errs.append(f"필드 없음: {k}")
    if errs:
        return errs
    sid = s["scenario_id"]
    allowed_types = TURN_TYPES_V2 if s.get("schema_version") == 2 else TURN_TYPES_V1
    if s["status"] not in STATUSES:
        errs.append(f"{sid}: status 는 {STATUSES} 중 하나")
    turns = s["turns"]
    if not isinstance(turns, list) or not turns:
        return errs + [f"{sid}: turns 가 비었습니다"]
    for i, t in enumerate(turns):
        p = f"{sid} 턴 {i}"
        if t.get("turn") != i:
            errs.append(f"{p}: turn 번호가 {t.get('turn')} (순서대로 0 부터여야 함)")
        bad_fields = [k for k, typ in (("question", str), ("answer", str), ("key_facts", list),
                                       ("key_entities", list), ("evidence_pages", list),
                                       ("depends_on", list), ("evidence", list))
                      if not isinstance(t.get(k), typ)]
        if bad_fields:
            errs.append(f"{p}: 필드가 없거나 타입이 다름 {bad_fields}")
            continue
        if t.get("turn_type") not in allowed_types:
            errs.append(f"{p}: turn_type 은 {allowed_types} 중 하나")
        if t.get("type") not in ANSWER_TYPES:
            errs.append(f"{p}: type 은 {ANSWER_TYPES} 중 하나")
        if not [f for f in t["key_facts"] if str(f).strip()]:
            errs.append(f"{p}: key_facts 가 비었습니다")
        for d in t["depends_on"]:
            if not isinstance(d, int) or isinstance(d, bool):
                errs.append(f"{p}: depends_on 값은 정수 ({d!r})")
            elif d >= i:
                errs.append(f"{p}: depends_on 이 현재·미래 턴 {d} 을 가리킵니다")
            elif d < 0:
                errs.append(f"{p}: depends_on 음수 {d}")
        tt = t.get("turn_type")
        if tt == "new" and not t["evidence_pages"]:
            errs.append(f"{p}: new 턴은 evidence_pages 가 있어야 합니다")
        if tt in ("recall", "synthesis", "same_doc_new_topic") and t["evidence_pages"]:
            errs.append(f"{p}: {tt} 턴은 문서를 다시 첨부하지 않습니다")
        if tt in ("followup", "recall", "synthesis", "update", "same_doc_new_topic") and not t["depends_on"]:
            errs.append(f"{p}: {tt} 턴은 depends_on 이 있어야 합니다")
        if tt == "synthesis" and len(t["depends_on"]) < 2:
            errs.append(f"{p}: synthesis 턴은 이전 턴 2개 이상에 의존해야 합니다")
        covered = set()
        for e in t["evidence"]:
            # schema_version 2 는 사용자 발화 인용 {quote, user_turn, fact_idx} 도 받는다 (v1 은 page 인용만)
            src_ok = isinstance(e, dict) and (isinstance(e.get("page"), str) or (
                s.get("schema_version") == 2 and isinstance(e.get("user_turn"), int)
                and not isinstance(e.get("user_turn"), bool)))
            if not (src_ok and isinstance(e.get("quote"), str) and isinstance(e.get("fact_idx"), int)):
                errs.append(f"{p}: evidence 항목은 {{quote, page, fact_idx}}"
                            + (" 또는 {quote, user_turn, fact_idx}" if s.get("schema_version") == 2 else ""))
                continue
            if not 0 <= e["fact_idx"] < len(t["key_facts"]):
                errs.append(f"{p}: evidence fact_idx {e['fact_idx']} 범위 밖")
            covered.add(e["fact_idx"])
        missing = set(range(len(t["key_facts"]))) - covered
        if missing:
            errs.append(f"{p}: 근거 인용문이 없는 key_fact {sorted(missing)}")
    types = [t.get("turn_type") for t in turns]
    if types.count("recall") < MIN_RECALL:
        errs.append(f"{sid}: recall 턴이 {types.count('recall')}개 (최소 {MIN_RECALL})")
    if types.count("synthesis") < MIN_SYNTHESIS:
        errs.append(f"{sid}: synthesis 턴이 {types.count('synthesis')}개 (최소 {MIN_SYNTHESIS})")
    return errs


def grounding_pages(s: dict, k: int) -> list[str]:
    """턴 k 의 근거 페이지: 자신의 evidence_pages + depends_on 을 거슬러 올라간 턴들의 evidence_pages."""
    seen, stack, pages = set(), [k], []
    while stack:
        i = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        t = s["turns"][i]
        for p in t["evidence_pages"]:
            if p not in pages:
                pages.append(p)
        stack.extend(t["depends_on"])
    return pages


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_grounding(s: dict, corpus) -> list[str]:
    """quote 는 공백을 접은 뒤 글자 그대로, key_entity 는 core_match.find_normalized 로 근거 페이지에서 찾는다."""
    from core_match import find_normalized

    errs = []
    for t in s["turns"]:
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
            if e["page"] not in pages:
                errs.append(f"{p}: 인용 페이지 {e['page']} 가 근거 페이지 {pages} 밖")
            elif _squash(e["quote"]) not in _squash(texts.get(e["page"], "")):
                errs.append(f"{p}: 인용문이 {e['page']} 에 없음: {e['quote'][:60]!r}")
        joined = "\n".join(texts.values())
        for ent in t["key_entities"]:
            if find_normalized(joined, ent) is None:
                errs.append(f"{p}: key_entity {ent!r} 가 근거 페이지에 없음")
    return errs
