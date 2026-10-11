"""
평가 데이터셋 생성

문서는 corpus.load_corpus() 로만 받는다 (OpenWiki 위키 data/openwiki/en, 가공 없음).
본문 페이지(kind="page") 원문을 LLM에 주고 질문-정답 후보를 뽑는다. 목차 페이지
(quickstart, index)는 질문 생성 대상이 아니다. 근거(evidence)는 corpus.locate_all 로 찾아
다음 형식으로 기록한다.
    {"quote": 인용문, "page": 인용문이 발견된 페이지 doc_id,
     "locations": [{"file": 페이지 doc_id, "line": 줄 번호}, ...]}   # 일치하는 위치 전부
종합형에서 두 페이지 모두에서 발견되면 페이지마다 별도 항목. 문항의 evidence_pages 는 근거 page 를 중복 없이 정렬한 목록으로,
채점기가 "근거 페이지를 열었는가"를 판정할 때 쓴다.

질문 유형
    fact       사실 확인형      기본값, 이름, 타입, 숫자 등 짧은 사실
    procedure  계획·절차형      무엇을 어떤 순서로 해야 하는지
    code       코드·파라미터형  예제 코드의 인자, 값, 데코레이터, import 등
    multi      여러 페이지 종합형  두 페이지의 정보를 합쳐야 답할 수 있음

처리 단계
    문서 선택(dev/test 비율 맞춘 뒤 폴더별 층화 추출) -> 유형별 생성 -> 순환 질문 제거
    -> 문서 표현 베끼기 검사(바꿔 쓰기 또는 제거) -> 근거 위치 확인(corpus.locate)
    -> 유형별 근거 위치(사실형=코드 블록 밖 문장, 코드형=코드 블록 안의 줄)
    -> 종합형은 한 페이지에만 있는 핵심 엔티티가 양쪽에 있는지, 그리고 페이지 A만/B만 주고
       풀게 했을 때 어느 한쪽으로도 정답이 나오지 않는지 (single_page_a / single_page_b)
    -> LLM 자동 검증 -> 문서 없이 맞히는 질문 제거 -> 저장
    (답이 "not mentioned" 류인 문항은 초반에 "답이 없는 질문"으로 제외)
    종합형 짝: 위키 페이지 간 링크 기준. 이 페이지가 링크하는 본문 페이지 우선, 없으면
    이 페이지를 링크하는 본문 페이지 (같은 분할·예산 안)
    (질문을 바꿔 쓰면 바꾼 질문으로 순환·복사 검사를 다시 하고, 검증과 문서 없이 풀기도
     바꾼 질문으로 한다)

문서 길이
    --min-tokens(600) 미만은 제외. --max-tokens(12000) 초과 문서는 제외하지 않고
    ## 섹션 단위로 나눠 섹션마다 생성한다 (작은 섹션은 이웃과 합침). 문서 선택은 문서
    단위이고, 근거의 파일은 섹션이어도 원래 문서 doc_id 다. 생성 입력(채팅 템플릿 포함)
    + 출력 상한(OUTPUT_RESERVE)이 num_ctx 를 넘는 호출은 하지 않는다.

저장 (data/eval/)
    qa_dataset.json   전체 (split 필드 포함)
    qa_dev.json       개발용 — 프롬프트·파라미터 조정에만 사용
    qa_test.json      최종용 — 최종 결과 보고에만 사용
    qa_meta.json      다음 문항 번호, 삭제된 번호, 코퍼스 매니페스트 해시

실행 로그 (results/logs/dataset_<run_id>.jsonl)
    LLM 호출마다 보낸 메시지와 답변 원문을,
    후보 문항마다 단계별 판정(생성 -> 엔티티 -> 길이 -> 순환 -> 복사/바꿔 쓰기
    -> 근거 -> 검증 -> 문서 없이 풀기)을 빠짐없이 남긴다. 평가셋 문항의 gen_log
    필드가 로그의 후보(cand_id)를 가리킨다. 이벤트 형식은 RunLog 참고.

문항 ID는 한 번 붙으면 바뀌지 않는다. 삭제해도 다른 문항 번호는 그대로이고
삭제된 번호는 재사용하지 않는다. 다시 생성하면 기존 평가셋에 이어 붙인다
(같은 질문은 건너뜀). 개발/최종 분할은 문서 경로 해시로 정해지므로
같은 문서의 문항은 항상 같은 쪽에 들어간다.

사용법
    python src/dataset_builder.py                      # 기본: 문서 30개 x 유형별 1문항
    python src/dataset_builder.py --docs 50 --per-type 2
    python src/dataset_builder.py --types fact,code --docs 5 --dry-run   # 화면 출력만
    python src/dataset_builder.py --only-split dev --docs 10             # dev 문서에서만

외부 생성 후보 (Ollama 대신 다른 모델이 후보를 만들고, 검사·필터·저장은 여기서)
    python src/dataset_builder.py --list-targets        # 페이지별 split·짝 후보 (+ candidates/targets.json)
    python src/dataset_builder.py --import data/eval/candidates/claude_20261006.jsonl \
        --generator claude-opus-5-5 --dry-run
    한 줄 = 후보 하나: {"type", "persona", "source_pages", "question", "answer",
                        "key_entities", "key_facts", "evidence"}
    기본값: --copy-mode drop, 자동 검증 끔(--verify 로 켬), 문서 없이 풀기·종합형 한 페이지
    검사는 항상 (실험 모델 기준). 통과 문항에 persona 와 gen_log(generator, 파일, 줄 번호) 기록

검수
    python src/dataset_builder.py --review             # 대화형 검수 모드
    python src/dataset_builder.py --stats
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from corpus import FENCE, Corpus, load_corpus, manifest_sha256
from grader import closed_book_knows
from llm import LLM, count_message_tokens, count_tokens

TYPES = ("fact", "procedure", "code", "multi")


# ---------------- 프롬프트 ----------------

GEN_SYSTEM = (
    "You create question-answer pairs for evaluating document-grounded QA systems. "
    "You output only valid JSON."
)

COMMON_RULES = """
For each question also give:
- "key_entities": 1 to 5 exact strings (class/function/parameter names, values,
  commands, keywords) that are important for answering the question. Copy each
  one verbatim from the page.
- "key_facts": a list of the essential facts that a correct answer must convey.
  Each item must express one independently checkable fact. Write each fact as a
  short, complete statement. Do not combine multiple facts into one item.
- "evidence": a list of exact sentences or code lines copied verbatim from the
  page that prove the answer.

General rules:
- Write the question in your OWN words. Do NOT copy phrases or sentences from the
  page into the question; describe the situation or goal instead. Identifiers
  (class, function, parameter names) may be kept as they are.
- The question must be answerable WITHOUT seeing the page title, so include enough
  context in the question itself (e.g. "In FastAPI, ...").
- The answer must NOT already appear inside the question.
- The answer must not be general knowledge that does not need the page.
- Do not ask about the document itself ("what does this page explain?").
- Each question must target a DIFFERENT piece of information.
- Ask exactly ONE thing per question.

Output ONLY a JSON array, no markdown fences, no explanation:
[
  {
    "question": "...",
    "answer": "...",
    "key_entities": ["..."],
    "key_facts": ["..."],
    "evidence": ["..."]
  }
]
"""

TYPE_SPECS = {
    "fact": """Create {n} FACT-CHECKING questions.

- The answer must be a specific, verifiable fact stated explicitly in the page
  (a default value, a name, a type, a number, a keyword, a term definition).
- The answer must be SHORT: at most 15 words.
- Ask about facts stated in the prose, not values that only appear in code.
- Do not ask why, and do not ask for opinions or comparisons.

GOOD examples:
- Q "When a FastAPI route handles a successful POST without an explicit status, which HTTP code is sent?" A "200"
- Q "Which FastAPI class marks a function argument as coming from an HTML form submission?" A "Form"
""",
    "procedure": """Create {n} PLANNING / PROCEDURE questions.

- Ask how to accomplish a concrete goal that the page walks through
  (e.g. "what do I need to do, and in what order, to ...?").
