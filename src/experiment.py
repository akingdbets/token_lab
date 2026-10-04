"""
압축 실험 실행기 (A/B 비교)

평가셋 문항마다 다음을 압축기별로 실행하고 결과를 한 줄씩 기록한다.

    질문 -> 근거 문서(평가셋 evidence_pages 의 원문) -> 압축 -> LLM 답변 -> 채점 -> 로그

RAG 검색 단계는 두지 않는다. 문맥은 문항의 정답 근거 페이지를 코퍼스에서 그대로 꺼낸다
(corpus.expanded_text: 원문 + 예제 코드 펼침). 압축기 "none" 이 기준선(Baseline)이다.
같은 문항을 압축기들에 연달아 돌리므로, 압축기 간 비교는 문항 단위로 짝지어진다.

사용법
    python src/experiment.py                                 # dev 문항, none,rule
    python src/experiment.py --split all --limit 5           # 연결 확인용
    python src/experiment.py --compressors none,rule --semantic   # 임베딩 유사도까지 (bge-m3 필요)
    python src/experiment.py --no-judge                      # LLM 채점 생략 (긴 정답도 단어 일치로)

저장 (results/runs/<run_id>/)
    trials.jsonl    문항 x 압축기마다 한 줄 (TrialRecord 필드)
    summary.json    압축기별 집계 + 실행 설정
    contexts/       압축 전후 문맥 (<문항>.<압축기>.md). 압축 결과를 눈으로 확인할 때

지표
    토큰 절감률      1 - 압축 후 문맥 토큰 합 / 원문 문맥 토큰 합 (Qwen 토크나이저)
    순 토큰 절감률    압축에 쓴 LLM 토큰까지 더해서 계산
    정확도 유지율    압축기 정답률 / none 정답률
    엔티티 보존율    문항 핵심 엔티티 중 압축 문맥에 남은 비율
    정답 보존        짧은 정답이 압축 문맥에 단어 그대로 남아 있는지
    의미 유사도      압축 전후 문맥 임베딩의 코사인 유사도 (--semantic)
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
from grader import contains_words, grade, is_short, word_tokens
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
    correct: bool
    grade_method: str               # match | judge
    match: bool
    judge: bool | None
    judge_raw: str
    info: dict = field(default_factory=dict)   # 압축기 부가 정보 (규칙별 적용 횟수 등)


# ---------------- 문맥 ----------------

def page_ref(doc_id: str) -> str:
    return doc_id.removeprefix("docs/en/docs/")


def build_context(corpus, item: dict) -> str:
    parts = []
    for doc_id in item["evidence_pages"]:
        parts.append(f"## Document: {page_ref(doc_id)}\n\n{corpus.expanded_text(doc_id).strip()}")
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
    judge = None if args.no_judge else LLM(model=CFG.judge_model, max_tokens=8)
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
                    correct=g.correct, grade_method=g.method, match=g.match, judge=g.judge,
                    judge_raw=g.judge_raw, info=cres.info,
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
        raw = sum(r.ctx_tokens_raw for r in rs)
        comp = sum(r.ctx_tokens for r in rs)
        extra = sum(r.compress_llm_tokens for r in rs)
        acc = sum(r.correct for r in rs) / len(rs)
        s = {
            "n": len(rs),
            "ctx_tokens_raw": raw,
            "ctx_tokens": comp,
            "reduction_pct": round(100 * (1 - comp / raw), 2) if raw else None,
            "net_reduction_pct": round(100 * (1 - (comp + extra) / raw), 2) if raw else None,
            "accuracy": round(acc, 4),
            "entity_retention": _mean(r.entity_retention for r in rs),
            "answer_in_context": _mean(None if r.answer_in_context is None else float(r.answer_in_context)
                                       for r in rs),
            "semantic_sim": _mean(r.semantic_sim for r in rs),
            "ttft_sec": _mean(r.ttft_sec for r in rs),
            "latency_sec": _mean(r.latency_sec for r in rs),
            "ctx_overflow": sum(r.ctx_overflow for r in rs),
        }
        if base and n != "none":
            paired = [(base[r.qid], r) for r in rs if r.qid in base]
            base_acc = sum(b.correct for b, _ in paired) / len(paired) if paired else 0
            s["accuracy_retention_pct"] = round(100 * acc / base_acc, 2) if base_acc else None
            s["lost"] = [r.qid for b, r in paired if b.correct and not r.correct]     # 기준선은 맞고 압축 후 틀림
            s["gained"] = [r.qid for b, r in paired if not b.correct and r.correct]
        out[n] = s
    return out


def print_summary(results: dict, names: list[str]):
    print("\n압축기   문항  문맥토큰(원문->압축)   절감률   정확도  유지율   엔티티보존  평균TTFT")
    for n in names:
        s = results.get(n)
        if not s:
            continue
        ret, ent = s.get("accuracy_retention_pct"), s["entity_retention"]
        ret_s = "-" if ret is None else f"{ret:.1f}%"
        ent_s = "-" if ent is None else f"{100 * ent:.1f}%"
        print(f"{n:<8} {s['n']:>4}  {s['ctx_tokens_raw']:>8} -> {s['ctx_tokens']:<8} "
              f"{s['reduction_pct']:>6.1f}%  {100 * s['accuracy']:>5.1f}%  "
              f"{ret_s:>6}   {ent_s:>8}   {s['ttft_sec']}s")
        if s.get("lost"):
            print(f"         기준선은 맞고 압축 후 틀린 문항: {', '.join(s['lost'])}")


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
