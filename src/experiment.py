"""
압축 실험 실행기 (A/B 비교)

평가셋 문항마다 다음 과정을 압축기별로 실행하고 결과를 기록한다.

    질문
      -> 근거 문서(evidence_pages)의 원문 문맥 구성
      -> LLM 입력(system 지시문 + 문맥 + 질문) 압축. 압축기마다 targets 에 든 부분만 줄인다
      -> 압축된 세 부분으로 답변 메시지를 조립해 LLM 답변 생성
      -> 자동 평가
      -> 결과 저장

RAG 검색 단계는 두지 않는다.
문맥은 문항의 정답 근거 페이지를 코퍼스(OpenWiki 위키)에서 원문 그대로 꺼낸다.

압축기 "none"은 압축하지 않은 원문 입력을 사용하는 기준선(Baseline)이다.
압축기는 ">" 로 이어 붙일 수 있다 (예: "rule>llmlingua2", 앞 단계 출력이 다음 단계 입력).
같은 문항을 none과 각 압축기에 연달아 실행하여 문항 단위로 비교한다.


평가 데이터

평가셋의 각 문항은 주요하게 다음 정보를 사용한다.

    question
        LLM에게 제시할 질문

    answer
        기준 정답

    key_entities
        정답과 관련된 핵심 용어, 함수명, 파라미터명, 값 등의 문자열.
        압축 후 문맥에 핵심 정보가 남아 있는지 확인할 때 사용한다.

    key_facts
        정답이 반드시 전달해야 하는 핵심 사실 목록.
        생성된 답변이 각 핵심 사실을 얼마나 충족하는지 평가할 때 사용한다.

    evidence_pages
        정답의 근거가 존재하는 문서 페이지.
        실험에 사용할 원본 문맥을 구성할 때 사용한다.


최종 평가 지표 (v1)

토큰은 모두 Qwen 토크나이저로 센다. 입력 토큰(input_tokens)은 llm.count_message_tokens 로 센
실제 답변 메시지 전체(채팅 템플릿 포함)이고, 부분별 토큰(system/context/question_tokens)은 각 부분 글자만 센다.

1. 입력 토큰 절감률 (input_reduction_pct)  <- 주 지표 (목표 50%)

    1 - (압축 후 입력 토큰 / 압축 전 입력 토큰)

    지시문 + 문맥 + 질문을 합친 LLM 입력이 얼마나 줄었는지. 예전 주 지표였던
    문맥 토큰 절감률(reduction_pct)은 보조 지표로 남긴다.


2. 순 입력 토큰 절감률 (net_input_reduction_pct)

    압축 과정에서 LLM이 사용한 입력/출력 토큰까지 비용으로 포함한다.

    1 - ((압축 후 입력 토큰 + 압축 과정 LLM 토큰) / 압축 전 입력 토큰)

    LLM을 사용하지 않는 압축기의 경우 압축 과정 LLM 토큰은 0이다.


3. 의미 유사도 (semantic_sim)

    압축 전 문맥과 압축 후 문맥을 임베딩한 뒤 코사인 유사도를 계산한다.

    원문과 압축본의 전체적인 의미가 얼마나 유지되었는지 확인하기 위한 지표다.
    --semantic 옵션을 사용한 경우에만 계산한다.

    임베딩 모델은 config의 embed_model 설정을 사용한다.
    3·4번은 문맥 기준이다. 질문이 압축된 경우는 question_changed=True 로 따로 표시한다.


4. 핵심 엔티티 보존율 (entity_retention)

    평가 데이터의 key_entities 중 몇 개가 압축 후 문맥에 그대로 남아 있는지 측정한다.

    보존된 key_entities 수 / 전체 key_entities 수

    압축 과정에서 중요한 이름, 값, 함수, 파라미터 등의 정보가
    삭제되었는지 확인하기 위한 지표다.


5. 답변 정확도 (answer_accuracy)

    압축된 문맥을 기반으로 생성한 답변이 평가 데이터의 key_facts를
    얼마나 충족하는지 측정한다.

    각 key_fact의 충족 여부를 채점한 뒤 다음과 같이 계산한다.

    충족한 key_facts 수 / 전체 key_facts 수

    따라서 단순 정답/오답뿐 아니라 정답에 필요한 사실 중
    어느 정도를 전달했는지 0~1 사이의 값으로 기록할 수 있다.


6. 답변 정확도 유지율 (answer_accuracy_retention_pct)

    압축하지 않은 none 기준선의 답변 정확도와
    압축 후 답변 정확도를 비교한다.

    압축 후 답변 정확도 / none 답변 정확도 * 100

    입력을 압축하면서 원문 입력에서 얻을 수 있었던 답변 성능을
    얼마나 유지했는지 확인하기 위한 지표다.


7. 의미 손실률 (semantic_loss)

    max(1 - 의미 유사도, 1 - 핵심 엔티티 보존율)

    둘 다 있을 때만 계산한다 (--semantic 이고 문항에 key_entities 가 있을 때).
    summary 에는 평균과 5% 이내 문항 비율(semantic_loss_within_5pct)을 남긴다.


보조 기록

최종 6개 평가 지표와 별도로 기존 실험 코드와의 호환 및 분석을 위해
다음 정보도 trials.jsonl 등에 기록한다.

    correct
        기존 grader의 최종 정답/오답 판정

    match
        규칙 기반 문자열/엔티티 일치 판정

    judge
        기존 LLM judge 판정

    answer_in_context
        짧은 기준 정답이 압축 문맥에 그대로 남아 있는지 여부

    TTFT / latency
        답변 생성 속도 분석용

    ctx_overflow
        LLM 문맥 길이 초과 여부

    reduction_pct
        문맥 토큰 절감률 (예전 주 지표, 지금은 보조)

    answer_format / completion_tokens / not_found
        답변 형식 줄 키(문항 type, 없거나 모르면 default), 답변 출력 토큰, 답변이 "NOT FOUND" 로 시작했는지.
        not_found 이면 answer_accuracy 를 0 으로 둔다 (judge 판정은 answer_accuracy_judged).
        평가셋의 persona 필드는 기록용이라 실험·집계에 쓰지 않는다.


유형별 집계

    summary 의 by_type 에 type 별 답변 정확도, 정답률, NOT FOUND 비율, 평균 출력 토큰을 남기고,
    같은 네 값의 type 균등 가중 평균(유형별 평균의 평균)을 *_type_avg 로 전체 값 옆에 둔다.
    평가셋의 유형별 문항 수가 달라도 유형 간 비교가 한쪽으로 쏠리지 않게 하기 위함이다.


답변 지시문

    src/prompts/answer_<버전>.md 에서 읽는다 (--answer-prompt, 기본 v1).
    사용한 버전은 trials.jsonl 의 answer_prompt, summary.json 의 config.answer_prompt 에 남는다.
    지시문 v1 이전 결과와는 비교할 수 없다.


사용법

    python3 src/experiment.py

        기본 dev 문항에 대해 none과 rule 압축기를 비교한다.

    python3 src/experiment.py --split all --limit 5

        전체 평가셋 중 앞의 5문항만 실행한다.

    python3 src/experiment.py --compressors none,rule --semantic

        의미 유사도 계산까지 포함하여 실행한다.

    python3 src/experiment.py --no-judge

        LLM judge를 사용하지 않는다.
        key_facts 기반 답변 정확도 역시 LLM judge가 없으면 계산되지 않는다.

    python3 src/experiment.py --judge-mode per_fact

        key_facts 를 처음부터 fact 하나당 judge 호출 1회로 판정한다 (기본 batch).
        batch 는 응답 index 가 0..N-1 과 다르면 1회 재요청하고, 그래도 다르면 fact 별 판정으로 폴백한다.
        사용한 judge 프롬프트 버전·해시·모드는 trials.jsonl 의 judge_* 필드에 남는다.


저장 위치

    results/runs/<run_id>/

        trials.jsonl
            문항 x 압축기 단위의 상세 실험 결과.
            각 문항의 6개 평가 지표 계산에 필요한 값과
            key_facts별 채점 결과를 기록한다.

        summary.json
            압축기별 최종 집계 결과.
            6개 평가 지표의 평균 및 비교 결과를 기록한다.

        contexts/
            각 문항의 압축 결과 문맥.
            <문항ID>.<압축기>.md 형식으로 저장하여
            실제 압축 결과를 직접 확인할 수 있다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import math
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compressors import PromptParts, get_compressor
from config import CFG
from corpus import load_corpus
from grader import (
    FACT_JUDGE_PROMPT_HASH,
    FACT_JUDGE_PROMPT_VERSION,
    JUDGE_MODES,
    contains_words,
    grade,
    grade_answer_accuracy,
    is_short,
    word_tokens,
)
from llm import LLM, count_message_tokens, count_tokens

ANSWER_MAX_TOKENS = 512
FACT_JUDGE_MAX_TOKENS = 512      # key_facts judge JSON 출력 한도
TYPES = ("fact", "code", "procedure", "multi")   # 유형별 집계 순서

# 답변 지시문은 src/prompts/answer_<버전>.md 에 둔다 (바꾸면 이전 결과와 비교할 수 없으므로 새 버전으로)
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
NOT_FOUND = "NOT FOUND"


@dataclass
class AnswerPrompt:
    version: str
    sha256: str                     # 파일 해시 앞 12자리 (같은 버전 이름으로 내용이 바뀌었는지 확인용)
    system: str                     # {answer_format} 자리에 문항 type 의 형식 줄을 넣는다
    user: str                       # {context}, {question} 를 채우는 틀 (문서 + 질문만)
    format: dict[str, str]          # type -> 지시 한 줄. "default" 는 type 이 없거나 모르는 값일 때

    def format_key(self, qtype: str | None) -> str:
        return qtype if qtype in self.format and qtype != "default" else "default"

    def parts(self, context: str, question: str, qtype: str | None) -> PromptParts:
        """압축 전 입력 세 부분. system 은 형식 줄을 끼운 뒤의 전체 (압축 대상)."""
        fmt = self.format[self.format_key(qtype)]
        return PromptParts(system=self.system.replace("{answer_format}", fmt), context=context, question=question)

    def messages(self, parts: PromptParts) -> list[dict]:
        user = self.user.format(context=parts.context, question=parts.question)
        return [{"role": "system", "content": parts.system}, {"role": "user", "content": user}]


def answer_prompt_versions() -> list[str]:
    return sorted(p.stem.removeprefix("answer_") for p in PROMPTS_DIR.glob("answer_*.md"))


def load_answer_prompt(version: str) -> AnswerPrompt:
    path = PROMPTS_DIR / f"answer_{version}.md"
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    sections, cur = {}, None
    for line in text.split("\n"):
        m = re.match(r"## (\w+)\s*$", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
        elif cur:
            sections[cur].append(line)
    sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    missing = {"system", "format", "user"} - sections.keys()
    if "{answer_format}" not in sections.get("system", ""):
        missing.add("system 의 {answer_format}")
    if missing:
        sys.exit(f"{path}: 섹션이 없습니다: {sorted(missing)}")
    fmt = dict(re.findall(r"^- (\w+):[ \t]*(.+?)\s*$", sections["format"], re.M))
    if "default" not in fmt:
        sys.exit(f"{path}: format 에 default 줄이 없습니다")
    if "TODO:" in sections["system"] or any("TODO:" in v for v in fmt.values()):
        sys.exit(f"{path}: 아직 채우지 않은 TODO 가 있습니다")
    return AnswerPrompt(version=version, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
                        system=sections["system"], user=sections["user"], format=fmt)


def is_not_found(response: str) -> bool:
    return response.strip().startswith(NOT_FOUND)


# ---------------- 로그 형식 (팀 Spec 이 정해지면 여기만 고친다) ----------------

@dataclass
class TrialRecord:
    run_id: str
    qid: str
    split: str
    qtype: str
    answer_prompt: str              # 답변 지시문 버전 (src/prompts/answer_<버전>.md)
    answer_format: str              # 사용한 형식 줄 키 (문항 type, 없거나 모르면 default)
    compressor: str
    question: str
    answer: str
    evidence_pages: list[str]
    # 입력 토큰 (Qwen 토크나이저). input_* 는 채팅 템플릿 포함 실제 메시지 전체, 나머지는 부분 글자만
    input_tokens_raw: int
    input_tokens: int
    input_reduction_pct: float      # 입력 토큰 절감률 (%) - 주 지표
    net_input_reduction_pct: float  # 압축 LLM 토큰까지 비용으로 넣은 입력 토큰 절감률 (%)
    system_tokens_raw: int
    system_tokens: int
    context_tokens_raw: int
    context_tokens: int
    question_tokens_raw: int
    question_tokens: int
    reduction_pct: float            # 문맥 토큰 절감률 (%) - 보조
    question_changed: bool          # 질문이 압축됐는지 (의미 지표는 문맥 기준이므로 따로 표시)
    question_compressed: str | None # 압축된 질문 (바뀌었을 때만)
    system_compressed: str | None   # 압축된 system (바뀌었을 때만)
    compress_sec: float
    compress_llm_tokens: int        # 압축에 쓴 LLM 토큰 (입력+출력)
    entity_retention: float | None  # 핵심 엔티티 보존율 (엔티티 없으면 None)
    answer_in_context: bool | None  # 짧은 정답이 문맥에 남았는지 (긴 정답이면 None)
    semantic_sim: float | None      # 압축 전후 임베딩 코사인 유사도 (--semantic 일 때)
    semantic_chunks: int | None     # 임베딩 한도를 넘어 나눠 계산한 조각 수 (원문, 압축본 중 큰 쪽)
    semantic_loss: float | None     # max(1 - semantic_sim, 1 - entity_retention). 둘 다 있을 때만
    # 답변
    response: str
    prompt_tokens: int              # 답변 LLM 입력 토큰 (서버 보고값)
    completion_tokens: int          # 답변 출력 토큰
    not_found: bool                 # 답변이 "NOT FOUND" 로 시작 (이 경우 answer_accuracy = 0)
    ttft_sec: float | None
    latency_sec: float
    ctx_overflow: bool              # 입력이 num_ctx 를 넘어 잘렸는지
    # 채점
    correct: bool                     # 기존 O/X 판정 - 기존 코드 호환용
    grade_method: str
    match: bool
    judge: bool | None
    judge_raw: str

    # key_facts 기반 답변 정확도 (not_found 이면 0)
    answer_accuracy: float | None
    answer_accuracy_judged: float | None  # not_found 처리 전 judge 판정 그대로
    satisfied_facts: int | None
    total_facts: int | None
    fact_results: list[dict] = field(default_factory=list)
    # key_facts judge 기록 (grader.grade_answer_accuracy)
    judge_prompt_version: str | None = None   # fact_judge_v2 ...
    judge_prompt_hash: str | None = None      # 프롬프트 문구 해시 앞 12자리
    judge_mode: str | None = None             # batch | retry | per_fact_fallback | per_fact
    judge_retries: int = 0                    # 재요청 횟수 (0 또는 1)
    judge_missing_before_fix: list[int] = field(default_factory=list)  # 첫 응답에서 빠진(중복 포함) index
    judge_calls: int = 0                      # key_facts 판정에 쓴 judge 호출 수

    info: dict = field(default_factory=dict)


# ---------------- 문맥 ----------------

def build_context(corpus, item: dict) -> str:
    parts = []
    for doc_id in item["evidence_pages"]:
        parts.append(f"## Document: {corpus.page_ref(doc_id)}\n\n{corpus.expanded_text(doc_id).strip()}")
    return "\n\n".join(parts).replace("\r\n", "\n")


def entity_retention(entities: list[str], ctx_words: list[str]) -> float | None:
    ents = [e for e in entities if word_tokens(e)]
    if not ents:
        return None
    return sum(contains_words(ctx_words, e) for e in ents) / len(ents)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def embed_long(embedder: LLM, text: str) -> tuple[list[float], int]:
    """(임베딩, 조각 수). 임베딩 모델 한도를 넘으면 빈 줄 경계에서 반으로 나눠 다시 시도하고,
    조각 임베딩을 글자 수 가중 평균한다. 조각이 2개 이상이면 원문과 압축본이 다르게 나뉠 수
    있으므로 유사도 해석에 주의 (TrialRecord.semantic_chunks 로 기록)."""
    try:
        return embedder.embed(text), 1
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 400:
            raise
    mid = len(text) // 2
    cut = text.rfind("\n\n", 0, mid)
    if cut <= 0:
        cut = text.rfind("\n", 0, mid)
    if cut <= 0:
        cut = mid
    parts = [embed_long(embedder, p) for p in (text[:cut], text[cut:]) if p.strip()]
    weights = [len(p) for p in (text[:cut], text[cut:]) if p.strip()]
    dim = len(parts[0][0])
    vec = [sum(w * v[0][i] for w, v in zip(weights, parts)) / sum(weights) for i in range(dim)]
    return vec, sum(v[1] for v in parts)


# ---------------- 실행 ----------------

def load_items(split: str, limit: int | None, ids: list[str] | None) -> list[dict]:
    path = CFG.eval_dir / "qa_dataset.json"
    if not path.is_file():
        sys.exit(f"평가셋이 없습니다: {path}\n  python src/dataset_builder.py 로 먼저 생성하세요")
    items = json.loads(path.read_text(encoding="utf-8"))
    if ids:
        items = [x for x in items if x["id"] in ids]
    elif split != "all":
        items = [x for x in items if x["split"] == split]
    items = [x for x in items if x.get("evidence_pages")]
    return items[:limit] if limit else items


def judge_fields(fact_grade) -> dict:
    """AnswerAccuracyResult 에서 TrialRecord 의 judge_* 필드를 뽑는다 (없으면 기본값)."""
    if fact_grade is None:
        return {}
    return {
        "judge_prompt_version": fact_grade.judge_prompt_version,
        "judge_prompt_hash": fact_grade.judge_prompt_hash,
        "judge_mode": fact_grade.judge_mode,
        "judge_retries": fact_grade.judge_retries,
        "judge_missing_before_fix": fact_grade.judge_missing_before_fix,
        "judge_calls": fact_grade.judge_calls,
    }


def judge_counts(rs) -> dict:
    """judge_mode 별 문항 수와 재요청·누락 합계. rs 는 TrialRecord 또는 같은 키를 가진 dict."""
    get = (lambda r, k: r[k] if isinstance(r, dict) else getattr(r, k))
    judged = [r for r in rs if get(r, "judge_mode")]
    modes: dict[str, int] = {}
    for r in judged:
        modes[get(r, "judge_mode")] = modes.get(get(r, "judge_mode"), 0) + 1
    return {
        "n_judged": len(judged),
        "modes": modes,
        "retries": sum(get(r, "judge_retries") for r in judged),
        "per_fact_fallbacks": modes.get("per_fact_fallback", 0),
        "items_with_missing": sum(bool(get(r, "judge_missing_before_fix")) for r in judged),
        "missing_indices": sum(len(get(r, "judge_missing_before_fix")) for r in judged),
        "calls": sum(get(r, "judge_calls") for r in judged),
    }


def git_head() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(CFG.root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run(args) -> Path:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = CFG.results_dir / "runs" / run_id
    (out_dir / "contexts").mkdir(parents=True, exist_ok=True)

    names = [n.strip() for n in args.compressors.split(",") if n.strip()]
    compressors = [get_compressor(n) for n in names]
    items = load_items(args.split, args.limit, args.ids)
    if not items:
        sys.exit(f"실행할 문항이 없습니다 (split={args.split}). --split all 또는 평가셋 생성을 확인하세요")

    prompt = load_answer_prompt(args.answer_prompt)
    corpus = load_corpus()
    llm = LLM(max_tokens=ANSWER_MAX_TOKENS)
    # 기존 O/X 판정용 Judge
    judge = (
        None
        if args.no_judge
        else LLM(
            model=CFG.judge_model,
            max_tokens=8,
        )
    )

    # key_facts 기반 답변 정확도 평가용 Judge
    # JSON 형식의 평가 결과를 생성해야 하므로 충분한 출력 토큰을 허용한다.
    # (fact 하나당 결과 한 줄이라 key_facts 가 많으면 256 으로는 잘릴 수 있다)
    fact_judge = (
        None
        if args.no_judge
        else LLM(
            model=CFG.judge_model,
            max_tokens=FACT_JUDGE_MAX_TOKENS,
        )
    )
    embedder = LLM() if args.semantic else None

    print(f"설정: {CFG.summary()}  judge={'off' if judge is None else CFG.judge_model}")
    print(f"답변 지시문: {prompt.version} ({prompt.sha256})")
    if fact_judge is not None:
        print(f"key_facts judge: {FACT_JUDGE_PROMPT_VERSION} ({FACT_JUDGE_PROMPT_HASH})  mode={args.judge_mode}")
    print(f"문항 {len(items)}개 x 압축기 {names}  ->  {out_dir.relative_to(CFG.root).as_posix()}")
    print("모델 로딩 (첫 호출은 측정에서 제외)...", flush=True)
    llm.ask("Reply with OK.")

    records: list[TrialRecord] = []
    with open(out_dir / "trials.jsonl", "w", encoding="utf-8") as f:
        for i, item in enumerate(items, 1):
            raw = build_context(corpus, item)
            ents = item.get("key_entities", [])
            fmt_key = prompt.format_key(item.get("type"))
            raw_parts = prompt.parts(raw, item["question"], item.get("type"))
            raw_part_tokens = {k: count_tokens(getattr(raw_parts, k)) for k in ("system", "context", "question")}
            input_raw = count_message_tokens(prompt.messages(raw_parts))
            raw_emb, raw_chunks = embed_long(embedder, raw) if embedder else (None, None)
            print(f"[{i}/{len(items)}] {item['id']} {item['type']:<9} "
                  f"input {input_raw} tok (ctx {raw_part_tokens['context']})", flush=True)

            for comp in compressors:
                t0 = time.perf_counter()
                cres = comp.compress(raw_parts)
                compress_sec = time.perf_counter() - t0
                cparts = cres.parts
                ctx = cparts.context
                part_tokens = {k: count_tokens(getattr(cparts, k)) for k in ("system", "context", "question")}
                ctx_words = word_tokens(ctx)
                fname = comp.name.replace(">", "+")    # 조합 이름의 ">" 는 파일 이름에 못 쓴다
                (out_dir / "contexts" / f"{item['id']}.{fname}.md").write_text(ctx, encoding="utf-8")

                messages = prompt.messages(cparts)
                input_tokens = count_message_tokens(messages)
                compress_llm = cres.llm_prompt_tokens + cres.llm_completion_tokens
                res = llm.chat(messages, stream_ttft=True)
                not_found = is_not_found(res.text)
                g = grade(item["question"], item["answer"], ents, res.text, judge_llm=judge)

                # key_facts 기반 답변 정확도
                facts = item.get("key_facts", [])

                fact_grade = None
                if fact_judge is not None and facts:
                    fact_grade = grade_answer_accuracy(
                        question=item["question"],
                        reference_answer=item["answer"],
                        key_facts=facts,
                        candidate_answer=res.text,
                        judge_llm=fact_judge,
                        mode=args.judge_mode,
                    )

                judged_accuracy = fact_grade.answer_accuracy if fact_grade is not None else None
                answer_accuracy = 0.0 if not_found and facts else judged_accuracy

                sim = chunks = None

                if embedder:
                    if ctx == raw:
                        sim, chunks = 1.0, raw_chunks
                    else:
                        emb, n = embed_long(embedder, ctx)
                        sim, chunks = round(cosine(raw_emb, emb), 4), max(raw_chunks, n)
                ent_ret = entity_retention(ents, ctx_words)
                loss = (round(max(1 - sim, 1 - ent_ret), 4)
                        if sim is not None and ent_ret is not None else None)

                rec = TrialRecord(
                    run_id=run_id, qid=item["id"], split=item["split"], qtype=item["type"],
                    answer_prompt=prompt.version, answer_format=fmt_key, compressor=comp.name,
                    question=item["question"], answer=item["answer"],
                    evidence_pages=item["evidence_pages"],
                    input_tokens_raw=input_raw, input_tokens=input_tokens,
                    input_reduction_pct=round(100 * (1 - input_tokens / input_raw), 2),
                    net_input_reduction_pct=round(100 * (1 - (input_tokens + compress_llm) / input_raw), 2),
                    system_tokens_raw=raw_part_tokens["system"], system_tokens=part_tokens["system"],
                    context_tokens_raw=raw_part_tokens["context"], context_tokens=part_tokens["context"],
                    question_tokens_raw=raw_part_tokens["question"], question_tokens=part_tokens["question"],
                    reduction_pct=(round(100 * (1 - part_tokens["context"] / raw_part_tokens["context"]), 2)
                                   if raw_part_tokens["context"] else 0.0),
                    question_changed=cparts.question != raw_parts.question,
                    question_compressed=cparts.question if cparts.question != raw_parts.question else None,
                    system_compressed=cparts.system if cparts.system != raw_parts.system else None,
                    compress_sec=round(compress_sec, 4),
                    compress_llm_tokens=compress_llm,
                    entity_retention=ent_ret,
                    answer_in_context=contains_words(ctx_words, item["answer"]) if is_short(item["answer"]) else None,
                    semantic_sim=sim, semantic_chunks=chunks, semantic_loss=loss,
                    response=res.text.strip(), prompt_tokens=res.prompt_tokens,
                    completion_tokens=res.completion_tokens, not_found=not_found,
                    ttft_sec=round(res.ttft, 3) if res.ttft is not None else None,
                    latency_sec=round(res.latency, 3), ctx_overflow=res.ctx_overflow,
                    correct=g.correct,
                    grade_method=g.method,
                    match=g.match,
                    judge=g.judge,
                    judge_raw=g.judge_raw,

                    answer_accuracy=answer_accuracy,
                    answer_accuracy_judged=judged_accuracy,
                    satisfied_facts=(
                        fact_grade.satisfied_count
                        if fact_grade is not None
                        else None
                    ),
                    total_facts=(
                        fact_grade.total_count
                        if fact_grade is not None
                        else None
                    ),
                    fact_results=(
                        [asdict(x) for x in fact_grade.fact_results]
                        if fact_grade is not None
                        else []
                    ),
                    **judge_fields(fact_grade),

                    info=cres.info,
                )
                records.append(rec)
                f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
                f.flush()
                print(f"    {comp.name:<6} input {input_raw:>6} -> {input_tokens:<6} ({rec.input_reduction_pct:5.1f}%)  "
                      f"{'O' if g.correct else 'X'} [{g.method}]  out {rec.completion_tokens} tok"
                      f"{'  NOT FOUND' if not_found else ''}  ttft {rec.ttft_sec}s", flush=True)

    summary = {
        "run_id": run_id,
        "time": datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "config": {"llm": CFG.summary(), "judge_model": None if judge is None else CFG.judge_model,
                   "answer_max_tokens": ANSWER_MAX_TOKENS,
                   "answer_prompt": {"version": prompt.version, "sha256": prompt.sha256},
                   "fact_judge": (None if fact_judge is None else
                                  {"prompt_version": FACT_JUDGE_PROMPT_VERSION,
                                   "prompt_hash": FACT_JUDGE_PROMPT_HASH,
                                   "mode": args.judge_mode,
                                   "max_tokens": FACT_JUDGE_MAX_TOKENS}),
                   "semantic": bool(embedder),
                   "split": args.split, "n_items": len(items)},
        "corpus_source": corpus.source,
        "compressors": {c.name: c.config() for c in compressors},
        "results": summarize(records, names),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(summary["results"], names)
    print(f"\n저장: {out_dir.relative_to(CFG.root).as_posix()}/ (trials.jsonl, summary.json, contexts/)")
    return out_dir


# ---------------- 집계 ----------------

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def summarize(records: list[TrialRecord], names: list[str]) -> dict:
    by = {n: [r for r in records if r.compressor == n] for n in names}
    base = {r.qid: r for r in by.get("none", [])}

    out = {}

    for n, rs in by.items():
        if not rs:
            continue

        # --------------------------------------------------
        # 1·2. 입력 토큰 절감률 / 순 입력 토큰 절감률 (+ 보조: 문맥 토큰 절감률)
        # --------------------------------------------------
        # 문항별 비율의 평균이 아니라 전체 토큰 합의 비율 (긴 문항에 가중)
        input_raw = sum(r.input_tokens_raw for r in rs)
        input_comp = sum(r.input_tokens for r in rs)
        raw = sum(r.context_tokens_raw for r in rs)
        comp = sum(r.context_tokens for r in rs)
        extra = sum(r.compress_llm_tokens for r in rs)

        input_reduction_pct = round(100 * (1 - input_comp / input_raw), 2) if input_raw else None
        net_input_reduction_pct = round(100 * (1 - (input_comp + extra) / input_raw), 2) if input_raw else None
        reduction_pct = round(100 * (1 - comp / raw), 2) if raw else None

        losses = [r.semantic_loss for r in rs if r.semantic_loss is not None]

        # --------------------------------------------------
        # 2. 답변 정확도
        # key_facts 충족 비율의 평균
        # --------------------------------------------------
        answer_accuracy = _mean(
            r.answer_accuracy for r in rs
        )

        s = {
            "n": len(rs),

            # 참고용: 부분별 문항 평균 토큰 (압축 전 raw / 후 compressed). input 은 채팅 템플릿 포함 전체
            "tokens": {
                k: {"raw": _mean(getattr(r, f"{k}_tokens_raw") for r in rs),
                    "compressed": _mean(getattr(r, f"{k}_tokens") for r in rs)}
                for k in ("input", "system", "context", "question")
            },
            "compress_llm_tokens": extra,
            "question_changed_rate": round(sum(r.question_changed for r in rs) / len(rs), 4),

            # ===== 최종 평가 지표 =====

            # 1. 입력 토큰 절감률 (주 지표)
            "input_reduction_pct": input_reduction_pct,

            # 2. 순 입력 토큰 절감률
            "net_input_reduction_pct": net_input_reduction_pct,

            # 3. 의미 유사도
            "semantic_sim": _mean(
                r.semantic_sim for r in rs
            ),

            # 4. 핵심 엔티티 보존율
            "entity_retention": _mean(
                r.entity_retention for r in rs
            ),

            # 5. 답변 정확도
            "answer_accuracy": answer_accuracy,

            # 7. 의미 손실률 (6. 유지율은 아래에서 none 과 짝지어 계산)
            "semantic_loss": _mean(losses),
            "semantic_loss_within_5pct": (
                round(sum(x <= 0.05 for x in losses) / len(losses), 4) if losses else None
            ),

            # ===== 보조 지표 =====
            # 문맥 토큰 절감률 (예전 주 지표)
            "reduction_pct": reduction_pct,

            # 기존 코드와 비교/디버깅용
            "binary_accuracy": round(
                sum(r.correct for r in rs) / len(rs), 4
            ),

            "answer_in_context": _mean(
                None
                if r.answer_in_context is None
                else float(r.answer_in_context)
                for r in rs
            ),

            # 답변이 "NOT FOUND" 로 시작한 비율 (이 문항들은 answer_accuracy 0)
            "not_found_rate": round(sum(r.not_found for r in rs) / len(rs), 4),
            "completion_tokens": _mean(r.completion_tokens for r in rs),

            "ttft_sec": _mean(r.ttft_sec for r in rs),
            "latency_sec": _mean(r.latency_sec for r in rs),
            "ctx_overflow": sum(r.ctx_overflow for r in rs),

            # key_facts judge 응답 보정 횟수 (재요청 / fact 별 폴백 / 첫 응답 누락 index 합)
            "fact_judge": judge_counts(rs),
        }

        # --------------------------------------------------
        # 6. 답변 정확도 유지율
        #
        # 같은 질문의 none 결과와 압축 결과를 짝지어 비교
        # --------------------------------------------------
        if base and n != "none":
            paired = [
                (base[r.qid], r)
                for r in rs
                if r.qid in base
                and base[r.qid].answer_accuracy is not None
                and r.answer_accuracy is not None
            ]

            if paired:
                base_answer_accuracy = (
                    sum(b.answer_accuracy for b, _ in paired)
                    / len(paired)
                )

                compressed_answer_accuracy = (
                    sum(r.answer_accuracy for _, r in paired)
                    / len(paired)
                )

                s["answer_accuracy_retention_pct"] = (
                    round(
                        100
                        * compressed_answer_accuracy
                        / base_answer_accuracy,
                        2,
                    )
                    if base_answer_accuracy > 0
                    else None
                )

                # 분석용
                s["baseline_answer_accuracy"] = round(
                    base_answer_accuracy, 4
                )

                s["paired_answer_accuracy"] = round(
                    compressed_answer_accuracy, 4
                )

            else:
                s["answer_accuracy_retention_pct"] = None
                s["baseline_answer_accuracy"] = None
                s["paired_answer_accuracy"] = None

        elif n == "none":
            # baseline 자신은 유지율 비교 대상이 아님
            s["answer_accuracy_retention_pct"] = None

        # type 별 정답률·출력 토큰, 그리고 type 균등 가중 평균 (유형별 평균의 평균)
        s["by_type"] = {}
        for t in sorted({r.qtype for r in rs}, key=lambda t: (TYPES.index(t) if t in TYPES else len(TYPES), t)):
            ts = [r for r in rs if r.qtype == t]
            s["by_type"][t] = {
                "n": len(ts),
                "answer_accuracy": _mean(r.answer_accuracy for r in ts),
                "binary_accuracy": round(sum(r.correct for r in ts) / len(ts), 4),
                "not_found_rate": round(sum(r.not_found for r in ts) / len(ts), 4),
                "completion_tokens": _mean(r.completion_tokens for r in ts),
            }
        for k in ("answer_accuracy", "binary_accuracy", "not_found_rate", "completion_tokens"):
            s[f"{k}_type_avg"] = _mean(v[k] for v in s["by_type"].values())

        out[n] = s

    return out


def print_summary(results: dict, names: list[str]):
    print("\n" + "=" * 64)
    print("압축 실험 평가 결과")
    print("=" * 64)

    for n in names:
        s = results.get(n)
        if not s:
            continue

        input_reduction = s.get("input_reduction_pct")
        net_input = s.get("net_input_reduction_pct")
        reduction = s.get("reduction_pct")
        loss = s.get("semantic_loss")
        within = s.get("semantic_loss_within_5pct")
        semantic = s.get("semantic_sim")
        entity = s.get("entity_retention")
        accuracy = s.get("answer_accuracy")
        retention = s.get("answer_accuracy_retention_pct")

        input_s = "-" if input_reduction is None else f"{input_reduction:.1f}%"
        net_s = "-" if net_input is None else f"{net_input:.1f}%"
        reduction_s = "-" if reduction is None else f"{reduction:.1f}%"
        loss_s = "-" if loss is None else f"{loss * 100:.1f}% (5% 이내 {within * 100:.0f}%)"
        semantic_s = "-" if semantic is None else f"{semantic:.4f}"
        entity_s = "-" if entity is None else f"{entity * 100:.1f}%"
        accuracy_s = "-" if accuracy is None else f"{accuracy * 100:.1f}%"
        retention_s = "-" if retention is None else f"{retention:.1f}%"

        label = f"{n} (Baseline)" if n == "none" else n

        print(f"\n[{label}]")
        print(f"  입력 토큰 절감률   : {input_s}")
        print(f"  순 입력 토큰 절감률: {net_s}")
        print(f"  문맥 토큰 절감률   : {reduction_s}  (보조)")
        print(f"  의미 유사도        : {semantic_s}")
        print(f"  핵심 엔티티 보존율 : {entity_s}")
        print(f"  답변 정확도        : {accuracy_s}")
        print(f"  답변 정확도 유지율 : {retention_s}")
        print(f"  의미 손실률        : {loss_s}")
        print(f"  NOT FOUND 비율     : {s['not_found_rate'] * 100:.1f}%")
        tavg = s.get("answer_accuracy_type_avg")
        print(f"  답변 정확도 (type 균등): {'-' if tavg is None else f'{tavg * 100:.1f}%'}")
        for t, ts in s.get("by_type", {}).items():
            acc = "-" if ts["answer_accuracy"] is None else f"{ts['answer_accuracy'] * 100:.1f}%"
            print(f"    {t:<10} n={ts['n']:<3} 정확도 {acc:>6}  정답 {ts['binary_accuracy'] * 100:5.1f}%  "
                  f"NOT FOUND {ts['not_found_rate'] * 100:5.1f}%  출력 {ts['completion_tokens']} tok")

    print("\n" + "=" * 64)

def main():
    ap = argparse.ArgumentParser(description="압축 실험 실행 (A/B 비교)")
    ap.add_argument("--compressors", default="none,rule", help="쉼표로 구분 (none 이 기준선)")
    ap.add_argument("--split", default="dev", choices=("dev", "test", "all"),
                    help="dev 로 조정하고 test 는 최종 보고에만 사용")
    ap.add_argument("--limit", type=int, help="앞에서부터 N 문항만")
    ap.add_argument("--ids", nargs="*", help="특정 문항만 (예: q0001 q0003). --split 무시")
    ap.add_argument("--no-judge", action="store_true", help="LLM 채점 생략 (긴 정답도 단어 일치로 판정)")
    ap.add_argument("--judge-mode", default="batch", choices=JUDGE_MODES,
                    help="key_facts 판정 방식: batch (한 번에, 불완전하면 재요청/개별 폴백) | per_fact (fact 별 개별 호출)")
    ap.add_argument("--semantic", action="store_true", help="압축 전후 임베딩 유사도 계산 (bge-m3 필요)")
    ap.add_argument("--answer-prompt", default="v1", choices=answer_prompt_versions(),
                    help="답변 지시문 버전 (src/prompts/answer_<버전>.md)")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