- The answer is an ordered list of the steps the page describes, written as
  "1) ... 2) ... 3) ...", at most 60 words, naming the exact classes,
  functions, commands or settings involved.
- Every step must come from the page; do not add steps from outside knowledge.
- The procedure must have at least 2 steps.
- Prefer procedures specific to this page (particular settings, parameters, or steps)
  over general usage that any FastAPI user would already know.

GOOD example:
- Q "In FastAPI, what must I do to receive a JSON object with name and price fields in a request?"
  A "1) Import BaseModel from pydantic 2) Create a class inheriting BaseModel with name and price attributes 3) Declare a path operation parameter typed with that class"
""",
    "code": """Create {n} CODE / PARAMETER questions about the example code in the page
(the code blocks).

- Ask about a concrete detail of the code: an argument name or value, a default,
  a decorator, an import, a type annotation, a return value, a class used.
- The answer must be SHORT: an identifier, a value or a code expression of at
  most 15 words.
- At least one evidence item must be the exact code line containing the answer.

GOOD examples:
- Q "In the FastAPI example that limits how many items are returned, what default is given to the limit argument?" A "10"
- Q "Which keyword argument on the route decorator makes a FastAPI endpoint reply with 201?" A "status_code"
""",
}

MULTI_SPEC = """Below are TWO related technical documentation pages, PAGE A and PAGE B.

Create {n} MULTI-PAGE SYNTHESIS questions.

- Each question must REQUIRE information from BOTH pages: it cannot be answered
  from page A alone or from page B alone.
- The answer combines the needed facts, at most 40 words.
- "evidence" must include at least one exact quote from PAGE A and at least one
  exact quote from PAGE B.

GOOD example:
- Q "In FastAPI, how do I accept an item body together with a query parameter q that defaults to None?"
  A "Declare a parameter typed with a Pydantic BaseModel for the body and a separate q: str | None = None parameter"
"""

VERIFY_PROMPT = """Below are document(s) and a question-answer pair.

Check ALL of the following:
1. The answer is supported by the document(s).
2. The question is answerable using only the document(s).
3. The answer is specific, not vague.
4. The answer does NOT already appear inside the question text.
5. The answer fully answers everything the question asks.

Output ONLY one word: VALID or INVALID

--- DOCUMENTS ---
{doc}
--- QUESTION ---
{q}
--- PROPOSED ANSWER ---
{a}"""

REWRITE_PROMPT = """The question below copies wording from its source document.
Rewrite it so it asks for exactly the same information and has exactly the same
answer, but uses different words and sentence structure, as a real user would ask.
Keep code identifiers (class, function, parameter names) unchanged.
Do not put the answer in the question.

Output ONLY the rewritten question.

Question: {q}
Answer (for reference, do not include it): {a}"""

CLOSED_BOOK_PROMPT = """Answer the question from your own knowledge. Be brief.
If you do not know, reply exactly: UNKNOWN

Question: {q}"""

# 종합형이 한 페이지만으로 풀리는지 볼 때. 문서 없이 풀기와 같은 형식에 문서만 준다
SINGLE_PAGE_PROMPT = """Answer the question using only the document below. Be brief.
If the document does not contain the answer, reply exactly: UNKNOWN

--- DOCUMENT ---
{doc}
--- END DOCUMENT ---

