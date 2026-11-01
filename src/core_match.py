"""
정답 핵심어 매칭 (normalized-v2)

압축 문맥에 정답 핵심어가 있는지 판정한다. experiment.answer_core_in_context 와 memory_suspect, 정답 사본을
지우는 진단용 압축기(compressors/copies.py)가 같은 규칙을 쓰도록 여기 모아 둔다.
experiment 는 이 모듈의 이름을 그대로 다시 내보낸다 (from experiment import find_normalized 가 계속 된다).
"""

from __future__ import annotations

import re

from grader import contains_words, is_short, word_tokens


CORE_MATCH_VERSION = "normalized-v2"
_CORE_TOKEN = re.compile(r"[a-z0-9]+")
_LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+(?=\S)", re.I)


def _sep_kind(sep: str) -> str:
    """토큰 사이 구분자의 종류: id (식별자 안의 _ 나 -), ws (공백만), other (. / : 등)."""
    if "_" in sep or "-" in sep:
        return "id"
    return "ws" if not sep.strip() else "other"


def _core_tokens(s: str) -> list[tuple[re.Match, str | None]]:
    """[(토큰, 앞 토큰과의 구분자 종류)]. 첫 토큰은 None."""
    low = s.lower()
    toks, prev = [], None
    for m in _CORE_TOKEN.finditer(low):
        toks.append((m, None if prev is None else _sep_kind(low[prev.end():m.start()])))
        prev = m
    return toks


def _cut_ok(needle_kind: str | None, ctx_kind: str) -> bool:
    """정답의 같은 자리(needle_kind, 경계가 없으면 None)에 문맥 경계(ctx_kind)가 있어도 되는지.
    정답에 경계가 없는 자리에는 압축이 끼워 넣은 공백만 허용한다 (WebSocket Disconnect). 정답에 경계가 있으면 같은
    종류여야 한다: asgi-lifespan 과 asgi_lifespan 은 같지만, response_class 가 산문의 "response class" 나
    "Read items" 가 read_items 와 같지는 않다."""
    if needle_kind is None:
        return ctx_kind == "ws"
    return ctx_kind == needle_kind


def iter_normalized(context: str, needle: str, _ctx_tokens: list | None = None):
    """needle 이 문맥에 나오는 위치 (start, end) 를 앞에서부터 모두 낸다 (normalized-v2).

    대소문자와 구분자 표기 차이는 무시한다: "WebSocket Disconnect" == "WebSocketDisconnect",
    "asgi_lifespan" == "asgi-lifespan" == "asgi - lifespan". 연속한 문맥 토큰을 이어 붙인 결과가 needle 토큰을
    이어 붙인 결과와 같아야 하고, 경계마다 _cut_ok 를 지켜야 한다:
        needle 의 경계는 문맥에도 있어야 한다 ("johndoe" 는 "John Doe" 가 아님)
        문맥에만 있는 경계는 공백만 된다 ("10.0" 은 "100" 이 아님, "1000" 안의 "100" 도 아님)
        needle 의 공백 경계에 문맥의 _ 나 - 가 오면 안 된다 ("read_items" 는 "Read items" 가 아님)
    찾은 구절의 앞뒤가 _ 나 - 로 이어지면(식별자의 일부) 맞지 않은 것으로 본다 ("auto_error" 안의 "auto")."""
    want = _core_tokens(needle)
    if not want:
        return
    target = "".join(m.group() for m, _ in want)
    want_cuts, pos = {}, 0
    for m, kind in want:
        if kind is not None:
            want_cuts[pos] = kind
        pos += len(m.group())
    toks = _ctx_tokens if _ctx_tokens is not None else _core_tokens(context)
    for i, (first, before) in enumerate(toks):
        if before == "id" or not target.startswith(first.group()):
            continue
        pos, j, cuts = 0, i, set()
        while j < len(toks) and pos < len(target):
            t, kind = toks[j][0].group(), toks[j][1]
            if not target.startswith(t, pos) or (j > i and not _cut_ok(want_cuts.get(pos), kind)):
                break
            if j > i:
                cuts.add(pos)
            pos += len(t)
            j += 1
        after = toks[j][1] if j < len(toks) else None
        if pos == len(target) and set(want_cuts) <= cuts and after != "id":
            yield first.start(), toks[j - 1][0].end()


