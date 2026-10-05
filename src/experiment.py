"""
압축 실험 실행기 (A/B 비교)

평가셋 문항마다 다음 과정을 압축기별로 실행하고 결과를 기록한다.

    질문
      -> 근거 문서(evidence_pages)의 원문 문맥 구성
      -> 문맥 압축
      -> 압축된 문맥을 기반으로 LLM 답변 생성
      -> 자동 평가
      -> 결과 저장

RAG 검색 단계는 두지 않는다.
문맥은 문항의 정답 근거 페이지를 코퍼스(OpenWiki 위키)에서 원문 그대로 꺼낸다.

압축기 "none"은 압축하지 않은 원문 문맥을 사용하는 기준선(Baseline)이다.
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


최종 평가 지표 (v0)

1. 토큰 절감률 (reduction_pct)

    압축 전 문맥에 비해 압축 후 문맥의 토큰 수가 얼마나 감소했는지 측정한다.

    1 - (압축 후 문맥 토큰 / 압축 전 문맥 토큰)

    값이 높을수록 문맥을 많이 줄였다는 의미다.


2. 순 토큰 절감률 (net_reduction_pct)

    압축 결과의 토큰 수뿐만 아니라 압축 과정에서 LLM이 사용한
    입력/출력 토큰까지 비용으로 포함한다.

    1 - ((압축 후 문맥 토큰 + 압축 과정 LLM 토큰) / 압축 전 문맥 토큰)

    LLM을 사용하지 않는 압축기의 경우 압축 과정 LLM 토큰은 0이다.


3. 의미 유사도 (semantic_sim)

    압축 전 문맥과 압축 후 문맥을 임베딩한 뒤 코사인 유사도를 계산한다.

    원문과 압축본의 전체적인 의미가 얼마나 유지되었는지 확인하기 위한 지표다.
    --semantic 옵션을 사용한 경우에만 계산한다.

    임베딩 모델은 config의 embed_model 설정을 사용한다.


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

    문맥을 압축하면서 원문 문맥에서 얻을 수 있었던 답변 성능을
    얼마나 유지했는지 확인하기 위한 지표다.


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
import json
import math
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compressors import get_compressor
from config import CFG
from corpus import load_corpus
from grader import (
    contains_words,
    grade,
    grade_answer_accuracy,
    is_short,
    word_tokens,
)
from llm import LLM, count_tokens

ANSWER_MAX_TOKENS = 512

# 답변 프롬프트. 실험 내내 고정 (바꾸면 이전 결과와 비교할 수 없다)
ANSWER_SYSTEM = "You are an assistant that answers questions about FastAPI using the given documentation."
ANSWER_PROMPT = """Answer the question using only the documentation below. Be concise.

<documentation>
{context}
</documentation>