Question: {q}"""


# ---------------- 문서 ----------------

def rel_root(p: Path) -> str:
    """프로젝트 루트 기준 경로 (로그 파일 위치 표시용)."""
    p = p.resolve()
    return p.relative_to(CFG.root).as_posix() if p.is_relative_to(CFG.root) else p.as_posix()


def ngrams(words: list[str], n: int) -> set[tuple]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


@dataclass
class Doc:
    """생성 대상 문서. 원본은 코퍼스가 갖고, 여기는 LLM에 줄 보기와 선택용 정보만 둔다."""
    doc_id: str                 # 코퍼스 doc_id (request/request-body.md)
    text: str                   # 페이지 원문 그대로
    tokens: int                 # text 의 토큰 수 (길이 범위 필터 기준)
    corpus: Corpus = field(repr=False)
    links: list[str] = field(default_factory=list)   # 이 페이지가 링크하는 본문 페이지 (doc_id)
    section: str | None = None  # 섹션 단위일 때 ## 제목 (여럿을 합쳤으면 " / " 로 연결)
    parts: list[Doc] = field(default_factory=list, repr=False)
    # 길이 상한을 넘는 문서는 ## 섹션 단위로 나눈 parts 로 생성한다. 문서 선택(층화 추출)은
    # 문서 단위로 하고, 근거의 page 는 섹션이어도 원래 문서 doc_id 그대로다.

    def units(self) -> list[Doc]:
        """질문 생성 단위. 나눈 문서면 섹션들, 아니면 문서 자신."""
        return self.parts or [self]

    @property
    def rel(self) -> str:
        """위키 루트 기준 경로 (= doc_id). 폴더 구분과 분할 해시에 쓴다."""
        return self.doc_id

    @property
    def folder(self) -> str:
        return self.rel.split("/")[0] if "/" in self.rel else "(root)"

    @property
    def split(self) -> str:
        return split_of(self.rel)

    def ngram_sets(self) -> tuple[set, set]:
        if not hasattr(self, "_ng"):
            w = words_of(self.text)
            self._ng = (ngrams(w, 3), ngrams(w, 6))
        return self._ng


DEV_RATIO = 0.2


def split_of(rel: str) -> str:
    """문서 경로 해시로 개발/최종 결정. 실행마다 같고, 문서 단위라 누수가 없다."""
    h = int(hashlib.md5(rel.encode("utf-8")).hexdigest(), 16) % 1000
    return "dev" if h < DEV_RATIO * 1000 else "test"


def split_sections(text: str, min_tokens: int, max_tokens: int) -> list[tuple[str, str]]:
    """펼친 텍스트를 ## 제목 단위로 나눈다 -> [(섹션 제목, 텍스트)].
    - 코드 블록 안의 ## 는 제목으로 치지 않는다.
    - min_tokens 미만 섹션은 이웃과 합친다 (합쳐도 max_tokens 이하일 때만).
    - 첫 조각이 아닌 섹션에는 문서의 # 제목 줄을 앞에 붙여 무슨 문서인지 알 수 있게 한다
      (원문에 있는 줄이라 근거 찾기에 영향 없음)."""
    lines = text.split("\n")
    starts, heads, fence, title = [0], ["(도입)"], None, None
    for i, ln in enumerate(lines):
        s = ln.rstrip("\r")
        if m := FENCE.match(s):
            mark = m.group(1)
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        if s.startswith("## "):
            starts.append(i)
            heads.append(s[3:].strip())
        elif s.startswith("# ") and title is None:
            title = s
    starts.append(len(lines))
    sections = [(h, "\n".join(lines[a:b])) for h, a, b in zip(heads, starts, starts[1:])]
    sections = [(h, t) for h, t in sections if t.strip()]

    # 작은 섹션을 이웃과 합치기
    chunks: list[list] = []            # [[제목들], 텍스트, 토큰]
    for h, t in sections:
        n = count_tokens(t)
        if chunks and chunks[-1][2] < min_tokens and chunks[-1][2] + n <= max_tokens:
            chunks[-1][0].append(h)
            chunks[-1][1] += "\n" + t
            chunks[-1][2] += n
        else:
            chunks.append([[h], t, n])
    if len(chunks) > 1 and chunks[-1][2] < min_tokens and chunks[-2][2] + chunks[-1][2] <= max_tokens:
        h, t, n = chunks.pop()
        chunks[-1][0] += h
        chunks[-1][1] += "\n" + t
        chunks[-1][2] += n

    out = []
    for k, (hs, t, _) in enumerate(chunks):
        if k > 0 and title:
            t = title + "\n\n" + t
        out.append((" / ".join(hs), t))
    return out


def load_all_docs(corpus: Corpus, min_tokens: int, max_tokens: int,
                  exclude: list[str]) -> dict[str, Doc]:
    """본문 페이지(kind="page") 중 min_tokens 이상인 것. 목차 페이지(quickstart, index)는
    질문 생성 대상이 아니다. max_tokens 를 넘는 문서는 제외하지 않고 ## 섹션 단위 parts 로
    나눈다. exclude 는 위키 루트 기준 fnmatch 패턴으로 추가로 좁히기만 한다."""
    docs = {}
    for d in corpus.docs("page"):
        if any(fnmatch.fnmatch(d.doc_id, pat) for pat in exclude):
            continue
        text, tokens = d.text, d.tokens
        if tokens < min_tokens:
            continue
        links = [t for t in d.links if corpus.get(t).kind == "page"]
        doc = Doc(d.doc_id, text, tokens, corpus, links)
        if tokens > max_tokens:
            doc.parts = [Doc(d.doc_id, t, count_tokens(t), corpus, links, section=h)
                         for h, t in split_sections(text, min_tokens, max_tokens)]
        docs[d.doc_id] = doc
    return docs


def pick_documents(docs: dict[str, Doc], n: int, seed: int,
                   only_split: str | None = None) -> list[Doc]:
    """분할(dev/test)별로 먼저 나눈 뒤, 각 분할 안에서 폴더별 층화 추출.
    dev 는 n 의 DEV_RATIO 만큼(반올림, 2개 이상 뽑으면 최소 1개) 배정해 작은 실행에서도
    dev 문서가 빠지지 않게 한다. 한쪽 문서가 모자라면 나머지는 다른 쪽에서 채운다.
    only_split 을 주면 그 분할에서만 뽑는다."""
    pools = {s: {k: d for k, d in docs.items() if d.split == s} for s in ("dev", "test")}
    if only_split:
        return _pick_by_folder(pools[only_split], n, seed)
    n = min(n, len(docs))
    n_dev = round(n * DEV_RATIO)
    if n >= 2 and pools["dev"]:
        n_dev = max(n_dev, 1)
    n_dev = min(n_dev, len(pools["dev"]))
    n_test = min(n - n_dev, len(pools["test"]))
    n_dev = min(n - n_test, len(pools["dev"]))
    return _pick_by_folder(pools["dev"], n_dev, seed) + _pick_by_folder(pools["test"], n_test, seed)


def _pick_by_folder(docs: dict[str, Doc], n: int, seed: int) -> list[Doc]:
    """폴더별 층화 추출. 폴더 크기에 비례해 배분하되 폴더마다 최소 1개."""
    groups: dict[str, list[Doc]] = defaultdict(list)
    for d in docs.values():
        groups[d.folder].append(d)

    total = sum(len(g) for g in groups.values())
    n = min(n, total)
    if n <= 0:
        return []
    alloc = {k: 0 for k in groups}
    if n >= len(groups):
        for k in alloc:
            alloc[k] = 1
    left = n - sum(alloc.values())
    # 남은 수는 크기 비례(최대 잉여 방식)로 배분
    quota = {k: left * len(g) / total for k, g in groups.items()}
    for k in alloc:
        alloc[k] += int(quota[k])
    rest = n - sum(alloc.values())
    for k in sorted(groups, key=lambda k: quota[k] - int(quota[k]), reverse=True)[:rest]:
        alloc[k] += 1
    # 폴더 크기를 넘게 배정된 몫은 남는 문서가 많은 폴더로 옮긴다 (n 이 전체에 가까울 때)
    over = sum(max(0, alloc[k] - len(g)) for k, g in groups.items())
    alloc = {k: min(alloc[k], len(g)) for k, g in groups.items()}
    while over:
        k = max(sorted(groups), key=lambda k: len(groups[k]) - alloc[k])
        alloc[k] += 1
        over -= 1

    rng = random.Random(seed)
    picked = []
    for k in sorted(groups):
        g = sorted(groups[k], key=lambda d: d.rel)
        rng.shuffle(g)
        picked.extend(g[:min(alloc[k], len(g))])
    return picked


def pick_partner(unit: Doc, docs: dict[str, Doc], rng: random.Random,
                 fits=lambda u: True) -> tuple[Doc | None, str]:
    """종합형 질문의 짝 (문서 또는 섹션)과 고른 근거("link" / "backlink").
    위키 페이지 간 링크 기준: 1) 이 페이지가 링크하는 페이지  2) 없으면 이 페이지를 링크하는 페이지.
    같은 폴더 무작위 선택은 하지 않는다 (관련 없는 두 페이지를 억지로 엮는 문항이 나옴).
    개발/최종 분할이 섞이지 않도록 같은 split 안에서만 고르고, 두 단위를 합친
    생성 입력이 문맥 예산 안에 드는 것(fits)만 고른다."""
    same = lambda d: d.doc_id != unit.doc_id and d.split == unit.split

    def choose(ids):
        pool = [docs[r] for r in ids if r in docs and same(docs[r])]
        cands = [u for d in pool for u in d.units() if fits(u)]
        return rng.choice(cands) if cands else None

    if (p := choose(unit.links)) is not None:
        return p, "link"
    backlinks = sorted(k for k, d in docs.items() if unit.doc_id in d.links)
    if (p := choose(backlinks)) is not None:
        return p, "backlink"
    return None, ""


# ---------------- 검사 유틸 ----------------

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", s.lower())


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_json_array(text: str) -> list[dict]:
    """LLM 출력에서 JSON 배열만 뽑아낸다."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)]


def answer_leaks_into_question(q: str, a: str) -> bool:
    """정답이 질문 안에 그대로 들어 있으면 순환 질문."""
    a_norm, q_norm = norm(a), norm(q)
    if len(a_norm) < 3:
        return False
    return a_norm in q_norm


COPY_RATIO = 0.5    # 질문 3-gram 중 문서에 있는 비율
COPY_SPAN = 6       # 문서와 연속으로 겹치는 단어 수


def copy_overlap(q: str, docs: list[Doc]) -> tuple[float, bool]:
    """(질문 3-gram 중 문서에 그대로 있는 비율, 6단어 이상 연속 일치 여부)."""
    w = words_of(q)
    q3, q6 = ngrams(w, 3), ngrams(w, COPY_SPAN)
    d3 = set().union(*(d.ngram_sets()[0] for d in docs))
    d6 = set().union(*(d.ngram_sets()[1] for d in docs))
    ratio = len(q3 & d3) / len(q3) if q3 else 0.0
    return round(ratio, 3), bool(q6 & d6)


def locate_evidence(quote: str, docs: list[Doc]) -> list[dict]:
    """인용문의 근거 항목들. 페이지마다 하나씩:
        {"quote": 인용문, "page": 페이지 doc_id,
         "locations": [{"file": 페이지 doc_id, "line": 줄 번호}, ...]}
    종합형에서 두 페이지 모두에서 발견되면 페이지마다 별도 항목. 못 찾으면 []."""
    out = []
    for d in docs:
        if any(e["page"] == d.doc_id for e in out):
            continue                            # 같은 문서의 두 섹션이 함께 오는 경우 대비
        locs = d.corpus.locate_all(d.doc_id, quote)
        if locs:
            out.append({"quote": quote, "page": d.doc_id, "locations": locs})
    return out


# ---------------- 생성 ----------------

def build_prompt(qtype: str, docs: list[Doc], n: int) -> str:
    if qtype == "multi":
        a, b = docs
        return (MULTI_SPEC.replace("{n}", str(n)) + COMMON_RULES
                + f"\n--- PAGE A START ---\n{a.text}\n--- PAGE A END ---"
                + f"\n\n--- PAGE B START ---\n{b.text}\n--- PAGE B END ---")
    return ("Below is a technical documentation page.\n\n"
            + TYPE_SPECS[qtype].replace("{n}", str(n)) + COMMON_RULES
            + f"\n--- DOCUMENT START ---\n{docs[0].text}\n--- DOCUMENT END ---")


MAX_ANSWER_WORDS = {"fact": 20, "code": 20, "procedure": 80, "multi": 60}

# 답이 문서에 없다는 표현 -> 답이 없는 질문
NO_ANSWER = re.compile(
    r"\b(not (explicitly )?(mentioned|specified|stated|provided|documented|defined|described)"
    r"|no explicit|(does|do) not (mention|specify|state|say)|(doesn't|don't) (mention|specify|state|say)"
    r"|no information|not covered|cannot be determined)\b", re.I)