def find_normalized(context: str, needle: str, _ctx_tokens: list | None = None) -> str | None:
    """needle 이 문맥에 있으면 문맥에서 찾은 첫 구절, 없으면 None (iter_normalized 의 첫 위치)."""
    span = next(iter_normalized(context, needle, _ctx_tokens), None)
    return None if span is None else context[span[0]:span[1]]


def _strip_article(s: str) -> str:
    """짧은 답·핵심 개체 앞의 관사(The / A / An) 를 뗀다. LLMLingua-2 가 관사부터 지운다.
    떼고 한 단어만 남으면 떼지 않는다 ("A plumbus" 의 plumbus 는 예제 코드 여기저기에 나온다)."""
    rest = _LEADING_ARTICLE.sub("", s.strip())
    return rest if len(_CORE_TOKEN.findall(rest.lower())) >= 2 else s.strip()


def core_needles(item: dict) -> list[str]:
    """문항의 정답 핵심어 목록. 짧은 답은 정답 하나, 긴 답은 핵심 개체(key_entities, 없으면 정답)."""
    answer = item["answer"]
    if is_short(answer):
        return [answer]
    return [e for e in (item.get("key_entities") or [answer]) if _core_tokens(e)]


def find_core(context: str, needle: str, _toks: list | None = None, _words: list[str] | None = None) -> str | None:
    """정답 핵심어 하나를 문맥에서 찾는다. 정규화 매칭(find_normalized) 이나 이전 방식(단어 연속 일치) 중 하나로
    찾으면 문맥에서 찾은 구절(이전 방식이면 needle), 없으면 None. 비교 전에 앞 관사를 뗀다."""
    needle = _strip_article(needle)
    toks = _toks if _toks is not None else _core_tokens(context)
    words = _words if _words is not None else word_tokens(context)
    return find_normalized(context, needle, toks) or (needle if contains_words(words, needle) else None)


def core_matches(context: str, item: dict) -> tuple[bool, list[str]]:
    """answer_core_in_context 의 판정과 문맥에서 찾은 구절들.
    짧은 답은 정답, 긴 답은 핵심 개체 절반 이상을 find_core 로 찾으면 있다고 본다.
    중간 단어가 지워진 경우("last added" 와 "The last one added")는 잡지 않는다 (근거 보존율 축의 몫)."""
    toks, words = _core_tokens(context), word_tokens(context)
    needles = core_needles(item)
    if not needles:
        return False, []
    hits = [h for h in (find_core(context, n, toks, words) for n in needles) if h is not None]
    if is_short(item["answer"]):
        return bool(hits), hits
    return len(hits) >= -(-len(needles) // 2), hits


ANSWER_KINDS = ("identifier", "value")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]+")
_IDENT_MARK = re.compile(r"[_@:{(\[.\-]|[a-z][A-Z]|[A-Z]{2}")


def answer_kind(answer: str) -> str:
    """정답을 식별자형/값형으로 나눈다 (keep_answer_in_place 결과를 나눠 볼 때 쓰는 고정 규칙).

    값형 (위에서부터 먼저 걸리는 것)
        여러 단어            "The last one added", "Apache 2.0", 'uv add "fastapi[standard]"'
        따옴표 리터럴        '"request"', '"lax"'
        글자 없음            숫자·버전 (15, 0.95.0, <0.113.0)
        URL·경로·이메일·와일드카드   http://test, /v1, testing_admin@example.com, *.example.com
    식별자형: 한 단어에 _ @ : { ( [ . - 가 있거나 낙타 표기·연속 대문자
        DUMMY_HASH, asgi-lifespan, @pytest.mark.anyio, StaticPool, FastAPIError, main:app, item.html
    나머지(소문자·첫 글자만 대문자인 한 단어)는 값형: blue, swordfish, Rick, World
    """
    a = answer.strip()
    if re.search(r"\s", a) or a[:1] in "\"'" or not re.search(r"[A-Za-z]", a):
        return "value"
    if "://" in a or a.startswith("/") or "*" in a or _EMAIL.fullmatch(a):
        return "value"
    return "identifier" if _IDENT_MARK.search(a) else "value"