Question: {question}"""


# ---------------- 로그 형식 (팀 Spec 이 정해지면 여기만 고친다) ----------------

@dataclass
class TrialRecord:
    run_id: str
    qid: str
    split: str
    qtype: str
    compressor: str
    question: str
    answer: str
    evidence_pages: list[str]
    # 문맥
    ctx_tokens_raw: int             # 압축 전 문맥 토큰
    ctx_tokens: int                 # 압축 후 문맥 토큰
    reduction_pct: float            # 문맥 토큰 절감률 (%)
    compress_sec: float
    compress_llm_tokens: int        # 압축에 쓴 LLM 토큰 (입력+출력)
    entity_retention: float | None  # 핵심 엔티티 보존율 (엔티티 없으면 None)
    answer_in_context: bool | None  # 짧은 정답이 문맥에 남았는지 (긴 정답이면 None)
    semantic_sim: float | None      # 압축 전후 임베딩 코사인 유사도 (--semantic 일 때)
    semantic_chunks: int | None     # 임베딩 한도를 넘어 나눠 계산한 조각 수 (원문, 압축본 중 큰 쪽)
    # 답변
    response: str
    prompt_tokens: int              # 답변 LLM 입력 토큰 (서버 보고값)
    completion_tokens: int
    ttft_sec: float | None
    latency_sec: float
    ctx_overflow: bool              # 입력이 num_ctx 를 넘어 잘렸는지
    # 채점
    correct: bool                     # 기존 O/X 판정 - 기존 코드 호환용
    grade_method: str
    match: bool
    judge: bool | None
    judge_raw: str

    # key_facts 기반 답변 정확도
    answer_accuracy: float | None
    satisfied_facts: int | None
    total_facts: int | None
    fact_results: list[dict] = field(default_factory=list)

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
    fact_judge = (
        None
        if args.no_judge
        else LLM(
            model=CFG.judge_model,
            max_tokens=256,
        )
    )
    embedder = LLM() if args.semantic else None

    print(f"설정: {CFG.summary()}  judge={'off' if judge is None else CFG.judge_model}")
    print(f"문항 {len(items)}개 x 압축기 {names}  ->  {out_dir.relative_to(CFG.root).as_posix()}")
    print("모델 로딩 (첫 호출은 측정에서 제외)...", flush=True)
    llm.ask("Reply with OK.")

    records: list[TrialRecord] = []
    with open(out_dir / "trials.jsonl", "w", encoding="utf-8") as f:
        for i, item in enumerate(items, 1):
            raw = build_context(corpus, item)
            raw_tokens = count_tokens(raw)
            raw_emb, raw_chunks = embed_long(embedder, raw) if embedder else (None, None)
            ents = item.get("key_entities", [])
            print(f"[{i}/{len(items)}] {item['id']} {item['type']:<9} ctx {raw_tokens} tok", flush=True)

            for comp in compressors:
                t0 = time.perf_counter()
                cres = comp.compress(item["question"], raw)
                compress_sec = time.perf_counter() - t0
                ctx = cres.text
                ctx_tokens = count_tokens(ctx)
                ctx_words = word_tokens(ctx)
                (out_dir / "contexts" / f"{item['id']}.{comp.name}.md").write_text(ctx, encoding="utf-8")

                res = llm.chat([
                    {"role": "system", "content": ANSWER_SYSTEM},
                    {"role": "user", "content": ANSWER_PROMPT.format(context=ctx, question=item["question"])},
                ], stream_ttft=True)
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
                    )

                sim = chunks = None
                
                if embedder:
                    if ctx == raw:
                        sim, chunks = 1.0, raw_chunks
                    else:
                        emb, n = embed_long(embedder, ctx)
                        sim, chunks = round(cosine(raw_emb, emb), 4), max(raw_chunks, n)

                rec = TrialRecord(
                    run_id=run_id, qid=item["id"], split=item["split"], qtype=item["type"],
                    compressor=comp.name, question=item["question"], answer=item["answer"],
                    evidence_pages=item["evidence_pages"],
                    ctx_tokens_raw=raw_tokens, ctx_tokens=ctx_tokens,
                    reduction_pct=round(100 * (1 - ctx_tokens / raw_tokens), 2) if raw_tokens else 0.0,
                    compress_sec=round(compress_sec, 4),
                    compress_llm_tokens=cres.llm_prompt_tokens + cres.llm_completion_tokens,
                    entity_retention=entity_retention(ents, ctx_words),
                    answer_in_context=contains_words(ctx_words, item["answer"]) if is_short(item["answer"]) else None,
                    semantic_sim=sim, semantic_chunks=chunks,
                    response=res.text.strip(), prompt_tokens=res.prompt_tokens,
                    completion_tokens=res.completion_tokens,
                    ttft_sec=round(res.ttft, 3) if res.ttft is not None else None,
                    latency_sec=round(res.latency, 3), ctx_overflow=res.ctx_overflow,
                    correct=g.correct,
                    grade_method=g.method,
                    match=g.match,
                    judge=g.judge,
                    judge_raw=g.judge_raw,

                    answer_accuracy=(
                        fact_grade.answer_accuracy
                        if fact_grade is not None
                        else None
                    ),
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

                    info=cres.info,
                )
                records.append(rec)
                f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
                f.flush()
                print(f"    {comp.name:<6} {raw_tokens:>6} -> {ctx_tokens:<6} ({rec.reduction_pct:5.1f}%)  "
                      f"{'O' if g.correct else 'X'} [{g.method}]  ttft {rec.ttft_sec}s", flush=True)

    summary = {
        "run_id": run_id,
        "time": datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "config": {"llm": CFG.summary(), "judge_model": None if judge is None else CFG.judge_model,
                   "answer_max_tokens": ANSWER_MAX_TOKENS, "semantic": bool(embedder),
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
        # 1. 토큰 절감률 / 순 토큰 절감률
        # --------------------------------------------------
        raw = sum(r.ctx_tokens_raw for r in rs)
        comp = sum(r.ctx_tokens for r in rs)
        extra = sum(r.compress_llm_tokens for r in rs)

        reduction_pct = (
            round(100 * (1 - comp / raw), 2)
            if raw else None
        )

        net_reduction_pct = (
            round(100 * (1 - (comp + extra) / raw), 2)
            if raw else None
        )

        # --------------------------------------------------
        # 2. 답변 정확도
        # key_facts 충족 비율의 평균
        # --------------------------------------------------
        answer_accuracy = _mean(
            r.answer_accuracy for r in rs
        )

        s = {
            "n": len(rs),

            # 참고용 토큰 수
            "ctx_tokens_raw": raw,
            "ctx_tokens": comp,
            "compress_llm_tokens": extra,

            # ===== 최종 평가 지표 =====

            # 1. 토큰 절감률
            "reduction_pct": reduction_pct,

            # 2. 순 토큰 절감률
            "net_reduction_pct": net_reduction_pct,

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

            # ===== 보조 지표 =====
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

            "ttft_sec": _mean(r.ttft_sec for r in rs),
            "latency_sec": _mean(r.latency_sec for r in rs),
            "ctx_overflow": sum(r.ctx_overflow for r in rs),
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

        reduction = s.get("reduction_pct")
        net_reduction = s.get("net_reduction_pct")
        semantic = s.get("semantic_sim")
        entity = s.get("entity_retention")
        accuracy = s.get("answer_accuracy")
        retention = s.get("answer_accuracy_retention_pct")

        reduction_s = "-" if reduction is None else f"{reduction:.1f}%"
        net_s = "-" if net_reduction is None else f"{net_reduction:.1f}%"
        semantic_s = "-" if semantic is None else f"{semantic:.4f}"
        entity_s = "-" if entity is None else f"{entity * 100:.1f}%"
        accuracy_s = "-" if accuracy is None else f"{accuracy * 100:.1f}%"
        retention_s = "-" if retention is None else f"{retention:.1f}%"

        label = f"{n} (Baseline)" if n == "none" else n

        print(f"\n[{label}]")
        print(f"  토큰 절감률        : {reduction_s}")
        print(f"  순 토큰 절감률     : {net_s}")
        print(f"  의미 유사도        : {semantic_s}")
        print(f"  핵심 엔티티 보존율 : {entity_s}")
        print(f"  답변 정확도        : {accuracy_s}")
        print(f"  답변 정확도 유지율 : {retention_s}")

    print("\n" + "=" * 64)

def main():
    ap = argparse.ArgumentParser(description="압축 실험 실행 (A/B 비교)")
    ap.add_argument("--compressors", default="none,rule", help="쉼표로 구분 (none 이 기준선)")
    ap.add_argument("--split", default="dev", choices=("dev", "test", "all"),
                    help="dev 로 조정하고 test 는 최종 보고에만 사용")
    ap.add_argument("--limit", type=int, help="앞에서부터 N 문항만")
    ap.add_argument("--ids", nargs="*", help="특정 문항만 (예: q0001 q0003). --split 무시")
    ap.add_argument("--no-judge", action="store_true", help="LLM 채점 생략 (긴 정답도 단어 일치로 판정)")
    ap.add_argument("--semantic", action="store_true", help="압축 전후 임베딩 유사도 계산 (bge-m3 필요)")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