# 유형별로 근거 위치가 하나 이상 있어야 하는 곳: 코드 블록 밖(False) / 안(True)
EVIDENCE_IN_CODE = {
    "fact": False,      # 코드 블록 밖 문장
    "code": True,       # 코드 블록 안의 줄
}

# 문맥 예산: 입력(채팅 템플릿 포함) + 출력 <= num_ctx.
# 출력은 LLM(max_tokens=OUTPUT_RESERVE) 로 실제로 잘라 예산을 보장한다.
# 문항 1개 JSON 은 넉넉히 잡아 약 330 토큰 (질문 30 + 답 80단어 + 엔티티 + 근거 3개).
OUTPUT_RESERVE = 2048
TOKENS_PER_ITEM = 400


def gen_messages(qtype: str, units: list[Doc], n: int) -> list[dict]:
    return [{"role": "system", "content": GEN_SYSTEM},
            {"role": "user", "content": build_prompt(qtype, units, n)}]


def input_budget() -> int:
    return CFG.num_ctx - OUTPUT_RESERVE


def gen_input_tokens(qtype: str, units: list[Doc], n: int) -> int:
    """생성 호출의 실제 입력 토큰 (Qwen 채팅 템플릿 적용)."""
    return count_message_tokens(gen_messages(qtype, units, n))


# ---------------- 실행 로그 ----------------

class RunLog:
    """생성 실행 한 번의 전체 기록. results/logs/dataset_<run_id>.jsonl, 한 줄에 이벤트 하나.

    이벤트
        run_start  설정, 명령 인자, 대상 문서
        llm_call   LLM 호출 1회: 단계, 보낸 메시지 원문, 받은 답변 원문, 토큰·시간
        candidate  후보 문항 1개: LLM이 낸 원본, 단계별 판정(trace), 최종 문항, 제외 사유
        error      예외로 건너뛴 생성 단위
        partner    종합형 짝 문서와 고른 근거 (link: 링크하는 페이지, backlink: 링크받는 페이지)
        saved      후보 ID -> 평가셋 문항 ID 대응
        run_end    집계

    candidate.trace 의 각 단계는 해당 llm_call 의 call 번호를 가리킨다.
    이벤트는 발생 즉시 기록하므로 중간에 멈춰도 그때까지의 기록은 남는다.
    """

    def __init__(self, llm: LLM):
        self.llm = llm
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_dir = CFG.results_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"dataset_{self.run_id}.jsonl"
        k = 2
        while self.path.exists():
            self.path = log_dir / f"dataset_{self.run_id}-{k}.jsonl"
            k += 1
        self.calls = 0
        self.cands = 0

    def event(self, event: str, **fields):
        rec = {"event": event, "run_id": self.run_id,
               "time": datetime.now().isoformat(timespec="milliseconds"), **fields}
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def ask(self, step: str, prompt: str, system: str | None = None, **ctx) -> tuple[str, int]:
        """LLM 호출 + 기록. (답변 원문, call 번호)를 돌려준다."""
        self.calls += 1
        call = self.calls
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        base = {
            "call": call, "step": step, **ctx,
            "model": getattr(self.llm, "model", None),
            "temperature": getattr(self.llm, "temperature", None),
            "seed": CFG.seed, "num_ctx": getattr(self.llm, "num_ctx", None),
            "messages": messages,
        }
        try:
            res = self.llm.ask(prompt, system=system)
        except Exception as e:
            self.event("llm_call", **base, error=f"{type(e).__name__}: {e}")
            raise
        self.event("llm_call", **base,
                   response=res.text,
                   prompt_tokens=res.prompt_tokens,
                   completion_tokens=res.completion_tokens,
                   est_prompt_tokens=getattr(res, "est_prompt_tokens", None),
                   ctx_overflow=getattr(res, "ctx_overflow", None),
                   latency=res.latency, ttft=res.ttft,
                   raw=getattr(res, "raw", None))
        return res.text, call

    def new_candidate(self) -> str:
        self.cands += 1
        return f"{self.run_id}-c{self.cands:04d}"


def config_snapshot() -> dict:
    snap = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(CFG).items()}
    if snap.get("api_key"):
        snap["api_key"] = "***"
    return snap


# ---------------- 생성 ----------------


def process_candidate(rec: RunLog, it: dict, qtype: str, docs: list[Doc], doc_text: str,
                      args, trace: list[dict]) -> tuple[dict | None, str | None]:
    """LLM이 낸 후보 하나를 단계별로 검사한다. 모든 판정은 trace 에 남긴다.
    (문항, 제외 사유)를 돌려준다. 통과하면 사유는 None."""
    q = str(it.get("question", "")).strip()
    a = str(it.get("answer", "")).strip()
    trace.append({"step": "parse", "pass": bool(q and a)})
    if not q or not a:
        return None, "질문/답 없음"

    ev = it.get("evidence") or []
    ev = [ev] if isinstance(ev, str) else [str(e) for e in ev]
    ents = it.get("key_entities") or []
    ents = [ents] if isinstance(ents, str) else [str(e).strip() for e in ents]
    facts = it.get("key_facts") or []
    facts = [facts] if isinstance(facts, str) else [str(f).strip() for f in facts]
    facts = [f for f in facts if f]

    trace.append({
        "step": "key_facts",
        "given": facts,
        "count": len(facts),
        "pass": bool(facts),
    })

    if not facts:
        return None, "핵심 사실 없음"

    doc_lower = doc_text.lower()
    # 문서에 실제로 있는 것만 채점 기준으로 남긴다
    kept_ents = [e for e in ents if e and e.lower() in doc_lower]
    fallback = not kept_ents and a.lower() in doc_lower
    if fallback:
        kept_ents = [a]
    trace.append({"step": "key_entities", "given": ents, "kept": kept_ents,
                  "dropped": [e for e in ents if e not in kept_ents],
                  "fallback_to_answer": fallback})

    item = {
        "id": "",
        "split": docs[0].split,
        "type": qtype,
        "question": q,
        "answer": a,
        "key_entities": kept_ents,
        "key_facts": facts,
        "evidence": [],
        # 근거 page 를 중복 없이 정렬. 채점기가 "근거 페이지를 열었는가" 판정에 바로 쓴다
        "evidence_pages": [],
        "source_files": [d.doc_id for d in docs],
        # 섹션 단위로 생성했으면 ## 제목, 문서 전체면 None (source_files 와 같은 순서)
        "sections": [d.section for d in docs],
        "folder": docs[0].folder,
        "doc_tokens": sum(d.tokens for d in docs),
        "copy_overlap": None,
        "original_question": None,
        "verified": None,
        "closed_book_ok": None,
        "human_checked": False,
        "gen_log": None,
    }

    # 문서에 답이 없다는 답 ("There is no explicit limit mentioned" 등)
    m = NO_ANSWER.search(a)
    trace.append({"step": "no_answer", "match": m.group(0) if m else None, "pass": not m})
    if m:
        return item, "답이 없는 질문"

    words = len(a.split())
    ok = words <= MAX_ANSWER_WORDS[qtype]
    trace.append({"step": "answer_length", "words": words,
                  "max": MAX_ANSWER_WORDS[qtype], "pass": ok})
    if not ok:
        return item, "답이 너무 김"

    ok = not answer_leaks_into_question(q, a)
    trace.append({"step": "answer_leak", "pass": ok})
    if not ok:
        return item, "질문에 답 포함"

    # 문서 표현을 그대로 베낀 질문: 바꿔 쓰거나 제거
    ratio, span = copy_overlap(q, docs)
    copied = ratio >= COPY_RATIO or span
    item["copy_overlap"] = ratio
    trace.append({"step": "copy_check", "ratio": ratio, "span_match": span,
                  "copied": copied, "mode": args.copy_mode})
    if copied and args.copy_mode == "drop":
        return item, f"문서 표현 복사 ({ratio})"
    if copied and args.copy_mode == "rewrite":
        resp, call = rec.ask("rewrite", REWRITE_PROMPT.format(q=q, a=a))
        new_q = resp.strip().strip('"')
        new_ratio, new_span = copy_overlap(new_q, docs) if new_q else (0.0, False)
        leak = bool(new_q) and answer_leaks_into_question(new_q, a)
        ok = bool(new_q) and not (new_ratio >= COPY_RATIO or new_span) and not leak
        trace.append({"step": "rewrite", "call": call, "new_question": new_q,
                      "ratio": new_ratio, "span_match": new_span, "answer_leak": leak,
                      "pass": ok})
        if not ok:
            return item, f"바꿔 쓰기 실패 ({ratio} -> {new_ratio})"
        item["original_question"], item["question"] = q, new_q
        item["copy_overlap"] = new_ratio
        q = new_q

    # 근거를 원본 페이지와 모든 위치로 확인. 못 찾은 인용은 버린다
    per_quote = [(e, locate_evidence(e, docs)) for e in ev]
    evidence = [entry for _, entries in per_quote for entry in entries]
    pages = sorted({entry["page"] for entry in evidence})
    item["evidence"] = evidence
    item["evidence_pages"] = pages
    # 종합형은 page 기준으로 두 페이지 모두에 근거가 있어야 통과
    ok = bool(evidence) and (qtype != "multi" or len(pages) >= 2)
    trace.append({"step": "evidence", "pass": ok, "pages": pages, "evidence": evidence,
                  "not_found": [e for e, entries in per_quote if not entries]})
    if not evidence:
        return item, "근거를 원본에서 찾지 못함"
    if not ok:
        return item, "두 페이지 근거가 모두 있지 않음"

    # 유형별 근거 위치: 사실형은 코드 블록 밖 문장, 코드형은 코드 블록 안의 줄에 근거가 있어야 한다
    corpus = docs[0].corpus
    locs = [(loc["file"], loc["line"]) for e in evidence for loc in e["locations"]]
    need = EVIDENCE_IN_CODE.get(qtype)
    if need is not None:
        in_code = [corpus.in_code(f, ln) for f, ln in locs]
        ok = any(c == need for c in in_code)
        trace.append({"step": "evidence_kind", "need": "code" if need else "prose",
                      "locations": [{"file": f, "line": ln, "in_code": c}
                                    for (f, ln), c in zip(locs, in_code)],
                      "pass": ok})
        if not ok:
            return item, "근거 위치가 유형과 맞지 않음"

    # 종합형: 한 페이지에만 있는 핵심 엔티티가 양쪽에 하나 이상씩 있어야 두 페이지가 모두 필요하다
    if qtype == "multi":
        a_low, b_low = docs[0].text.lower(), docs[1].text.lower()
        only_a = [e for e in kept_ents if e.lower() in a_low and e.lower() not in b_low]
        only_b = [e for e in kept_ents if e.lower() in b_low and e.lower() not in a_low]
        ok = bool(only_a) and bool(only_b)
        trace.append({"step": "multi_entities", "only_a": only_a, "only_b": only_b,
                      "pass": ok})
        if not ok:
            return item, "한 페이지로 풀 수 있음"

        # 페이지 하나만 주고 풀게 해서, 어느 한쪽만으로 정답이 나오면 제외
        solved = False
        for step, unit in (("single_page_a", docs[0]), ("single_page_b", docs[1])):
            resp, call = rec.ask(step, SINGLE_PAGE_PROMPT.format(doc=unit.text, q=q))
            knows, rule = closed_book_knows(resp, a, kept_ents)
            trace.append({"step": step, "call": call, "page": unit.doc_id,
                          "section": unit.section, "question": q, "rule": rule,
                          "knows": knows, "pass": not knows})
            solved = solved or knows
        if solved:
            return item, "한 페이지로 풀 수 있음"

    # 아래 검증·문서 없이 풀기는 최종 질문(바꿔 썼으면 바꾼 질문)으로 한다
    if not args.no_verify:
        resp, call = rec.ask("verify", VERIFY_PROMPT.format(doc=doc_text, q=q, a=a))
        item["verified"] = resp.strip().upper().startswith("VALID")
        trace.append({"step": "verify", "call": call, "question": q, "pass": item["verified"]})
        if not item["verified"]:
            return item, "자동 검증 실패"

    if not args.no_closed_book:
        # 문서 없이도 맞히는 질문이면 압축 실험에 쓸 수 없다
        resp, call = rec.ask("closed_book", CLOSED_BOOK_PROMPT.format(q=q))
        knows, rule = closed_book_knows(resp, a, kept_ents)
        item["closed_book_ok"] = not knows
        trace.append({"step": "closed_book", "call": call, "question": q, "rule": rule,
                      "knows": knows, "pass": not knows})
        if knows:
            return item, "문서 없이도 정답"
    return item, None


def generate(rec: RunLog, qtype: str, docs: list[Doc], n: int, args,
             retries: int = 2) -> list[tuple[dict, str | None]]:
    """한 문서(종합형은 두 문서)에서 한 유형의 문항을 만든다.
    [(문항, 제외 사유 또는 None)]을 돌려준다. 모든 후보는 로그에 candidate 로 남는다."""
    prompt = build_prompt(qtype, docs, n)
    sources = [d.doc_id for d in docs]
    # 문맥 예산 확인: 넘치면 Ollama 가 입력 앞부분을 조용히 잘라내므로 호출하지 않는다
    in_tokens = gen_input_tokens(qtype, docs, n)
    if in_tokens > input_budget():
        raise ValueError(f"생성 입력 {in_tokens} 토큰 + 출력 예약 {OUTPUT_RESERVE} "
                         f"> num_ctx {CFG.num_ctx}")
    raw_items, gen_call = [], None
    for attempt in range(retries + 1):
        resp, gen_call = rec.ask("generate", prompt, system=GEN_SYSTEM,
                                 qtype=qtype, sources=sources, attempt=attempt)
        raw_items = parse_json_array(resp)
        if raw_items:
            break

    doc_text = "\n\n".join(d.text for d in docs)
    out = []
    for it in raw_items:
        cand_id = rec.new_candidate()
        trace: list[dict] = []
        item, reject = process_candidate(rec, it, qtype, docs, doc_text, args, trace)
        rec.event("candidate", cand_id=cand_id, qtype=qtype, sources=sources,
                  gen_call=gen_call, llm_output=it, trace=trace,
                  item=item, reject=reject)
        if item is not None:
            item["gen_log"] = {"run_id": rec.run_id, "cand_id": cand_id,
                               "log": rel_root(rec.path)}
            out.append((item, reject))
    return out




# ---------------- 저장 ----------------

DATASET = "qa_dataset.json"
META = "qa_meta.json"


def load_dataset() -> tuple[list[dict], dict]:
    path, meta_path = CFG.eval_dir / DATASET, CFG.eval_dir / META
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    # 근거에 page 가 없던 구 형식은 변환하지 않는다 (시험본이라 버리고 다시 만든다)
    if any("evidence_pages" not in x or any("page" not in e for e in x.get("evidence", []))
           for x in items):
        raise SystemExit(f"구 형식 평가셋입니다. {CFG.eval_dir} 를 비우고 다시 생성하세요")
    meta.setdefault("deleted", [])
    used = [int(re.search(r"(\d+)$", i).group(1)) for i in [x["id"] for x in items] + meta["deleted"] if i]
    meta.setdefault("next_id", max(used, default=0) + 1)
    return items, meta


def save_dataset(items: list[dict], meta: dict):
    CFG.eval_dir.mkdir(parents=True, exist_ok=True)
    dump = lambda p, obj: p.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    dump(CFG.eval_dir / DATASET, items)
    dump(CFG.eval_dir / "qa_dev.json", [x for x in items if x["split"] == "dev"])
    dump(CFG.eval_dir / "qa_test.json", [x for x in items if x["split"] == "test"])
    dump(CFG.eval_dir / META, meta)


def record_corpus(meta: dict, corpus: Corpus, sha: str):
    """평가셋을 만든 코퍼스 매니페스트 해시를 기록. 이전 실행과 다르면 경고하고 이력에 남긴다."""
    prev = meta.get("corpus_manifest_sha256")
    if prev and prev != sha:
        print(f"※ 경고: 코퍼스가 이전 생성 때와 다릅니다 ({prev[:12]} -> {sha[:12]}). "
              f"기존 문항의 근거 줄 번호를 확인하세요.")
        meta.setdefault("corpus_history", []).append(prev)
    meta["corpus_manifest_sha256"] = sha
    meta["corpus_source"] = corpus.source


def assign_ids(new_items: list[dict], meta: dict):
    """새 문항에만 번호를 붙인다. 기존 번호는 절대 바꾸지 않는다.
    번호 앞 글자는 평가셋마다 meta["id_prefix"] (기본 q). 평가셋끼리 번호가 겹쳐 보이지 않게 한다."""
    prefix = meta.get("id_prefix", "q")
    for x in new_items:
        x["id"] = f"{prefix}{meta['next_id']:04d}"
        meta["next_id"] += 1


# ---------------- 명령 ----------------

def cmd_generate(args):
    global DEV_RATIO
    DEV_RATIO = args.dev_ratio
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    bad = set(types) - set(TYPES)
    if bad:
        raise SystemExit(f"알 수 없는 유형: {bad}. 가능: {','.join(TYPES)}")

    if args.per_type * TOKENS_PER_ITEM > OUTPUT_RESERVE:
        raise SystemExit(f"--per-type {args.per_type} 은 출력 예약 {OUTPUT_RESERVE} 토큰을 넘을 수 "
                         f"있습니다 (문항당 약 {TOKENS_PER_ITEM}). "
                         f"{OUTPUT_RESERVE // TOKENS_PER_ITEM} 이하로 주세요.")

    # 모든 호출의 답변 원문은 실행 로그에 남긴다. 출력 상한으로 입력+출력 <= num_ctx 보장
    rec = RunLog(LLM(max_tokens=OUTPUT_RESERVE))
    print(f"설정: {CFG.summary()}")
    corpus = load_corpus()
    corpus_sha = manifest_sha256(corpus)
    print(f"코퍼스: {corpus.source.get('wiki')}  (본문 페이지 {len(corpus.docs('page'))}개, "
          f"매니페스트 {corpus_sha[:12]})")

    all_docs = load_all_docs(corpus, args.min_tokens, args.max_tokens, args.exclude)
    docs = pick_documents(all_docs, args.docs, args.seed, args.only_split)
    if not docs:
        raise SystemExit("조건에 맞는 문서가 없습니다. --min-tokens / --exclude 확인")
    by_folder = Counter(d.folder for d in docs)
    print(f"대상 문서 {len(docs)}개 / 후보 {len(all_docs)}개  "
          f"({', '.join(f'{k} {v}' for k, v in sorted(by_folder.items()))})")
    print(f"유형 {','.join(types)} x {args.per_type}문항")
    print(f"로그: {rel_root(rec.path)}\n")
    rec.event("run_start", config=config_snapshot(), args=vars(args), types=types,
              corpus={"source": corpus.source, "manifest_sha256": corpus_sha},
              docs=[{"doc_id": d.doc_id, "split": d.split, "tokens": d.tokens}
                    for d in docs])

    rng = random.Random(args.seed)
    all_items = []
    budget = input_budget()
    for i, d in enumerate(docs, 1):
        split_note = f", 섹션 {len(d.parts)}개로 나눔" if d.parts else ""
        print(f"[{i}/{len(docs)}] {d.rel} ({d.split}, {d.tokens} tok{split_note})")
        for unit in d.units():
            indent = "    "
            if unit.section is not None:
                print(f"    § {unit.section} ({unit.tokens} tok)")
                indent = "      "
            for t in types:
                group = [unit]
                if t == "multi":
                    fits = lambda u: gen_input_tokens("multi", [unit, u], args.per_type) <= budget
                    partner, how = pick_partner(unit, all_docs, rng, fits)
                    if partner is None:
                        print(f"{indent}{t:9s} -> 짝 문서 없음 (링크로 이어진 페이지 중 같은 분할·예산 "
                              f"조건 맞는 문서 없음), 건너뜀")
                        rec.event("error", qtype=t, sources=[unit.doc_id],
                                  sections=[unit.section], error="짝 문서 없음")
                        continue
                    group = [unit, partner]
                    rec.event("partner", sources=[unit.doc_id, partner.doc_id],
                              sections=[unit.section, partner.section], chosen_by=how)
                try:
                    items = generate(rec, t, group, args.per_type, args)
                except Exception as e:
                    print(f"{indent}{t:9s} -> 실패: {e}")
                    rec.event("error", qtype=t, sources=[x.doc_id for x in group],
                              sections=[x.section for x in group],
                              error=f"{type(e).__name__}: {e}")
                    continue
                ok = sum(1 for _, r in items if not r)
                extra = ""
                if t == "multi":
                    p = group[1]
                    extra = f"  (+ {p.rel}{' § ' + p.section if p.section else ''}, {how})"
                print(f"{indent}{t:9s} -> {len(items)}문항 (통과 {ok}){extra}")
                all_items.extend(items)

                if args.dry_run:
                    print_items(items, indent)

    kept = [x for x, r in all_items if not r]
    reasons = Counter(r.split(" (")[0] for _, r in all_items if r)

    print(f"\n생성 {len(all_items)}문항 -> 통과 {len(kept)}문항")
    for r, c in reasons.most_common():
        print(f"  제외 {c:3d}  {r}")

    summary = {"candidates": len(all_items), "passed": len(kept),
               "rejected": dict(reasons), "llm_calls": rec.calls}
    if args.dry_run:
        rec.event("run_end", dry_run=True, **summary)
        print(f"\n[dry-run] 평가셋은 저장하지 않음 (로그: {rel_root(rec.path)})")
        return
    save_kept(rec, kept, corpus, corpus_sha, summary, args.id_prefix)


def print_items(items: list[tuple[dict, str | None]], indent: str = "    "):
    """--dry-run 화면 출력: 후보마다 통과/제외, 질문, 답, 근거 위치, 제외 사유."""
    for x, r in items:
        persona = f"  [{x['persona']}]" if x.get("persona") else ""
        print(f"{indent}  [{'OK ' if not r else '제외'}] Q: {x['question']}{persona}")
        if x["original_question"]:
            print(f"{indent}         (원래 질문: {x['original_question']})")
        print(f"{indent}         A: {x['answer']}  entities={x['key_entities']}")
        for ev in x["evidence"]:
            locs = ", ".join(f"{l['file']}:{l['line']}" for l in ev["locations"][:3])
            more = f" 외 {len(ev['locations']) - 3}곳" if len(ev["locations"]) > 3 else ""
            print(f"{indent}         근거 [{ev['page']}] "
                  f"{locs}{more}")
        if r:
            print(f"{indent}         사유: {r}")


def save_kept(rec: RunLog, kept: list[dict], corpus: Corpus, corpus_sha: str, summary: dict,
              id_prefix: str | None = None):
    """통과 문항을 기존 평가셋에 이어 붙인다 (같은 유형·질문은 건너뜀, 새 문항에만 번호).
    id_prefix 는 새 평가셋에서만 정할 수 있다 (기존 평가셋과 다르면 중단)."""
    items, meta = load_dataset()
    if id_prefix:
        cur = meta.get("id_prefix", "q" if items else None)
        if cur and cur != id_prefix:
            raise SystemExit(f"이 평가셋의 번호 접두어는 '{cur}' 입니다 (--id-prefix {id_prefix} 와 다름)")
        meta["id_prefix"] = id_prefix
    seen = {(x["type"], norm(x["question"])) for x in items}
    new = []
    for x in kept:
        k = (x["type"], norm(x["question"]))
        if k not in seen:
            seen.add(k)
            new.append(x)
    assign_ids(new, meta)
    items.extend(new)
    record_corpus(meta, corpus, corpus_sha)
    save_dataset(items, meta)
    rec.event("saved", ids={x["gen_log"]["cand_id"]: x["id"] for x in new},
              duplicates=[x["gen_log"]["cand_id"] for x in kept if not x["id"]])
    rec.event("run_end", dry_run=False, added=len(new), total=len(items), **summary)

    print(f"\n새로 추가 {len(new)}문항 (중복 {len(kept) - len(new)}) -> 전체 {len(items)}문항")
    print(f"저장: {CFG.eval_dir / DATASET}  (+ qa_dev.json / qa_test.json)")
    print(f"로그: {rel_root(rec.path)}")
    print("\n※ 다음 단계: python src/dataset_builder.py --review 로 사람 검수를 진행하세요.")


# ---------------- 외부 생성 후보 (--list-targets / --import) ----------------
# 질문 후보를 Ollama 대신 다른 생성기(예: Claude)가 만들고, 검사·필터·저장은 위와 같은
# process_candidate / save_kept 로 한다. 문서 없이 풀기와 종합형 한 페이지 검사는
# 실험 모델(config.model) 기준이어야 하므로 그대로 Ollama 로 한다.

CANDIDATES_DIR = "candidates"
PERSONAS = ("beginner", "intermediate", "advanced")


def partner_candidates(d: Doc, docs: dict[str, Doc]) -> tuple[list[str], str]:
    """종합형 짝 후보 (pick_partner 와 같은 기준, 무작위 선택 없이 전부).
    같은 split 안에서 이 페이지가 링크하는 본문 페이지, 없으면 이 페이지를 링크하는 본문 페이지."""
    same = lambda k: k != d.doc_id and k in docs and docs[k].split == d.split
    links = sorted({k for k in d.links if same(k)})
    if links:
        return links, "link"
    back = sorted(k for k, o in docs.items() if same(k) and d.doc_id in o.links)
    return back, ("backlink" if back else "")


def cmd_list_targets(args):
    corpus = load_corpus()
    docs = load_all_docs(corpus, args.min_tokens, args.max_tokens, args.exclude)
    rows = []
    for d in sorted(docs.values(), key=lambda d: (d.split, d.doc_id)):
        partners, how = partner_candidates(d, docs)
        rows.append({"doc_id": d.doc_id, "split": d.split, "tokens": d.tokens,
                     "folder": d.folder, "partners": partners, "partners_by": how})

    print(f"{'split':5s} {'tokens':>6s}  {'doc_id':45s} 종합형 짝 후보")
    for r in rows:
        by = f" ({r['partners_by']})" if r["partners"] else ""
        print(f"{r['split']:5s} {r['tokens']:6d}  {r['doc_id']:45s} "
              f"{', '.join(r['partners']) or '-'}{by}")
    c = Counter(r["split"] for r in rows)
    print(f"\n본문 페이지 {len(rows)}개 (dev {c['dev']} / test {c['test']}), "
          f"짝 후보 있는 페이지 {sum(1 for r in rows if r['partners'])}개")

    out = CFG.eval_dir / CANDIDATES_DIR / "targets.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"corpus_manifest_sha256": manifest_sha256(corpus),
                               "min_tokens": args.min_tokens, "max_tokens": args.max_tokens,
                               "targets": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {rel_root(out)}")


def import_sources(it: dict, qtype: str, corpus: Corpus,
                   docs: dict[str, Doc]) -> tuple[list[Doc] | None, str | None]:
    """후보의 source_pages -> Doc 목록. 쓸 수 없으면 (None, 제외 사유)."""
    pages = it.get("source_pages") or []
    pages = [pages] if isinstance(pages, str) else [str(p).strip() for p in pages]
    need = 2 if qtype == "multi" else 1
    if len(pages) != need:
        return None, f"source_pages 개수 오류 ({len(pages)}개, {need}개 필요)"
    out = []
    for p in pages:
        if p not in corpus:
            return None, f"없는 페이지 ({p})"
        if corpus.get(p).kind != "page":
            return None, f"목차 페이지 ({p})"
        if p not in docs:
            return None, f"생성 대상 아닌 페이지 ({p})"
        out.append(docs[p])
    if qtype == "multi" and out[0].split != out[1].split:
        return None, "짝이 다른 분할 (dev/test 섞임)"
    return out, None


def cmd_import(args):
    path = Path(args.import_file)
    if not path.is_file():
        raise SystemExit(f"후보 파일이 없습니다: {path}")
    if not args.generator:
        raise SystemExit("--import 에는 --generator (후보를 만든 모델 이름)가 필요합니다")

    lines = path.read_text(encoding="utf-8").splitlines()
    rec = RunLog(LLM(max_tokens=OUTPUT_RESERVE))
    corpus = load_corpus()
    corpus_sha = manifest_sha256(corpus)
    docs = load_all_docs(corpus, args.min_tokens, args.max_tokens, args.exclude)
    print(f"설정: {CFG.summary()}")
    print(f"후보: {path.as_posix()} ({sum(1 for l in lines if l.strip())}개, 생성 {args.generator})")
    print(f"검사: copy-mode {args.copy_mode}, verify {'on' if not args.no_verify else 'off'}, "
          f"closed-book on ({CFG.model})")
    print(f"로그: {rel_root(rec.path)}\n")
    rec.event("run_start", mode="import", candidates_file=path.as_posix(),
              generator=args.generator, config=config_snapshot(), args=vars(args),
              corpus={"source": corpus.source, "manifest_sha256": corpus_sha})

    results: list[tuple[dict | None, str | None, str, str, int]] = []  # (문항, 사유, 유형, persona, 줄)
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        cand_id = rec.new_candidate()
        try:
            it = json.loads(line)
        except json.JSONDecodeError as e:
            rec.event("candidate", cand_id=cand_id, line=lineno, reject=f"JSON 오류: {e}")
            results.append((None, "JSON 오류", "?", "?", lineno))
            continue
        qtype = str(it.get("type", "")).strip()
        persona = str(it.get("persona", "")).strip()
        trace: list[dict] = []
        item, reject, sources = None, None, it.get("source_pages")
        if qtype not in TYPES:
            reject = f"알 수 없는 유형 ({qtype})"
        elif persona not in PERSONAS:
            reject = f"알 수 없는 persona ({persona})"
        else:
            units, reject = import_sources(it, qtype, corpus, docs)
            if units is not None:
                sources = [d.doc_id for d in units]
                doc_text = "\n\n".join(d.text for d in units)
                item, reject = process_candidate(rec, it, qtype, units, doc_text, args, trace)
        if item is not None:
            item["persona"] = persona
            item["gen_log"] = {"generator": args.generator, "candidates_file": path.as_posix(),
                               "line": lineno, "run_id": rec.run_id, "cand_id": cand_id,
                               "log": rel_root(rec.path)}
        rec.event("candidate", cand_id=cand_id, line=lineno, qtype=qtype, persona=persona,
                  sources=sources, llm_output=it, trace=trace, item=item, reject=reject)
        results.append((item, reject, qtype, persona, lineno))
        mark = "OK " if item is not None and not reject else "제외"
        print(f"[{lineno:3d}] {mark} {qtype:9s} {persona:12s} "
              f"{', '.join(sources) if isinstance(sources, list) else sources}"
              + (f"  - {reject}" if reject else ""), flush=True)
        if args.dry_run and item is not None:
            print_items([(item, reject)], "      ")

    kept = [x for x, r, *_ in results if x is not None and not r]
    reasons = Counter(r.split(" (")[0] for _, r, *_ in results if r)
    print(f"\n후보 {len(results)}개 -> 통과 {len(kept)}개")
    for r, c in reasons.most_common():
        print(f"  제외 {c:3d}  {r}")

    print(f"\n{'유형':10s}" + "".join(f"{p:>14s}" for p in PERSONAS) + f"{'합계':>10s}")
    for t in TYPES:
        row = [(sum(1 for x, r, qt, pe, _ in results if qt == t and pe == p and x is not None and not r),
                sum(1 for _, _, qt, pe, _ in results if qt == t and pe == p)) for p in PERSONAS]
        tot = (sum(a for a, _ in row), sum(b for _, b in row))
        print(f"{t:10s}" + "".join(f"{f'{a}/{b}':>14s}" for a, b in row) + f"{f'{tot[0]}/{tot[1]}':>10s}")
    print("(통과/후보)")

    summary = {"candidates": len(results), "passed": len(kept),
               "rejected": dict(reasons), "llm_calls": rec.calls}
    if args.dry_run:
        rec.event("run_end", dry_run=True, **summary)
        print(f"\n[dry-run] 평가셋은 저장하지 않음 (로그: {rel_root(rec.path)})")
        return
    save_kept(rec, kept, corpus, corpus_sha, summary, args.id_prefix)


def cmd_review(args):
    items, meta = load_dataset()
    if not items:
        raise SystemExit("qa_dataset.json이 없습니다. 먼저 생성하세요.")
    todo = [x for x in items if not x["human_checked"]]
    if not todo:
        print("검수할 항목이 없습니다.")
        return

    print(f"검수 대기 {len(todo)}문항. [Enter]=통과  d=삭제  e=답 수정  "
          f"k=핵심 엔티티 수정  q=저장 후 종료\n")
    removed = 0
    for i, x in enumerate(todo, 1):
        print(f"--- [{i}/{len(todo)}] {x['id']}  {x['type']}  {x['split']}  "
              f"persona {x.get('persona') or '-'}")
        print(f"출처: {', '.join(x['source_files'])}")
        print(f"Q: {x['question']}")
        if x.get("original_question"):
            print(f"   (원래 질문: {x['original_question']})")
        print(f"A: {x['answer']}")
        print(f"핵심 엔티티: {x['key_entities']}")
        print(f"근거 페이지: {', '.join(x['evidence_pages'])}")
        for ev in x["evidence"][:3]:
            loc = ev["locations"][0]
            more = f" (위치 {len(ev['locations'])}곳)" if len(ev["locations"]) > 1 else ""
            print(f"근거: [{ev['page']}] {loc['file']}:{loc['line']}{more}  "
                  f"{squash(ev['quote'])[:120]}")
        cmd = input("> ").strip().lower()

        if cmd == "q":
            break
        if cmd == "d":
            x["_delete"] = True
            removed += 1
            print()
            continue
        if cmd == "e":
            new = input("  새 정답: ").strip()
            if new:
                x["answer"] = new
        if cmd in ("e", "k"):
            new = input("  핵심 엔티티(쉼표 구분, Enter=유지): ").strip()
            if new:
                x["key_entities"] = [e.strip() for e in new.split(",") if e.strip()]
        x["human_checked"] = True
        print()

    # 삭제해도 다른 문항 번호는 그대로. 삭제된 번호는 기록만 하고 재사용하지 않는다
    meta["deleted"].extend(x["id"] for x in items if x.get("_delete"))
    items = [x for x in items if not x.get("_delete")]
    save_dataset(items, meta)

    checked = sum(1 for x in items if x["human_checked"])
    print(f"저장 완료: 전체 {len(items)}문항 (검수 완료 {checked}, 삭제 {removed})")


def cmd_stats(args):
    items, meta = load_dataset()
    if not items:
        raise SystemExit("qa_dataset.json이 없습니다.")
    files = {f for x in items for f in x["source_files"]}
    checked = sum(1 for x in items if x["human_checked"])
    toks = [x["doc_tokens"] for x in items]
    print(f"문항 수    : {len(items)}  (다음 번호 {meta.get('id_prefix', 'q')}{meta['next_id']:04d}, "
          f"삭제 {len(meta['deleted'])})")
    print(f"출처 문서  : {len(files)}개")
    print(f"사람 검수  : {checked}/{len(items)}")
    print(f"문서 길이  : 평균 {sum(toks)//len(toks)} / 최소 {min(toks)} / 최대 {max(toks)} 토큰")

    print(f"\n{'':10s}" + "".join(f"{t:>10s}" for t in TYPES) + f"{'합계':>8s}")
    for s in ("dev", "test"):
        c = Counter(x["type"] for x in items if x["split"] == s)
        print(f"{s:10s}" + "".join(f"{c[t]:10d}" for t in TYPES) + f"{sum(c.values()):10d}")
    print(f"\n{'persona':14s}" + "".join(f"{t:>10s}" for t in TYPES) + f"{'합계':>8s}")
    for p in PERSONAS + ("-",):
        c = Counter(x["type"] for x in items if (x.get("persona") or "-") == p)
        if p == "-" and not c:
            continue
        print(f"{p:14s}" + "".join(f"{c[t]:10d}" for t in TYPES) + f"{sum(c.values()):10d}")
    print("\n폴더별: " + ", ".join(f"{k} {v}" for k, v in
                                sorted(Counter(x["folder"] for x in items).items())))


# ---------------- 진입점 ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=30, help="대상 문서 수 (폴더별 층화 추출)")
    ap.add_argument("--per-type", type=int, default=1, help="문서당 유형별 문항 수")
    ap.add_argument("--types", default=",".join(TYPES),
                    help=f"생성할 유형 (쉼표 구분): {','.join(TYPES)}")
    ap.add_argument("--min-tokens", type=int, default=600, help="너무 짧은 문서 제외")
    ap.add_argument("--max-tokens", type=int, default=12000,
                    help="생성 단위 길이 상한. 넘는 문서는 제외하지 않고 ## 섹션 단위로 나눠 생성")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="추가로 제외할 본문 페이지 패턴 (위키 루트 기준, fnmatch)")
    ap.add_argument("--dev-ratio", type=float, default=0.2,
                    help="개발용 비율 (문서 단위, 경로 해시로 고정)")
    ap.add_argument("--copy-mode", choices=("rewrite", "drop", "off"),
                    help="문서 표현을 베낀 질문 처리: 바꿔 쓰기 / 제거 / 검사 안 함 "
                         "(기본: 생성 rewrite, --import drop)")
    ap.add_argument("--only-split", choices=("dev", "test"),
                    help="이 분할의 문서에서만 생성 (기본: dev 를 --dev-ratio 비율로 섞음)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-verify", action="store_true", help="LLM 자동 검증 생략(빠름)")
    ap.add_argument("--verify", action="store_true",
                    help="--import 에서 LLM 자동 검증 켜기 (기본은 끔: 외부 생성 문항을 7B 로 검증하지 않음)")
    ap.add_argument("--no-closed-book", action="store_true",
                    help="문서 없이도 맞히는 질문 걸러내기 생략(빠름)")
    ap.add_argument("--dry-run", action="store_true", help="저장하지 않고 화면 출력만")
    ap.add_argument("--review", action="store_true", help="대화형 검수 모드")
    ap.add_argument("--stats", action="store_true", help="현재 평가셋 통계")
    ap.add_argument("--list-targets", action="store_true",
                    help="본문 페이지별 split·토큰·종합형 짝 후보 출력 (+ data/eval/candidates/targets.json)")
    ap.add_argument("--import", dest="import_file", metavar="FILE.jsonl",
                    help="외부에서 만든 후보 파일을 검사·필터해 평가셋에 추가")
    ap.add_argument("--generator", help="--import 후보를 만든 모델 이름 (gen_log 에 기록)")
    ap.add_argument("--id-prefix", help="새 평가셋의 문항 번호 앞 글자 (기본 q, 예: c -> c0001)")
    args = ap.parse_args()

    if args.import_file:
        # 외부 생성 문항: 베낀 질문은 Qwen 으로 바꿔 쓰지 않고 제외, 7B 검증은 기본 끔,
        # 문서 없이 풀기·종합형 한 페이지 검사는 실험 모델 기준이라 항상 한다
        args.copy_mode = args.copy_mode or "drop"
        args.no_verify = not args.verify
        if args.no_closed_book:
            print("※ --import 에서는 문서 없이 풀기 검사를 끌 수 없습니다 (무시함)")
        args.no_closed_book = False
    else:
        args.copy_mode = args.copy_mode or "rewrite"

    if args.list_targets:
        cmd_list_targets(args)
    elif args.import_file:
        cmd_import(args)
    elif args.review:
        cmd_review(args)
    elif args.stats:
        cmd_stats(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()
