"""
멀티턴 replay 실행기

    python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 \
        --model gpt-6-luna --compressors "none,window(2),per_message(rule)" --samples 3 \
        --reasoning-effort server_default --max-completion-tokens 4096 \
        --reference-sample 0 --concurrency 5

    --reasoning-effort, --max-completion-tokens 는 필수 (config 기본값에 기대지 않는다).
    --estimate-only 는 API 를 부르지 않고 예상 비용만 출력한다 (multiturn/estimate.py).
    --resume <run_id> 는 끝난 (시나리오, 턴, 압축기, sample) 을 건너뛰고 이어서 돌린다.

절차
    1. 기준 궤적: 시나리오마다 none 으로 턴을 순서대로 실제 대화로 진행한다 (sample_idx = --reference-sample).
       results/multiturn/references/<설정 해시>/<scenario_id>.jsonl 에 저장하고, 설정이 같으면 재사용한다.
       기준 궤적의 각 턴도 채점해 둔다 (reference_grades). 빈 답변·finish_reason=length 는 경고하고 summary 에 남긴다.
    2. replay: 기준 궤적의 턴 k, 압축기, sample 마다
         history_before_turn(k) -> compress_history -> 턴 k 질문 답변 -> grader.grade_answer_accuracy
       none 도 sample 마다 다시 돌려 잡음 기준선을 만든다. none 의 reference sample 은 기준 궤적과 요청이 완전히 같아
       응답 캐시에 적중한다 (실험상 비용에만 들어가고 실제 지출은 0).

상태가 없는 압축기 (none, window, window_budget, query_select, per_message, on_arrival)
    on_arrival 은 현재 턴 문서도 압축한다 (문서가 온 턴에 압축, 이후 그 압축본 유지). 턴 k 의 기록은 기준 궤적 원문에서
    "모든 과거 문서가 도착 시 압축된 상태" 로 다시 만든다 (같은 문서·같은 질문이면 같은 결과를 재사용).
    (시나리오, 턴, 압축기, sample) 마다 독립으로 처리한다.
상태형 압축기 (rolling_summary, frozen_summary)
    (시나리오, 압축기, 예산, sample) 마다 체인 하나로 처리한다. 턴 0 부터 차례로 history_before_turn(k) (기준 궤적의 원문
    기록) 를 넣어 상태를 갱신하고, 턴 k 에는 "그 압축기로 실제 대화했을 때 턴 k 시점의 기록" 을 보낸다.
    기록 내용(과거 답변)은 기준 궤적의 것이다. 체인끼리는 병렬, 체인 안은 순서대로.
    이어 돌리기: 끝난 턴도 압축 단계는 다시 실행해 상태를 재구성한다 (요약 호출은 응답 캐시에 적중, sample_idx 포함 키).
    요약 실패(3번 시도 뒤에도 빈 요약·length): 그 체인을 그 턴부터 summary_failed 로 표시하고 남은 턴은 건너뛴다.
    실패한 응답은 캐시에 저장하지 않으므로, 이어 돌리면 summary_failed 체인은 다시 시도된다.

주 지표 (토큰 기준, 캐시가 없는 LLM 가정)
    입력 토큰 절감률 (input_reduction_pct), 총 토큰 절감률 (total_token_reduction_pct = 입력 + 출력(추론 포함) + 압축에 쓴
    LLM 토큰(요약·메모, 추론 포함)), 정확도 유지율 (retention_pct), 비열등 판정 (턴 단위 + 시나리오 군집).
    토큰 항목별 합은 tokens 에, 턴 유형별·recall 거리별 정확도는 accuracy_breakdown 에 있다.
    아래 캐시 관련 지표는 --cost-mode cache 일 때만 summary 에 나온다 (기본 none). trial 행에는 항상 계산해 저장한다.

비용 지표 (--cost-mode cache)
    replay 는 턴을 병렬·순서 무관하게 처리하므로 실험 중 서버가 보고한 cached_tokens 는 실제 대화의 프롬프트 캐시 동작이 아니다.
    그래서 비용 절감률 주 지표는 prefix_shared_tokens (같은 압축기로 실제 대화했을 때 직전 턴 요청과 겹치는 접두부) 로 계산한
    시뮬레이션 캐시 비용 (*_sim: 캐시 읽기 단가, *_sim_write: 미스 부분을 캐시 쓰기 단가로) 이다. 실측 cached_tokens 기반은 *_measured (참고).
    --sequential-chains 는 지정한 압축기 체인을 턴 순서대로, 동시 실행 없이, 응답 캐시를 끄고 실제 대화처럼 보내
    시뮬레이션 캐시 토큰과 실측 cached_tokens 를 턴별로 비교한다 (sequential_summary.json).

요약 추론 조건 (--summary-reasoning-effort server_default,none)
    요약형 압축기를 조건마다 펼쳐 이름에 [sre=<조건>] 을 붙인다 (예: rolling_summary(4000)[sre=none]).

예산 (--history-budget, 파일럿 기본 2000,4000,8000)
    예산 없이 쓴 예산형 이름(window_budget 등)을 예산마다 펼친다. 최근 --keep-recent 턴은 넘쳐도 남기고 overflow 로 표시.
    summary.json 의 budget_table 은 예산 × 압축기 비교표다 (none 대비, 실험상 비용 기준).

규칙
    - 대화 기록에는 최종 답변만 넣는다 (trajectory 규칙). 기준 궤적의 답변이 그대로 기록이 된다.
      그래서 턴 j 의 기준 답변이 틀리면 j 에 의존하는 턴은 압축과 무관하게 틀릴 수 있다 -> depends_on_reference_ok.
    - 현재 턴의 사용자 메시지(첨부 문서 포함)는 압축하지 않는다. 과거 기록만 압축한다.
    - 채점 프롬프트는 grader.py 그대로다. judge 호출도 응답 캐시에 넣는다 (sample_idx 0 고정: 같은 답변은 같은 채점).

결과 results/runs/mt_<run_id>/
    trajectory.jsonl     replay 호출 1번 = 1줄 (multiturn.trajectory 포맷)
    turn_trials.jsonl    턴 × 압축기 × sample 1줄
    reference_grades.json, errors.jsonl, summary.json
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import json
import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime

import requests

from config import CFG
from cost import compute_cost, cost_from_fields, find_price, load_pricing
from grader import contains_words, is_not_found_answer, word_tokens
from llm import count_message_tokens, count_tokens
from multiturn.fact_tags import setup_failed_fields, setup_indices, split_grade
from multiturn.history_compressors import (
    BUDGET_FAMILIES, budget_of, expand_budgets, expand_sets, expand_summary_efforts, family_of, get_history_compressor,
    is_stateful, label_of, parse_budget, parse_budget_list, split_compressor_list, summary_effort_of,
)
from multiturn.mt_stats import bootstrap_diff, non_inferiority, pair_rows
from multiturn.prompt import load_mt_prompt
from multiturn.scenario import scenario_hash, validate_scenario
from multiturn.trajectory import (
    REASONING_EFFORT_CHOICES, SERVER_DEFAULT, TrajectoryStep, append_step, history_before_turn, load_steps,
    reasoning_effort_for_llm, sampling_record, summarize_steps,
)

REFERENCE_ROOT = CFG.results_dir / "multiturn" / "references"
COST_MODES = ("none", "cache")
RETRY_STATUS = {429, 500, 502, 503, 504}
# 답변 모델 -> history_tokens_* / input_tokens_est 를 셀 토크나이저 (TOKENIZER). 정확히 일치하는 키, 없으면 가장 긴 접두사
EXPECTED_TOKENIZERS = {"gpt-6-luna": "tiktoken:o200k_base"}


class TokenizerMismatchError(RuntimeError):
    pass


def check_tokenizer(model: str, allow_approx: bool, tokenizer: str | None = None) -> dict:
    """TOKENIZER 가 답변 모델과 맞는지 확인한다. 다르거나 tiktoken 이 없으면 allow_approx 가 아닌 한 멈춘다.
    과금 토큰은 서버 usage 기준이라 영향이 없고, 압축 전후 기록 토큰·호출 전 입력 추정치의 단위가 달라진다."""
    tokenizer = tokenizer or CFG.tokenizer
    keys = [k for k in EXPECTED_TOKENIZERS if model == k or model.startswith(k)]
    expected = EXPECTED_TOKENIZERS[max(keys, key=len)] if keys else None
    problems = []
    if expected is None:
        problems.append(f"{model} 의 기대 토크나이저가 EXPECTED_TOKENIZERS 에 없습니다")
    elif tokenizer != expected:
        problems.append(f"TOKENIZER={tokenizer} 가 {model} 의 {expected} 와 다릅니다")
    if (expected or tokenizer).startswith("tiktoken:"):
        try:
            import tiktoken  # noqa: F401
        except ImportError:
            problems.append("tiktoken 이 설치돼 있지 않습니다 (pip install tiktoken)")
    ok = not problems
    if not ok and not allow_approx:
        raise TokenizerMismatchError("; ".join(problems) + ". .env 에 TOKENIZER=" + (expected or "<모델 토크나이저>")
                                     + " 를 넣거나, 근사로 돌리려면 --allow-approx-tokenizer 를 붙이세요.")
    return {"tokenizer": tokenizer, "expected": expected, "ok": ok, "approx": not ok, "problems": problems}


@dataclass
class ReplayConfig:
    model: str
    reasoning_effort: str               # REASONING_EFFORT_CHOICES (server_default 포함), 필수
    max_completion_tokens: int          # 필수
    compressors: list[str]
    samples: int = 3
    reference_sample: int = 0
    temperature: str = SERVER_DEFAULT   # server_default 또는 숫자 문자열
    prompt_version: str = "v2"          # src/prompts/mt_answer_v2.md (요약·발췌 블록도 제공 정보로 봄)
    history_budgets: list = field(default_factory=list)   # 예산형 압축기 기록 예산: 토큰(int) 또는 비율("r=0.5")
    keep_recent: int = 1                # 예산형 압축기가 항상 원문으로 남기는 최근 턴 수
    summary_model: str | None = None            # 요약형 압축기가 있으면 필수
    summary_reasoning_effort: str | list | None = None  # 요약형 압축기가 있으면 필수. 쉼표로 여러 조건 (server_default,none)
    summary_max_tokens: int | None = None        # 요약형 압축기가 있으면 필수
    presummary_model: str | None = None          # presummary 가 있으면 필수 (data/presummaries/<모델>/)
    notes_model: str | None = None               # fact_notes 가 있으면 필수
    notes_reasoning_effort: str | None = None    # fact_notes 가 있으면 필수
    notes_max_tokens: int | None = None          # fact_notes 가 있으면 필수
    notes_target_ratio: float = 0.25             # 메모 목표 길이 = 그 턴 문서 토큰 × 비율
    cost_mode: str = "none"                      # none: 토큰 지표만. cache: 캐시 관련 비용 지표(sim, nocache, 접두부 공유율, 실측)도 summary 에
    judge_mode: str = CFG.judge_mode
    concurrency: int = 5
    margin: float = 0.10
    boot: int = 10000
    seed: int = 42
    max_attempts: int = 6               # 429·5xx 재시도 (첫 호출 포함)
    backoff_base: float = 2.0

    def __post_init__(self):
        reasoning_effort_for_llm(self.reasoning_effort)      # 잘못된 값이면 ValueError
        if not isinstance(self.max_completion_tokens, int) or self.max_completion_tokens <= 0:
            raise ValueError("max_completion_tokens 는 양의 정수로 명시해야 합니다")
        self.compressors = expand_sets(list(self.compressors))       # "v2" -> 정한 압축기 목록
        if "none" not in self.compressors:
            raise ValueError("compressors 에 none(기준선)이 있어야 합니다")
        if not 0 <= self.reference_sample < self.samples:
            raise ValueError("reference_sample 은 0 이상 samples 미만")
        for b in self.history_budgets:
            v = parse_budget(str(b))
            if (isinstance(v, int) and v <= 0) or (isinstance(v, float) and not 0 < v <= 1):
                raise ValueError("history_budgets 는 양의 정수 또는 r=<0 초과 1 이하>")
        if self.cost_mode not in COST_MODES:
            raise ValueError(f"cost_mode 는 {COST_MODES} 중 하나")
        if isinstance(self.summary_reasoning_effort, str):
            self.summary_reasoning_effort = [e.strip() for e in self.summary_reasoning_effort.split(",") if e.strip()]
        self.compressors = expand_budgets(list(self.compressors), list(self.history_budgets))
        self.compressors = expand_summary_efforts(self.compressors, list(self.summary_efforts))
        if self.has_summary:
            missing = [k for k in ("summary_model", "summary_reasoning_effort", "summary_max_tokens")
                       if getattr(self, k) in (None, "")]
            if missing:
                raise ValueError(f"요약형 압축기에는 {missing} 가 필요합니다 (--summary-model, "
                                 "--summary-reasoning-effort, --summary-max-tokens). config 기본값을 쓰지 않습니다")
            for e in self.summary_efforts:
                reasoning_effort_for_llm(e)
            for c in self.compressors:
                if is_stateful(c) and summary_effort_of(c) not in self.summary_efforts:
                    raise ValueError(f"{c} 의 요약 조건이 --summary-reasoning-effort 에 없습니다")
            if not isinstance(self.summary_max_tokens, int) or self.summary_max_tokens <= 0:
                raise ValueError("summary_max_tokens 는 양의 정수")
        if self.has_presummary and not self.presummary_model:
            raise ValueError("presummary 에는 presummary_model 이 필요합니다 (--presummary-model)")
        if self.has_notes:
            missing = [k for k in ("notes_model", "notes_reasoning_effort", "notes_max_tokens")
                       if getattr(self, k) in (None, "")]
            if missing:
                raise ValueError(f"fact_notes 에는 {missing} 가 필요합니다 (--notes-model, --notes-reasoning-effort, "
                                 "--notes-max-tokens). config 기본값을 쓰지 않습니다")
            reasoning_effort_for_llm(self.notes_reasoning_effort)
            if not isinstance(self.notes_max_tokens, int) or self.notes_max_tokens <= 0:
                raise ValueError("notes_max_tokens 는 양의 정수")
            if not 0 < self.notes_target_ratio <= 1:
                raise ValueError("notes_target_ratio 는 0 초과 1 이하")

    @property
    def summary_efforts(self) -> list[str]:
        return list(self.summary_reasoning_effort or [])

    @property
    def has_summary(self) -> bool:
        return any(is_stateful(c) for c in self.compressors)

    @property
    def has_presummary(self) -> bool:
        return any("presummary" in c for c in self.compressors)

    @property
    def has_notes(self) -> bool:
        return "fact_notes" in self.compressors


def configure_llm(llm, model: str, reasoning_effort: str, max_tokens: int, temperature: str):
    """LLM 객체에 실험 설정을 명시적으로 넣는다 (llm.py 는 고치지 않음).
    temperature=server_default 면 처음부터 보내지 않는다 (0 을 보냈는데 서버가 받으면 서버 기본값 조건이 깨진다)."""
    llm.model = model
    llm.max_tokens = max_tokens
    llm.reasoning_effort = reasoning_effort_for_llm(reasoning_effort)
    if temperature == SERVER_DEFAULT:
        llm.temperature = None
        llm.unsupported.add("temperature")
    else:
        llm.temperature = float(temperature)
    return llm


def configure_answer_llm(llm, cfg: ReplayConfig):
    return configure_llm(llm, cfg.model, cfg.reasoning_effort, cfg.max_completion_tokens, cfg.temperature)


def configure_notes_llm(llm, cfg: ReplayConfig):
    return configure_llm(llm, cfg.notes_model, cfg.notes_reasoning_effort, cfg.notes_max_tokens, cfg.temperature)


def configure_summary_llm(llm, cfg: ReplayConfig, effort: str | None = None):
    effort = effort or cfg.summary_efforts[0]
    return configure_llm(llm, cfg.summary_model, effort, cfg.summary_max_tokens, cfg.temperature)


def with_backoff(fn, cfg: ReplayConfig, sleep=time.sleep):
    """429·5xx 와 연결 오류는 지수 백오프(+지터)로 다시 부른다."""
    for attempt in range(cfg.max_attempts):
        try:
            return fn()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            retryable = status in RETRY_STATUS or isinstance(e, (requests.ConnectionError, requests.Timeout))
            if not retryable or attempt == cfg.max_attempts - 1:
                raise
            wait = cfg.backoff_base * (2 ** attempt) * (1 + random.random() * 0.25)
            print(f"  [백오프 {attempt + 1}/{cfg.max_attempts}] {status or type(e).__name__} -> {wait:.1f}초", flush=True)
            sleep(wait)


def depends_closure(scenario: dict, k: int) -> list[int]:
    """턴 k 가 (거슬러 올라가며) 의존하는 이전 턴들."""
    seen, stack = set(), list(scenario["turns"][k]["depends_on"])
    while stack:
        d = stack.pop()
        if d not in seen:
            seen.add(d)
            stack.extend(scenario["turns"][d]["depends_on"])
    return sorted(seen)


def _same_current_turn(comp, sent: str, current_user: str) -> bool:
    """현재 턴 메시지는 그대로여야 한다. on_arrival 처럼 현재 턴 문서를 압축하는 압축기는 문서 블록 밖(질문·형식 줄)만 같으면 된다."""
    if sent == current_user:
        return True
    if not getattr(comp, "compresses_current_docs", False):
        return False
    from multiturn.prompt import DOC_BLOCK_RE
    strip = lambda t: DOC_BLOCK_RE.sub(r"\1\3", t)   # noqa: E731
    return strip(sent) == strip(current_user)


def reference_key(cfg: ReplayConfig, answer_llm, prompt, scenario: dict) -> str:
    payload = {"backend": answer_llm.backend, "base_url": answer_llm.base_url, "model": cfg.model,
               "reasoning_effort": cfg.reasoning_effort, "temperature": cfg.temperature,
               "max_completion_tokens": cfg.max_completion_tokens, "prompt": [prompt.version, prompt.sha256],
               "scenario": scenario_hash(scenario), "reference_sample": cfg.reference_sample, "seed": CFG.seed}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _history_tokens(messages: list[dict]) -> int:
    """system·현재 턴을 뺀 과거 기록 글자의 토큰 수 (템플릿 오버헤드 제외)."""
    return sum(count_tokens(m["content"]) for m in messages if m["role"] != "system")


def entity_retention_in_history(entities: list[str], raw_past: list[dict], comp_past: list[dict]) -> float | None:
    """이 턴 key_entities 중 압축 전 기록에 있던 것 가운데 압축된 기록에도 남은 비율. 원래 기록에 없으면 None."""
    raw_words = word_tokens("\n".join(m["content"] for m in raw_past))
    comp_words = word_tokens("\n".join(m["content"] for m in comp_past))
    present = [e for e in entities if word_tokens(e) and contains_words(raw_words, e)]
    if not present:
        return None
    return round(sum(contains_words(comp_words, e) for e in present) / len(present), 4)


class Replay:
    def __init__(self, cfg: ReplayConfig, scenarios: list[dict], corpus, answer_cached, judge_cached,
                 out_dir: Path, reference_root: Path = REFERENCE_ROOT, grade_fn=None, sleep=time.sleep,
                 tokenizer_check: dict | None = None, summarizer=None, presummary_store=None, notes_extractor=None):
        self.cfg, self.scenarios, self.corpus = cfg, scenarios, corpus
        self.summarizer = summarizer
        self.presummary_store = presummary_store
        self.notes_extractor = notes_extractor
        self.answer = answer_cached                    # multiturn.response_cache.CachedLLM (answer LLM 감쌈)
        self.judge = judge_cached.bind(0)              # 같은 답변은 같은 채점 (sample_idx 0 고정)
        self.out_dir = Path(out_dir)
        self.reference_root = Path(reference_root)
        self.prompt = load_mt_prompt(cfg.prompt_version)
        if grade_fn is None:
            from grader import grade_answer_accuracy
            grade_fn = grade_answer_accuracy
        self.grade_fn = grade_fn
        self.sleep = sleep
        self.tokenizer_check = tokenizer_check or {"tokenizer": CFG.tokenizer, "ok": None, "approx": None,
                                                   "note": "확인하지 않음 (Replay 를 직접 만든 경우)"}
        # 압축기를 여기서 만든다: llmlingua 가 필요한데 없으면 시작 시점에 MissingDependencyError 로 멈춘다
        self.compressors = {name: get_history_compressor(name, token_counter=lambda t: count_tokens(t),
                                                         summarizer=summarizer, keep_recent=cfg.keep_recent,
                                                         presummary_store=presummary_store,
                                                         notes_extractor=notes_extractor)
                            for name in cfg.compressors}
        self._lock = threading.Lock()
        self._memo: dict = {}
        self.run_id = self.out_dir.name.removeprefix("mt_")
        for s in scenarios:
            errs = validate_scenario(s)
            if errs:
                raise ValueError(f"시나리오 검증 실패: {errs[:5]}")

    # ---------------- 기록 ----------------

    def _append(self, name: str, row: dict):
        with self._lock:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            with open(self.out_dir / name, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _read(self, name: str) -> list[dict]:
        p = self.out_dir / name
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _trials(self) -> list[dict]:
        """turn_trials.jsonl. 같은 키가 여러 번 있으면 마지막 줄 (summary_failed 체인을 다시 돌린 경우)."""
        last = {}
        for r in self._read("turn_trials.jsonl"):
            last[self.trial_key(r)] = r
        return list(last.values())

    # ---------------- 1단계: 기준 궤적 ----------------

    def reference(self, scenario: dict) -> list[TrajectoryStep]:
        key = reference_key(self.cfg, self.answer.llm, self.prompt, scenario)
        path = self.reference_root / key / f"{scenario['scenario_id']}.jsonl"
        if path.exists():
            steps = load_steps(path)
            if len(steps) == len(scenario["turns"]):
                return steps
            path.unlink()                                  # 끊긴 기준 궤적은 처음부터 (응답 캐시로 다시 받는다)
        history = [{"role": "system", "content": self.prompt.system}]
        steps = []
        for t in scenario["turns"]:
            user = self.prompt.user_message(t, self.corpus)
            messages = history + [{"role": "user", "content": user}]
            res, hit = with_backoff(lambda: self.answer.chat(messages, sample_idx=self.cfg.reference_sample),
                                    self.cfg, self.sleep)
            step = TrajectoryStep.from_result(
                res, cache_hit=hit, cost=compute_cost(res).to_dict(), run_id=f"reference:{key}",
                scenario_id=scenario["scenario_id"], sample_idx=self.cfg.reference_sample, mode="free_run",
                compressor="none", turn=t["turn"], user_input=user, messages_sent=messages,
                response_content=res.text.strip(),
                sampling=sampling_record(self.answer.llm, res, self.cfg.reasoning_effort),
                history_tokens_raw=_history_tokens(history), history_tokens_compressed=_history_tokens(history))
            steps.append(step)
            history = messages + [{"role": "assistant", "content": step.response_content}]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.unlink(missing_ok=True)
        for s in steps:
            append_step(tmp, s)
        tmp.replace(path)
        return steps

    def grade(self, turn: dict, response: str):
        return with_backoff(lambda: self.grade_fn(turn["question"], turn["answer"], turn["key_facts"], response,
                                                  self.judge, mode=self.cfg.judge_mode), self.cfg, self.sleep)

    def build_references(self) -> tuple[dict, dict, list[str]]:
        refs, grades, warnings = {}, {}, []
        saved = {}
        p = self.out_dir / "reference_grades.json"
        if p.exists():
            saved = json.loads(p.read_text(encoding="utf-8"))
        for s in self.scenarios:
            sid = s["scenario_id"]
            refs[sid] = self.reference(s)
            grades[sid] = {}
            for step in refs[sid]:
                t = s["turns"][step.turn]
                if not step.response_content:
                    warnings.append(f"{sid} 턴 {step.turn}: 기준 궤적 답변이 비었습니다")
                if step.finish_reason == "length":
                    warnings.append(f"{sid} 턴 {step.turn}: 기준 궤적 답변이 출력 한도에 걸렸습니다 (finish_reason=length)")
                prev = saved.get(sid, {}).get(str(step.turn))
                if (prev is not None and prev.get("response") == step.response_content
                        and (not setup_indices(t) or "answer_accuracy_all" in prev)):
                    grades[sid][str(step.turn)] = prev
                    continue
                g = self.grade(t, step.response_content)
                sg = split_grade(t, g)       # answer_accuracy 는 setup 항목을 뺀 주 정확도 (depends_on_reference_ok 에 쓴다)
                grades[sid][str(step.turn)] = {"answer_accuracy": sg["answer_accuracy"], "response": step.response_content,
                                               **({"answer_accuracy_all": sg["answer_accuracy_all"],
                                                   "setup_accuracy": sg["setup_accuracy"]} if setup_indices(t) else {})}
        for w in warnings:
            print(f"  [경고] {w}", flush=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(grades, ensure_ascii=False, indent=1), encoding="utf-8")
        return refs, grades, warnings

    # ---------------- 2단계: replay ----------------

    @staticmethod
    def trial_key(row: dict) -> tuple:
        return (row["scenario_id"], row["turn"], row["compressor"], row["sample_idx"])

    def _row_base(self, scenario: dict, ref_grades: dict, k: int, comp_name: str, sample_idx: int) -> dict:
        t = scenario["turns"][k]
        deps = depends_closure(scenario, k)
        return {
            "run_id": self.run_id, "scenario_id": scenario["scenario_id"], "turn": k, "compressor": comp_name,
            "compressor_family": family_of(comp_name), "history_budget": budget_of(comp_name),
            "keep_recent": self.cfg.keep_recent if budget_of(comp_name) else None,
            "sample_idx": sample_idx, "turn_type": t["turn_type"], "type": t["type"],
            "depends_on": t["depends_on"], "depends_on_all": deps,
            "depends_distance_min": min((k - d for d in t["depends_on"]), default=None),
            "depends_distance_max": max((k - d for d in t["depends_on"]), default=None),
            "depends_on_reference_ok": all((ref_grades.get(str(d)) or {}).get("answer_accuracy") == 1.0 for d in deps),
            "summary_failed": False,
        }

    def _prefix(self, prev: list[dict] | None, messages: list[dict]) -> tuple[int, int]:
        from multiturn.estimate import CACHE_MIN_TOKENS, common_prefix_tokens
        raw = common_prefix_tokens(prev, messages, count_message_tokens) if prev else 0
        return (raw if raw >= CACHE_MIN_TOKENS else 0), raw

    def _inputs(self, scenario: dict, ref_steps: list[TrajectoryStep], k: int):
        t = scenario["turns"][k]
        return history_before_turn(ref_steps, k, system=self.prompt.system), self.prompt.user_message(t, self.corpus)

    def _stateless(self, scenario, ref_steps, k, comp_name, sample_idx: int = 0):
        """상태 없는 압축기의 턴 k 결과 (sample 과 무관해 메모해 둔다. 직전 턴 접두부 비교에도 쓴다).
        fact_notes 처럼 기록이 sample 마다 다른 압축기(per_sample)는 sample 별로 메모하고 state={"sample_idx": i} 를 넘긴다."""
        comp = self.compressors[comp_name]
        per_sample = getattr(comp, "per_sample", False)
        key = (scenario["scenario_id"], k, comp_name, sample_idx if per_sample else None)
        with self._lock:
            if key in self._memo:
                return self._memo[key]
        history, current_user = self._inputs(scenario, ref_steps, k)
        t0 = time.perf_counter()
        hres = with_backoff(lambda: comp.compress_history(history, current_user, None,
                                                          {"sample_idx": sample_idx} if per_sample else None),
                            self.cfg, self.sleep)
        out = (history, current_user, hres, time.perf_counter() - t0)
        with self._lock:
            self._memo[key] = out
        return out

    def run_trial(self, scenario: dict, ref_steps: list[TrajectoryStep], ref_grades: dict, k: int,
                  comp_name: str, sample_idx: int, pre=None, prev_messages=None) -> dict:
        t = scenario["turns"][k]
        if pre is None:
            pre = self._stateless(scenario, ref_steps, k, comp_name, sample_idx)
            if k > 0 and prev_messages is None:
                prev_messages = self._stateless(scenario, ref_steps, k - 1, comp_name, sample_idx)[2].messages
        history, current_user, hres, compress_sec = pre
        comp = self.compressors[comp_name]
        messages = hres.messages
        if messages[0] != history[0] or not _same_current_turn(comp, messages[-1]["content"], current_user):
            raise AssertionError("압축기가 system 또는 현재 턴 메시지를 바꿨습니다")
        info = dict(hres.info)
        results = list(info.pop("_llm_results", []) or [])
        llm_pt, llm_ct = hres.llm_prompt_tokens, hres.llm_completion_tokens
        notes = None
        if hasattr(comp, "turn_end"):
            # 턴 k 가 끝날 때 만드는 메모 (기준 궤적의 턴 k 문서·질문·답변). 토큰은 이 trial 에 귀속한다.
            # 이후 턴에서 다시 쓰는 것은 0 토큰 (같은 메모 재사용). 응답 캐시 적중이어도 원래 호출의 usage 로 센다 (실험상 비용)
            notes = with_backoff(lambda: comp.turn_end(k, current_user, ref_steps[k].response_content, sample_idx),
                                 self.cfg, self.sleep)
            if notes is not None:
                results += notes.results
                llm_pt += notes.prompt_tokens
                llm_ct += notes.completion_tokens
        compress_cost = compress_cost_of(results)
        res, hit = with_backoff(lambda: self.answer.chat(messages, sample_idx=sample_idx), self.cfg, self.sleep)
        response = res.text.strip()
        g = self.grade(t, response)
        cost = compute_cost(res).to_dict()
        judge_cost = None
        if g.judge_prompt_tokens or g.judge_completion_tokens:
            from cost import cost_from_fields
            judge_cost = cost_from_fields(self.judge.model, g.judge_prompt_tokens, g.judge_completion_tokens,
                                          cached_tokens=getattr(g, "judge_cached_tokens", None),
                                          cache_write_tokens=getattr(g, "judge_cache_write_tokens", None),
                                          usage_source=g.judge_usage_source or "api").to_dict()
        raw_past, comp_past = history[1:], messages[1:-1]
        shared, shared_raw = self._prefix(prev_messages, messages)
        step = TrajectoryStep.from_result(
            res, cache_hit=hit, cost=cost, run_id=self.run_id, scenario_id=scenario["scenario_id"],
            sample_idx=sample_idx, mode="replay", compressor=comp_name, turn=k, user_input=current_user,
            messages_sent=messages, response_content=response,
            sampling=sampling_record(self.answer.llm, res, self.cfg.reasoning_effort),
            history_tokens_raw=_history_tokens(raw_past), history_tokens_compressed=_history_tokens(comp_past),
            compression_info={"config": comp.config(), "llm_prompt_tokens": llm_pt,
                              "llm_completion_tokens": llm_ct, "info": info,
                              "notes_made": notes.record(comp.extractor.target_ratio) if notes is not None else None,
                              "compress_cost": compress_cost, "compress_sec": round(compress_sec, 3)})
        row = {
            **self._row_base(scenario, ref_grades, k, comp_name, sample_idx),
            "history_tokens_raw": step.history_tokens_raw, "history_tokens_compressed": step.history_tokens_compressed,
            "overflow": info.get("overflow"), "input_tokens_est": count_message_tokens(messages),
            "prefix_shared_tokens": shared, "prefix_shared_tokens_raw": shared_raw,
            "prompt_tokens": res.prompt_tokens, "cached_tokens": res.cached_tokens,
            "cache_write_tokens": res.cache_write_tokens, "reasoning_tokens": res.reasoning_tokens,
            "completion_tokens": res.completion_tokens, "usage_source": res.usage_source,
            "compress_llm_prompt_tokens": llm_pt, "compress_llm_completion_tokens": llm_ct,
            "compress_llm_reasoning_tokens": sum(r.reasoning_tokens or 0 for r in results),
            "compress_cost": compress_cost, "history_budget_effective": info.get("history_budget"),
            "notes_made": notes.record(comp.extractor.target_ratio) if notes is not None else None,
            "presummary_pages": info.get("pages_replaced"),
            "summary_calls": info.get("summary_calls"), "summary_cache_hits": info.get("summary_cache_hits"),
            "recompressed": info.get("recompressed"), "recompress_turns": info.get("recompress_turns"),
            "cost": cost, "judge_cost": judge_cost, "cache_hit": hit, "finish_reason": res.finish_reason,
            "summary_effort": summary_effort_of(comp_name),
            "response": response, "empty_response": not response, "not_found": is_not_found_answer(response),
            **split_grade(t, g),      # answer_accuracy 등은 setup 항목을 뺀 주 정확도, setup_accuracy 는 따로
            "judge_mode": g.judge_mode, "judge_skipped": g.judge_skipped, "judge_failed": list(g.judge_failed),
            "judge_prompt_tokens": g.judge_prompt_tokens, "judge_completion_tokens": g.judge_completion_tokens,
            "entity_retention": entity_retention_in_history(t["key_entities"], raw_past, comp_past),
            "prompt_hash": step.prompt_hash, "model": res.model,
        }
        row["cost_sim"] = sim_cost(row)
        self._append("trajectory.jsonl", step.to_dict())
        self._append("turn_trials.jsonl", row)
        return row

    def _failed_rows(self, scenario, ref_grades, k_fail, comp_name, sample_idx, hres, done: set):
        """요약 실패: 실패 턴과 남은 턴을 summary_failed 로 기록 (주 기준 정확도 0점, 답변 호출 없음)."""
        info = dict(hres.info)
        results = info.pop("_llm_results", []) or []
        cost = compress_cost_of(results)
        for k in range(k_fail, len(scenario["turns"])):
            if (scenario["scenario_id"], k, comp_name, sample_idx) in done:
                continue
            first = k == k_fail
            self._append("turn_trials.jsonl", {
                **self._row_base(scenario, ref_grades, k, comp_name, sample_idx),
                "summary_failed": True, "summary_failed_turn": k_fail, "skipped_after_summary_failure": not first,
                "summary_fail_reason": info.get("summary_fail_reason"),
                "summary_attempts": info.get("summary_attempts") if first else 0,
                "compress_llm_prompt_tokens": hres.llm_prompt_tokens if first else 0,
                "compress_llm_completion_tokens": hres.llm_completion_tokens if first else 0,
                "compress_cost": cost if first else {"usd": 0.0, "usd_nocache": 0.0, "calls": 0},
                "summary_effort": summary_effort_of(comp_name),
                "answer_accuracy": 0.0, **setup_failed_fields(scenario["turns"][k]),
                "response": None, "not_found": False, "empty_response": False,
                "cost": None, "cache_hit": False,
            })

    def run_chain(self, scenario: dict, ref_steps, ref_grades, comp_name: str, sample_idx: int, done: set) -> int:
        """상태형 압축기 체인. 끝난 턴도 압축은 다시 해서 상태를 재구성한다 (요약은 응답 캐시 적중)."""
        comp = self.compressors[comp_name]
        state = comp.initial_state(sample_idx)
        prev = None
        n = 0
        for k in range(len(scenario["turns"])):
            history, current_user = self._inputs(scenario, ref_steps, k)
            t0 = time.perf_counter()
            hres = with_backoff(lambda: comp.compress_history(history, current_user, None, state), self.cfg, self.sleep)
            sec = time.perf_counter() - t0
            if hres.info.get("summary_failed"):
                self._failed_rows(scenario, ref_grades, k, comp_name, sample_idx, hres, done)
                return n
            state = hres.state
            if (scenario["scenario_id"], k, comp_name, sample_idx) in done:
                prev = hres.messages
                continue
            self.run_trial(scenario, ref_steps, ref_grades, k, comp_name, sample_idx,
                           pre=(history, current_user, hres, sec), prev_messages=prev)
            prev = hres.messages
            n += 1
        return n

    def run(self) -> dict:
        refs, ref_grades, ref_warnings = self.build_references()
        done = {self.trial_key(r) for r in self._trials() if not r.get("summary_failed")}
        stateless = [c for c in self.cfg.compressors if not is_stateful(c)]
        stateful = [c for c in self.cfg.compressors if is_stateful(c)]
        tasks = [(s, k, c, i) for s in self.scenarios for k in range(len(s["turns"]))
                 for c in stateless for i in range(self.cfg.samples)
                 if (s["scenario_id"], k, c, i) not in done]
        chains = [(s, c, i) for s in self.scenarios for c in stateful for i in range(self.cfg.samples)
                  if any((s["scenario_id"], k, c, i) not in done for k in range(len(s["turns"])))]
        print(f"replay: trial {len(tasks)} + 상태형 체인 {len(chains)} (이미 끝남 {len(done)})", flush=True)
        failed = 0
        seg_start = datetime.now().isoformat(timespec="seconds")
        with ThreadPoolExecutor(max_workers=self.cfg.concurrency) as pool:
            futs = {}
            for s, k, c, i in tasks:
                futs[pool.submit(self.run_trial, s, refs[s["scenario_id"]], ref_grades[s["scenario_id"]], k, c, i)] = \
                    (s["scenario_id"], k, c, i)
            for s, c, i in chains:
                futs[pool.submit(self.run_chain, s, refs[s["scenario_id"]], ref_grades[s["scenario_id"]], c, i, done)] = \
                    (s["scenario_id"], "chain", c, i)
            for f in as_completed(futs):
                try:
                    f.result()
                except Exception as e:      # 한 trial·체인이 실패해도 나머지는 돈다. 이어 돌리기로 다시 시도된다
                    failed += 1
                    self._append("errors.jsonl", {"key": list(futs[f]), "error": f"{type(e).__name__}: {e}"[:500],
                                                  "time": datetime.now().isoformat(timespec="seconds")})
        # 실행 구간 기록: --resume 으로 이어 돌리면 구간이 하나씩 늘어난다 (concurrency 등을 덮어쓰지 않는다)
        self._append("run_segments.jsonl", {
            "started_at": seg_start, "finished_at": datetime.now().isoformat(timespec="seconds"),
            "concurrency": self.cfg.concurrency, "trials_submitted": len(tasks), "chains_submitted": len(chains),
            "already_done": len(done), "failed": failed})
        rows = self._trials()
        build = (presummary_build_block(self.presummary_store, self.scenarios)
                 if self.presummary_store is not None else None)
        summary = summarize_replay(rows, self.cfg, ref_warnings=ref_warnings, n_scenarios=len(self.scenarios),
                                   presummary_build=build)
        summary["failed_trials_this_run"] = failed
        summary["tokenizer_check"] = self.tokenizer_check
        if self.tokenizer_check.get("approx"):
            summary["notes"].append(f"토크나이저 근사: {self.tokenizer_check.get('problems')}. "
                                    "history_tokens_* 와 input_tokens_est 는 답변 모델 단위가 아니다 (과금 토큰은 서버 usage).")
        summary["config"] = self.config_record()
        steps = [TrajectoryStep.from_dict(d) for d in self._read("trajectory.jsonl")]
        summary["trajectory"] = summarize_steps(steps)
        summary["budget"] = budget_block(steps, [st for v in refs.values() for st in v], rows)
        if build is not None:
            summary["presummary_build"] = build
        (self.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        return summary

    def run_sequential(self, comp_names: list[str], scenario_ids: list[str] | None = None,
                       samples: list[int] | None = None) -> dict:
        """캐시 검증: 지정 압축기의 (시나리오, sample) 체인을 턴 순서대로, 동시 실행 없이, 응답 캐시를 끄고 보낸다.
        답변은 채점하지 않는다 (프롬프트 캐시 동작만 본다). 결과: sequential_chains.jsonl, sequential_summary.json."""
        from multiturn.history_compressors import Summarizer
        from multiturn.response_cache import CachedLLM

        refs, _, ref_warnings = self.build_references()
        answer = CachedLLM(self.answer.llm, enabled=False)
        summ = self.summarizer
        if isinstance(summ, dict):
            summ = {k: Summarizer(CachedLLM(v.cached.llm, enabled=False), v.prompt, v.max_attempts) for k, v in summ.items()}
        elif summ is not None:
            summ = Summarizer(CachedLLM(summ.cached.llm, enabled=False), summ.prompt, summ.max_attempts)
        scen = [s for s in self.scenarios if not scenario_ids or s["scenario_id"] in scenario_ids]
        rows = []
        for name in comp_names:
            comp = get_history_compressor(name, token_counter=lambda t: count_tokens(t), summarizer=summ,
                                          keep_recent=self.cfg.keep_recent, presummary_store=self.presummary_store,
                                          notes_extractor=self.notes_extractor)
            for s in scen:
                for i in (samples or [0]):
                    state = comp.initial_state(i) if hasattr(comp, "initial_state") else None
                    prev = None
                    for k in range(len(s["turns"])):
                        history, user = self._inputs(s, refs[s["scenario_id"]], k)
                        hres = comp.compress_history(history, user, None, state)
                        if hres.info.get("summary_failed"):
                            rows.append({"scenario_id": s["scenario_id"], "compressor": name, "sample_idx": i, "turn": k,
                                         "summary_failed": True})
                            break
                        state = hres.state
                        info = dict(hres.info)
                        sres = info.pop("_llm_results", []) or []
                        res = with_backoff(lambda: answer.chat(hres.messages, sample_idx=i)[0], self.cfg, self.sleep)
                        shared, shared_raw = self._prefix(prev, hres.messages)
                        row = {"scenario_id": s["scenario_id"], "compressor": name, "sample_idx": i, "turn": k,
                               "input_tokens_est": count_message_tokens(hres.messages),
                               "prefix_shared_tokens": shared, "prefix_shared_tokens_raw": shared_raw,
                               "prompt_tokens": res.prompt_tokens, "cached_tokens": res.cached_tokens,
                               "cache_write_tokens": res.cache_write_tokens, "completion_tokens": res.completion_tokens,
                               "reasoning_tokens": res.reasoning_tokens, "finish_reason": res.finish_reason,
                               "model": res.model, "created_at": res.created_at, "summary_calls": len(sres),
                               "summary_cached_tokens": [r.cached_tokens for r in sres],
                               "cost_measured": compute_cost(res).to_dict()}
                        row["cost_sim"] = sim_cost(row)
                        row["sim_cached_tokens"] = row["cost_sim"]["sim_cached_tokens"]
                        rows.append(row)
                        self._append("sequential_chains.jsonl", row)
                        prev = hres.messages
        out = sequential_summary(rows)
        out["notes"] = [
            "응답 캐시를 끄고 턴 순서대로 한 번에 하나씩 보낸 결과다. sim_cached_tokens 는 prefix_shared_tokens 를 API 토큰 단위로 맞춘 값 "
            "(prompt_tokens × prefix_shared_tokens / input_tokens_est), cached_tokens 는 서버 보고값이다.",
            "서버 캐시는 보존 시간·라우팅·다른 요청의 영향을 받으므로 한 체인의 결과로 일반화하지 않는다.",
            "답변은 채점하지 않았다 (캐시 동작 검증용).",
        ]
        out["reference_health"] = {"warnings": ref_warnings}
        (self.out_dir / "sequential_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
        return out

    def config_record(self) -> dict:
        replay_cfg = asdict(self.cfg)
        # concurrency 는 실행 구간마다 다를 수 있어 execution_segments 에만 남긴다 (마지막 값으로 덮어쓰지 않는다)
        replay_cfg.pop("concurrency", None)
        segments = self._read("run_segments.jsonl")
        return {
            "replay": replay_cfg,
            "execution_segments": segments,
            "concurrency_values": sorted({sg["concurrency"] for sg in segments}),
            "answer_sampling": self.answer.llm.sampling_info(),
            "answer_backend": {"backend": self.answer.llm.backend, "base_url": self.answer.llm.base_url},
            "judge": {"model": self.judge.model, "mode": self.cfg.judge_mode},
            "prompt": {"version": self.prompt.version, "sha256": self.prompt.sha256},
            "scenarios": {s["scenario_id"]: {"hash": scenario_hash(s), "status": s["status"], "turns": len(s["turns"])}
                          for s in self.scenarios},
            "compressor_configs": {n: c.config() for n, c in self.compressors.items()},
            "summarizer": ({e: sm.config() for e, sm in self.summarizer.items()} if isinstance(self.summarizer, dict)
                           else self.summarizer.config() if self.summarizer else None),
            "presummary": self.presummary_store.config() if self.presummary_store else None,
            "notes_extractor": self.notes_extractor.config() if self.notes_extractor else None,
            "tokenizer": CFG.tokenizer,
            "tokenizer_check": self.tokenizer_check,
        }


# ---------------- 요약 ----------------

def _rate(rows, pred):
    return round(sum(1 for r in rows if pred(r)) / len(rows), 4) if rows else None


def answer_health(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "reasoning_ran": sum((r.get("reasoning_tokens") or 0) > 0 for r in rows),
        "reasoning_zero": sum(r.get("reasoning_tokens") == 0 for r in rows),
        "reasoning_unknown": sum(r.get("reasoning_tokens") is None for r in rows),
        "finish_length": sum(r.get("finish_reason") == "length" for r in rows),
        "finish_length_rate": _rate(rows, lambda r: r.get("finish_reason") == "length"),
        "empty_response": sum(bool(r.get("empty_response")) for r in rows),
        "empty_response_rate": _rate(rows, lambda r: r.get("empty_response")),
    }


def _sum(rows, k):
    return sum(r.get(k) or 0 for r in rows)


def _usd(rows):
    """답변 비용 + 압축(요약) 호출 비용. 실험상 비용(호출당) 기준."""
    return sum(((r.get("cost") or {}).get("usd") or 0) + ((r.get("compress_cost") or {}).get("usd") or 0)
               for r in rows)


def _ratio(num, den):
    return round(num / den, 4) if den else None


def cache_metrics(rows: list[dict]) -> dict:
    """접두부 공유율(직전 턴 요청과 메시지 단위로 겹치는 접두부 / 입력 추정) 과 실제 캐시 적중률(서버 cached_tokens)."""
    ok = [r for r in rows if not r.get("summary_failed")]
    known = [r for r in ok if r.get("cached_tokens") is not None]
    return {
        "prefix_share_mean": _mean(_ratio(r.get("prefix_shared_tokens") or 0, r.get("input_tokens_est")) for r in ok),
        "prefix_share_raw_mean": _mean(_ratio(r.get("prefix_shared_tokens_raw") or 0, r.get("input_tokens_est"))
                                       for r in ok),
        "actual_cache_hit_rate": _ratio(_sum(known, "cached_tokens"), _sum(known, "prompt_tokens")) if known else None,
        "actual_cache_known_trials": len(known),
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def compress_cost_of(results: list) -> dict:
    """요약 호출 비용. usd: 서버 보고 cached_tokens 반영 (참고), usd_nocache: 캐시 없이 (시뮬레이션 비용에 쓴다)."""
    return {"usd": round(sum((compute_cost(r).usd or 0) for r in results), 8),
            "usd_nocache": round(sum((cost_from_fields(r.model, r.prompt_tokens, r.completion_tokens, 0, 0,
                                                       r.usage_source).usd or 0) for r in results), 8),
            "calls": len(results)}


def sim_cost(row: dict) -> dict:
    """prefix_shared_tokens 로 계산한 시뮬레이션 캐시 비용 (답변 호출 하나).
    단위 맞춤: 접두부는 TOKENIZER 단위라 API prompt_tokens × (prefix_shared_tokens / input_tokens_est) 를 캐시 읽기 토큰으로 본다."""
    from multiturn.estimate import call_usd
    est, pt = row.get("input_tokens_est") or 0, row.get("prompt_tokens") or 0
    cached = min(pt, round(pt * (row.get("prefix_shared_tokens") or 0) / est)) if est else 0
    price = find_price(row.get("model") or "", load_pricing())[1]
    if price is None:
        return {"usd_nocache": None, "usd_read": None, "usd_write": None, "sim_cached_tokens": cached}
    u = call_usd(pt, cached, row.get("completion_tokens") or 0, price)
    return {"usd_nocache": u["no_cache"], "usd_read": u["prefix_cache"], "usd_write": u["prefix_cache_write"],
            "sim_cached_tokens": cached}


def _usd_sim(rows, variant: str) -> float:
    """시뮬레이션 캐시 비용 합 (답변 + 요약). 요약 호출은 캐시 없이 센다 (입력이 매번 달라 접두부 공유가 거의 없음)."""
    tot = 0.0
    for r in rows:
        c = r.get("cost_sim") or sim_cost(r)
        tot += (c.get(variant) or 0) + ((r.get("compress_cost") or {}).get("usd_nocache")
                                        or (r.get("compress_cost") or {}).get("usd") or 0)
    return tot


def sequential_summary(rows: list[dict]) -> dict:
    """--sequential-chains 결과: 턴별 시뮬레이션 캐시 토큰과 실측 cached_tokens."""
    out = {}
    for name in sorted({r["compressor"] for r in rows}):
        rs = [r for r in rows if r["compressor"] == name and not r.get("summary_failed")]
        known = [r for r in rs if r.get("cached_tokens") is not None]
        out[name] = {
            "turns": [{k: r.get(k) for k in ("scenario_id", "sample_idx", "turn", "prompt_tokens", "sim_cached_tokens",
                                             "cached_tokens", "prefix_shared_tokens_raw", "summary_calls")} for r in rs],
            "sim_cached_total": _sum(rs, "sim_cached_tokens"),
            "measured_cached_total": _sum(known, "cached_tokens") if known else None,
            "prompt_total": _sum(rs, "prompt_tokens"),
            "sim_hit_rate": _ratio(_sum(rs, "sim_cached_tokens"), _sum(rs, "prompt_tokens")),
            "measured_hit_rate": _ratio(_sum(known, "cached_tokens"), _sum(known, "prompt_tokens")) if known else None,
            "mean_abs_diff_tokens": _mean(abs((r.get("sim_cached_tokens") or 0) - r["cached_tokens"]) for r in known),
            "cost_sim_read_usd": round(sum((r["cost_sim"].get("usd_read") or 0) for r in rs), 6),
            "cost_measured_usd": round(sum(((r.get("cost_measured") or {}).get("usd") or 0) for r in rs), 6),
            "summary_failed": any(r.get("summary_failed") for r in rows if r["compressor"] == name),
        }
    return out


def _pct_reduction(base: float, comp: float):
    return round(100 * (1 - comp / base), 2) if base else None


COST_BASIS_NOTE = ("비용 절감률 주 지표는 cost_reduction_pct_sim (시뮬레이션 캐시 비용: prefix_shared_tokens 를 캐시 읽기로, "
                   "_sim_write 는 미스 부분을 캐시 쓰기 단가로) 이다. replay 는 턴을 병렬·순서 무관하게 보내므로 실측 cached_tokens 는 "
                   "실제 대화의 캐시 동작이 아니다. 그래서 실측 기반 cost_reduction_pct_measured 는 참고용이다 "
                   "(검증은 --sequential-chains). 모든 비용은 실험상 비용(호출당): 응답 캐시 적중과 무관하게 원래 호출의 usage 로 센다. "
                   "요약 호출은 캐시 없이 센다. 실제 지출은 budget 에 따로 있다.")
SIM_INTERPRETATION_NOTE = ("두 비용 열의 해석: sim (cost_reduction_pct_sim, _sim_write) 은 대화 간격이 캐시 보존 시간(30분) 안이라는 가정이다 "
                           "(직전 턴 요청의 접두부가 아직 캐시에 남아 있음). nocache (cost_reduction_pct_nocache) 는 캐시가 만료된 경우의 경계값이다 "
                           "(매 턴 입력 전부를 input 단가로). 실제 서비스 비용은 대화 간격 분포에 따라 두 값 사이에 놓인다.")
REFERENCE_SPEND_NOTE = ("none 의 reference sample 은 기준 궤적과 같은 요청이라 응답 캐시에 적중해 실제 지출이 0원이다 "
                        "(기준 궤적 호출로 이미 한 번 냈다).")


def budget_block(replay_steps: list, reference_steps: list, rows: list[dict] | None = None) -> dict:
    """예산 확인용 실제 지출 (응답 캐시 적중은 0원). 압축기 비교에는 쓰지 않는다."""
    def actual(steps):
        return round(sum((st.cost or {}).get("usd") or 0 for st in steps if not st.cache_hit), 6)
    by_comp = defaultdict(list)
    for st in replay_steps:
        by_comp[st.compressor].append(st)
    return {
        "answer_usd_actual_total": round(actual(replay_steps) + actual(reference_steps), 6),
        "reference_usd_actual": actual(reference_steps),
        "replay_usd_actual_by_compressor": {c: actual(v) for c, v in sorted(by_comp.items())},
        "replay_cache_hits_by_compressor": {c: sum(st.cache_hit for st in v) for c, v in sorted(by_comp.items())},
        "summary_calls_usd_experimental": round(sum(((r.get("compress_cost") or {}).get("usd") or 0)
                                                    for r in rows or []), 6),
        "notes": [REFERENCE_SPEND_NOTE, "요약 호출 비용은 실험상 비용으로만 낸다 (이어 돌리기에서 상태 재구성용 요약은 캐시 적중이라 0원).", "실행을 이어 돌린 경우 앞선 실행에서 이미 받은 응답도 이번에는 캐시 적중(0원)으로 센다.",
                  "채점 비용(judge_cost)은 trial 행에만 있고 평가 비용이라 여기 넣지 않는다."],
    }


# --cost-mode none 이면 summary 에서 빼는 캐시 관련 키 (compare_block / overflow_block / budget_table)
CACHE_BLOCK_KEYS = ("cache", "cost_basis", "cost_reduction_pct_sim", "cost_reduction_pct_sim_write",
                    "cost_reduction_pct_nocache", "cost_usd_sim", "cost_reduction_pct_measured", "cost_usd_measured")
TOKEN_BASIS_NOTE = ("주 지표는 토큰 기준이다 (캐시가 없는 LLM 가정): 입력 토큰 절감률, 총 토큰 절감률(입력 + 출력(추론 포함) + "
                    "압축에 쓴 LLM 토큰(요약·메모, 추론 포함)), 정확도 유지율, 비열등 판정. 토큰은 서버 usage 기준 실험상 값이다 "
                    "(응답 캐시 적중이어도 원래 호출의 usage). presummary 의 요약 생성 토큰은 run 이 아니라 구축 비용(presummary_build) 이다.")
PRESUMMARY_BUILD_NOTE = ("presummary 의 총 토큰 절감률은 두 값을 낸다. total_token_reduction_pct_without_build: 구축 토큰을 빼고 계산 "
                         "(= total_token_reduction_pct). total_token_reduction_pct_with_build: 이 run 이 쓰는 페이지의 구축 토큰 "
                         "전부를 이 run 의 압축 쪽 토큰에 더해 계산. 실서비스에서는 페이지 요약을 여러 대화가 공유하므로, "
                         "구축 토큰을 이 run 에 전부 넣은 with_build 는 구축 비용 부담의 상한(절감률의 하한)이고 "
                         "without_build 는 대화가 충분히 많을 때의 극한이다. 실제 값은 둘 사이다.")


def build_tokens_of(build: dict | None) -> int:
    if not build:
        return 0
    return (build.get("build_prompt_tokens") or 0) + (build.get("build_completion_tokens") or 0)


def add_build_reduction(block: dict, build: dict | None) -> dict:
    """presummary 블록에 구축 토큰을 넣은 총 토큰 절감률과 뺀 값을 더한다."""
    if not block or not block.get("tokens"):
        return block
    base, comp = block["tokens"]["none"]["total"], block["tokens"]["compressed"]["total"]
    bt = build_tokens_of(build)
    block["total_token_reduction_pct_without_build"] = block.get("total_token_reduction_pct")
    block["total_token_reduction_pct_with_build"] = _pct_reduction(base, comp + bt)
    block["presummary_build_tokens"] = bt
    return block


def token_totals(rows: list[dict]) -> dict:
    """답변 입력·출력(추론 포함)·추론, 압축 LLM 입력·출력(추론 포함)·추론 토큰 합."""
    inp, out = _sum(rows, "prompt_tokens"), _sum(rows, "completion_tokens")
    reas = _sum(rows, "reasoning_tokens")
    cp, cc = _sum(rows, "compress_llm_prompt_tokens"), _sum(rows, "compress_llm_completion_tokens")
    return {"input": inp, "output": out, "reasoning": reas, "output_visible": out - reas,
            "compress_input": cp, "compress_output": cc, "compress_reasoning": _sum(rows, "compress_llm_reasoning_tokens"),
            "compress": cp + cc, "total": inp + out + cp + cc}


def _acc_cell(pairs) -> dict:
    if not pairs:
        return {"n_pairs": 0}
    b = _mean(x["answer_accuracy"] for x, _ in pairs)
    c = _mean(y["answer_accuracy"] for _, y in pairs)
    return {"n_pairs": len(pairs), "n_turns": len({(y["scenario_id"], y["turn"]) for _, y in pairs}),
            "none": b, "compressed": c, "retention_pct": round(100 * c / b, 2) if b else None}


def accuracy_breakdown(pairs: list[tuple[dict, dict]]) -> dict:
    """턴 유형별(시나리오에 나오는 turn_type 그대로) · recall 거리별 정확도.
    거리 = depends_distance_max (현재 턴 − 가장 먼 의존 턴). recall 턴만, 그리고 의존이 있는 모든 턴."""
    by_type = defaultdict(list)
    by_dist_recall, by_dist_all = defaultdict(list), defaultdict(list)
    for b, c in pairs:
        by_type[c["turn_type"]].append((b, c))
        d = c.get("depends_distance_max")
        if d is not None:
            by_dist_all[d].append((b, c))
            if c["turn_type"] == "recall":
                by_dist_recall[d].append((b, c))
    return {"by_turn_type": {tt: _acc_cell(v) for tt, v in sorted(by_type.items())},
            "by_recall_distance": {str(d): _acc_cell(v) for d, v in sorted(by_dist_recall.items())},
            "by_dependency_distance": {str(d): _acc_cell(v) for d, v in sorted(by_dist_all.items())}}


def notes_compression(rows: list[dict]) -> dict | None:
    """fact_notes 가 턴마다 만든 메모의 실제 압축률 (메모 토큰 / 그 턴 문서 토큰). sample 별로 따로 만든다."""
    made = [r["notes_made"] for r in rows if r.get("notes_made")]
    if not made:
        return None
    ok = [m for m in made if not m.get("failed") and m.get("notes_tokens") is not None]
    by_turn = defaultdict(list)
    for r in rows:
        m = r.get("notes_made")
        if m and m.get("ratio") is not None:
            by_turn[f"{r['scenario_id']}:{r['turn']}"].append(m["ratio"])
    return {"notes": len(made), "failed": len(made) - len(ok),
            "target_ratio": made[0].get("target_ratio"),
            "ratio_mean": _mean(m["ratio"] for m in ok),
            "ratio_total": _ratio(sum(m["notes_tokens"] for m in ok), sum(m["source_tokens"] for m in ok)),
            "over_2x_target": sum(bool(m.get("over_2x_target")) for m in ok),
            "over_2x_target_rate": _ratio(sum(bool(m.get("over_2x_target")) for m in ok), len(ok)),
            "by_turn_ratio_mean": {k: _mean(v) for k, v in sorted(by_turn.items())}}


SETUP_NOTE = ("key_fact 에 setup 태그(같은 턴 사용자 발화에 답이 그대로 있는 설정 확인 항목)가 있는 턴은 주 정확도"
              "(answer_accuracy, 유지율, 정확도 유지 확인 non_inferiority)에서 setup 항목을 뺀다. setup 항목도 채점은 하며 정확도는 setup_accuracy 에 따로 낸다. "
              "행의 answer_accuracy_all 은 setup 포함 원래 채점 결과. key_fact 가 전부 setup 인 턴은 주 집계에서 빠진다.")


def setup_accuracy_block(rows: list[dict], compressors: list[str]) -> dict | None:
    """setup 항목 정확도 (압축기별). setup 항목이 있는 trial 이 없으면 None (v1 시나리오: summary 에 키를 내지 않는다)."""
    if not any(r.get("setup_total") for r in rows):
        return None
    out = {}
    for c in compressors:
        rs = [r for r in rows if r["compressor"] == c and r.get("setup_total")]
        out[c] = {"trials": len(rs), "turns": len({(r["scenario_id"], r["turn"]) for r in rs}),
                  "facts": sum(r["setup_total"] for r in rs),
                  "accuracy": _mean(r.get("setup_accuracy") for r in rs),
                  "fact_accuracy": _ratio(sum(r.get("setup_satisfied") or 0 for r in rs), sum(r["setup_total"] for r in rs)),
                  "main_excluded_trials": sum(1 for r in rs if r.get("total_facts") == 0),
                  "by_turn_type": {tt: _mean(r.get("setup_accuracy") for r in rs if r["turn_type"] == tt)
                                   for tt in sorted({r["turn_type"] for r in rs})}}
    return out


def presummary_build_block(store, scenarios: list[dict]) -> dict:
    """presummary 구축 비용과 페이지별 실제 압축률 (이 run 이 쓰는 페이지만). run 의 압축 LLM 토큰은 0 이다."""
    from multiturn.build_presummaries import pages_of
    pages = set(pages_of(scenarios))
    log = [r for r in store.build_log() if r["page"] in pages]
    ok = [r for r in log if not r.get("failed")]
    return {
        "note": "구축 비용: 위키 구축 단계에서 페이지마다 한 번 만든 요약의 비용이다. 실험 run 비용(총 토큰 절감률)에 넣지 않는다.",
        "manifest": store.manifest, "pages": len(log), "pages_needed": len(pages),
        "build_prompt_tokens": _sum(log, "prompt_tokens"), "build_completion_tokens": _sum(log, "completion_tokens"),
        "build_reasoning_tokens": _sum(log, "reasoning_tokens"), "build_usd": round(sum(r.get("usd") or 0 for r in log), 6),
        "ratio_mean": _mean(r.get("ratio") for r in ok),
        "ratio_total": _ratio(_sum(ok, "summary_tokens"), _sum(ok, "source_tokens")),
        "over_2x_target": sum(bool(r.get("over_2x_target")) for r in ok),
        "by_page": {r["page"]: {k: r.get(k) for k in ("source_tokens", "target_tokens", "summary_tokens", "ratio",
                                                      "over_2x_target")} for r in sorted(log, key=lambda r: r["page"])},
    }


def _strip_cache(block: dict) -> dict:
    out = {k: v for k, v in block.items() if k not in CACHE_BLOCK_KEYS}
    if isinstance(out.get("excluding_overflow"), dict):
        out["excluding_overflow"] = {k: v for k, v in out["excluding_overflow"].items() if k not in CACHE_BLOCK_KEYS}
    return out


def compare_block(pairs: list[tuple[dict, dict]], cfg: ReplayConfig, n_scenarios: int) -> dict:
    """짝지은 (none, 압축) trial 들의 절감률·정확도·비열등 판정."""
    if not pairs:
        return {"n_pairs": 0}
    all_pairs = pairs
    failed = [c for _, c in pairs if c.get("summary_failed")]
    pairs = [(b, c) for b, c in pairs if not c.get("summary_failed")]     # 토큰·비용은 실제로 답한 trial 만
    bs = [b for b, _ in pairs]
    cs = [c for _, c in pairs]
    base_total = _sum(bs, "prompt_tokens") + _sum(bs, "completion_tokens")
    comp_total = (_sum(cs, "prompt_tokens") + _sum(cs, "completion_tokens")
                  + _sum(cs, "compress_llm_prompt_tokens") + _sum(cs, "compress_llm_completion_tokens"))
    # 정확도 주 기준: 요약 실패 턴을 0점으로 포함. 보조: 실패 턴을 뺀 집계
    turn = bootstrap_diff(all_pairs, unit="turn", boot=cfg.boot, seed=cfg.seed)
    cluster = bootstrap_diff(all_pairs, unit="scenario", boot=cfg.boot, seed=cfg.seed)
    excl = bootstrap_diff(pairs, unit="turn", boot=cfg.boot, seed=cfg.seed) if failed else None
    comp_rows = [c for _, c in all_pairs]
    tb, tc = token_totals(bs), token_totals(cs)
    block = {
        "n_pairs": len(all_pairs),
        "summary_failed": len(failed),
        "summary_failed_rate": _ratio(len(failed), len(all_pairs)),
        "overflow_rate": _rate(cs, lambda r: bool(r.get("overflow"))),
        "summary_calls": _sum(comp_rows, "summary_calls"),
        "recompress_count": sum(1 for r in cs if r.get("recompressed")),
        "compress_cost_usd": round(sum(((r.get("compress_cost") or {}).get("usd") or 0) for r in comp_rows), 6),
        "cache": {"none": cache_metrics(bs), "compressed": cache_metrics(cs)},
        "history_reduction_pct": _pct_reduction(_sum(bs, "history_tokens_raw"), _sum(cs, "history_tokens_compressed")),
        "input_reduction_pct": _pct_reduction(_sum(bs, "prompt_tokens"), _sum(cs, "prompt_tokens")),
        "total_token_reduction_pct": _pct_reduction(base_total, comp_total),
        "output_reduction_pct": _pct_reduction(tb["output"], tc["output"]),
        "reasoning_reduction_pct": _pct_reduction(tb["reasoning"], tc["reasoning"]),
        "compress_token_share_pct": round(100 * tc["compress"] / tc["total"], 2) if tc["total"] else None,
        "tokens": {"none": tb, "compressed": tc},
        # 비용 주 지표: 시뮬레이션 캐시 비용 (prefix_shared_tokens). 실측(cached_tokens) 은 참고
        "cost_basis": "simulated_prefix_cache",
        "cost_reduction_pct_sim": _pct_reduction(_usd_sim(bs, "usd_read"), _usd_sim(cs, "usd_read")),
        "cost_reduction_pct_sim_write": _pct_reduction(_usd_sim(bs, "usd_write"), _usd_sim(cs, "usd_write")),
        "cost_reduction_pct_nocache": _pct_reduction(_usd_sim(bs, "usd_nocache"), _usd_sim(cs, "usd_nocache")),
        "cost_usd_sim": {"none": round(_usd_sim(bs, "usd_read"), 6), "compressed": round(_usd_sim(cs, "usd_read"), 6)},
        "cost_reduction_pct_measured": _pct_reduction(_usd(bs), _usd(cs)),            # 참고
        "cost_usd_measured": {"none": round(_usd(bs), 6), "compressed": round(_usd(cs), 6)},
        "reasoning_tokens": {"none_mean": _mean(r.get("reasoning_tokens") for r in bs),
                             "compressed_mean": _mean(r.get("reasoning_tokens") for r in cs)},
        "completion_tokens": {"none_mean": _mean(r.get("completion_tokens") for r in bs),
                              "compressed_mean": _mean(r.get("completion_tokens") for r in cs)},
        "accuracy": {"none": _mean(b["answer_accuracy"] for b, _ in all_pairs),
                     "compressed": _mean(c["answer_accuracy"] for _, c in all_pairs)},
        "retention_pct": turn.get("retention_pct"),
        "not_found_rate": {"none": _rate(bs, lambda r: r.get("not_found")),
                           "compressed": _rate(cs, lambda r: r.get("not_found"))},
        "entity_retention_mean": _mean(r.get("entity_retention") for r in cs),
        "paired_bootstrap_turn": turn,                                      # 주 판정
        "non_inferiority": non_inferiority(turn, cfg.margin),
        "cluster_bootstrap_scenario": cluster,                              # 보조
        "non_inferiority_cluster": non_inferiority(cluster, cfg.margin),
        "excluding_summary_failed": ({"paired_bootstrap_turn": excl, "non_inferiority": non_inferiority(excl, cfg.margin)}
                                     if excl is not None else None),                 # 보조
        "excluding_overflow": overflow_block(all_pairs, cfg),                          # 보조
        "accuracy_breakdown": accuracy_breakdown(all_pairs),
    }
    return block if cfg.cost_mode == "cache" else _strip_cache(block)


def overflow_block(all_pairs, cfg: ReplayConfig) -> dict | None:
    """overflow 턴(최근 원문 턴만으로 예산 초과)을 뺀 집계. 예산형이 아니면 None."""
    if not any(c.get("history_budget") is not None for _, c in all_pairs):
        return None
    ps = [(b, c) for b, c in all_pairs if not c.get("overflow")]
    ok = [(b, c) for b, c in ps if not c.get("summary_failed")]
    t = bootstrap_diff(ps, unit="turn", boot=cfg.boot, seed=cfg.seed) if ps else {"n_pairs": 0}
    bs, cs = [b for b, _ in ok], [c for _, c in ok]
    return {"n_pairs": len(ps), "retention_pct": t.get("retention_pct"), "paired_bootstrap_turn": t,
            "non_inferiority": non_inferiority(t, cfg.margin) if ps else None,
            "input_reduction_pct": _pct_reduction(_sum(bs, "prompt_tokens"), _sum(cs, "prompt_tokens")),
            "total_token_reduction_pct": _pct_reduction(token_totals(bs)["total"], token_totals(cs)["total"]),
            "cost_reduction_pct_sim": _pct_reduction(_usd_sim(bs, "usd_read"), _usd_sim(cs, "usd_read"))}


def summarize_replay(rows: list[dict], cfg: ReplayConfig, ref_warnings: list[str] | None = None,
                     n_scenarios: int | None = None, presummary_build: dict | None = None) -> dict:
    n_scen = n_scenarios or len({r["scenario_id"] for r in rows})
    subsets = {"all": lambda r: True, "depends_on_reference_ok": lambda r: r["depends_on_reference_ok"]}
    out: dict = {
        "notes": [
            "주 판정은 (시나리오, 턴) 단위 쌍체 부트스트랩이다. sample 은 같은 턴 안에서 평균한다.",
            f"시나리오 군집 부트스트랩은 보조 결과다. 시나리오 {n_scen}개로 재추출하므로 구간이 넓고 불안정하다"
            + (" (파일럿 규모)." if n_scen < 10 else "."),
            "depends_on_reference_ok=False 인 턴은 기준 궤적의 앞 턴 답변이 틀려 압축과 무관하게 틀릴 수 있다.",
            "요약 실패 턴은 정확도 주 기준에서 0점으로 넣는다 (실서비스에서 나쁜 결과). 실패 턴을 뺀 집계는 excluding_summary_failed (보조). "
            "토큰·비용 절감률은 실제로 답한 trial 만으로 계산한다.",
            TOKEN_BASIS_NOTE,
            "fact_notes 의 메모 추출 토큰은 메모를 만든 턴의 trial 에 넣는다 (이후 턴의 재사용은 0).",
            REFERENCE_SPEND_NOTE,
        ] + ([PRESUMMARY_BUILD_NOTE] if cfg.has_presummary else [])
          + ([SETUP_NOTE] if any(r.get("setup_total") for r in rows) else []) + ([
            "prefix_shared_tokens 는 직전 턴 요청과 메시지 단위로 겹치는 접두부 토큰 (1,024 미만은 0, 원래 값은 _raw). "
            "actual_cache_hit_rate 는 서버가 보고한 cached_tokens / prompt_tokens.",
            COST_BASIS_NOTE,
            SIM_INTERPRETATION_NOTE,
        ] if cfg.cost_mode == "cache" else []),
        "cost_mode": cfg.cost_mode,
        "reference_health": {"warnings": ref_warnings or [], "n_warnings": len(ref_warnings or [])},
        "n_trials": len(rows),
        "answer_health": {c: answer_health([r for r in rows if r["compressor"] == c and not r.get("summary_failed")])
                          for c in cfg.compressors},
        "summary_failure": {c: {"trials": len(rs), "summary_failed": sum(bool(r.get("summary_failed")) for r in rs),
                                "rate": _rate(rs, lambda r: bool(r.get("summary_failed"))),
                                "chains_failed": len({(r["scenario_id"], r["sample_idx"]) for r in rs if r.get("summary_failed")})}
                            for c in cfg.compressors if is_stateful(c)
                            for rs in [[r for r in rows if r["compressor"] == c]]},
        "accuracy_by_turn_type": {c: {tt: _mean(r["answer_accuracy"] for r in rows if r["compressor"] == c
                                                 and r["turn_type"] == tt and r.get("answer_accuracy") is not None)
                                      for tt in sorted({r["turn_type"] for r in rows})} for c in cfg.compressors},
        "accuracy_by_recall_distance": {c: {str(d): _mean(r["answer_accuracy"] for r in rows if r["compressor"] == c
                                                         and r["turn_type"] == "recall"
                                                         and r.get("depends_distance_max") == d
                                                         and r.get("answer_accuracy") is not None)
                                            for d in sorted({r["depends_distance_max"] for r in rows
                                                             if r["turn_type"] == "recall"
                                                             and r.get("depends_distance_max") is not None})}
                                        for c in cfg.compressors},
        "not_found_rate_by_turn_type": {
            c: {tt: _rate([r for r in rows if r["compressor"] == c and r["turn_type"] == tt], lambda r: r["not_found"])
                for tt in sorted({r["turn_type"] for r in rows})}
            for c in cfg.compressors},
        "compressors": {},
    }
    # none 대 none 잡음 기준선: reference sample 이 아닌 none sample 을 reference sample 과 짝짓는다
    noise = {}
    for name, pred in subsets.items():
        sub = [r for r in rows if pred(r)]
        noise[name] = compare_block(pair_rows(sub, "none", base="none", base_sample=cfg.reference_sample), cfg, n_scen)
    out["noise_none_vs_none"] = noise
    for comp in cfg.compressors:
        if comp == "none":
            continue
        block = {}
        for name, pred in subsets.items():
            sub = [r for r in rows if pred(r)]
            pairs = pair_rows(sub, comp)
            block[name] = compare_block(pairs, cfg, n_scen)
            if "presummary" in comp:
                # 구축 토큰은 run 전체(이 run 이 쓰는 페이지)의 것이라 부분집합·턴별 블록에는 넣지 않는다
                add_build_reduction(block[name], presummary_build if name == "all" else None)
                if name != "all":
                    block[name].pop("total_token_reduction_pct_with_build", None)
                    block[name].pop("presummary_build_tokens", None)
            block[f"{name}_by_turn_type"] = {
                tt: compare_block([p for p in pairs if p[1]["turn_type"] == tt], cfg, n_scen)
                for tt in sorted({p[1]["turn_type"] for p in pairs})}
        block["by_turn"] = {str(k): compare_block([p for p in pair_rows(rows, comp) if p[1]["turn"] == k], cfg, n_scen)
                            for k in sorted({r["turn"] for r in rows})}
        out["compressors"][comp] = block
    if cfg.cost_mode == "cache":
        out["cache_by_compressor"] = {c: cache_metrics([r for r in rows if r["compressor"] == c]) for c in cfg.compressors}
    nc = {c: notes_compression([r for r in rows if r["compressor"] == c]) for c in cfg.compressors}
    if any(nc.values()):
        out["fact_notes_compression"] = {c: v for c, v in nc.items() if v}
    setup = setup_accuracy_block(rows, cfg.compressors)
    if setup is not None:
        out["setup_accuracy"] = setup
    out["budget_table"] = budget_table(out["compressors"], cfg)
    return out


TABLE_KEYS = ("n_pairs", "history_reduction_pct", "input_reduction_pct", "total_token_reduction_pct",
              "output_reduction_pct", "reasoning_reduction_pct", "compress_token_share_pct",
              "retention_pct", "overflow_rate", "summary_failed_rate", "summary_calls", "recompress_count",
              "compress_cost_usd")
CACHE_TABLE_KEYS = ("cost_reduction_pct_sim", "cost_reduction_pct_sim_write", "cost_reduction_pct_nocache",
                    "cost_reduction_pct_measured")


def budget_table(blocks: dict, cfg: ReplayConfig) -> dict:
    """예산 × 압축기 비교표 (none 대비, 토큰 기준). 예산이 없는 압축기는 "no_budget" 아래에 둔다.
    키: 절대 예산 "2000", 비율 예산 "r=0.5". --cost-mode cache 면 캐시 관련 열을 더한다."""
    table: dict = {}
    cache = cfg.cost_mode == "cache"
    for comp, block in blocks.items():
        b = block.get("all") or {}
        key = str(budget_of(comp)) if budget_of(comp) is not None else "no_budget"
        row = {k: b.get(k) for k in TABLE_KEYS + (CACHE_TABLE_KEYS if cache else ())}
        if "presummary" in comp:
            row["total_token_reduction_pct_without_build"] = b.get("total_token_reduction_pct_without_build")
            row["total_token_reduction_pct_with_build"] = b.get("total_token_reduction_pct_with_build")
        row["reasoning_mean"] = b.get("reasoning_tokens")
        row["non_inferior"] = (b.get("non_inferiority") or {}).get("non_inferior")
        row["non_inferior_cluster"] = (b.get("non_inferiority_cluster") or {}).get("non_inferior")
        ex = b.get("excluding_summary_failed")
        row["retention_pct_excluding_summary_failed"] = (ex or {}).get("paired_bootstrap_turn", {}).get("retention_pct") if ex else None
        eo = b.get("excluding_overflow") or {}
        row["n_pairs_excluding_overflow"] = eo.get("n_pairs")
        row["retention_pct_excluding_overflow"] = eo.get("retention_pct")
        row["non_inferior_excluding_overflow"] = (eo.get("non_inferiority") or {}).get("non_inferior")
        row["total_token_reduction_pct_excluding_overflow"] = eo.get("total_token_reduction_pct")
        if cache:
            row["cost_reduction_pct_sim_excluding_overflow"] = eo.get("cost_reduction_pct_sim")
            cm = (b.get("cache") or {}).get("compressed") or {}
            row["prefix_share_mean"] = cm.get("prefix_share_mean")
            row["actual_cache_hit_rate"] = cm.get("actual_cache_hit_rate")
        table.setdefault(key, {})[label_of(comp) if key != "no_budget" else comp] = row

    def order(kv):
        k = kv[0]
        if k == "no_budget":
            return (2, 0.0)
        return (0, float(k)) if k.isdigit() else (1, float(k[2:]))
    return dict(sorted(table.items(), key=order))


# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="멀티턴 replay 실험")
    ap.add_argument("--scenarios", required=True, help="시나리오 폴더 (예: data/evalsets/multiturn-v1)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--compressors", default="none,window(2),per_message(rule)",
                    help='쉼표로 구분, none 필수. 예: "none,window(2),per_message(rule)"')
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--reasoning-effort", required=True, choices=REASONING_EFFORT_CHOICES,
                    help="필수. server_default = 보내지 않음 (서버 기본값)")
    ap.add_argument("--max-completion-tokens", type=int, required=True, help="필수. 추론 토큰 포함 출력 한도")
    ap.add_argument("--temperature", default=SERVER_DEFAULT, help="server_default(보내지 않음) 또는 숫자")
    ap.add_argument("--reference-sample", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--margin", type=float, default=0.10, help="비열등 마진 (none 정확도의 비율)")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--prompt", default="v2", help="src/prompts/mt_answer_<version>.md (기본 v2)")
    ap.add_argument("--cost-mode", default="none", choices=COST_MODES,
                    help="none(기본): 토큰 지표만. cache: 캐시 관련 비용 지표(sim, nocache, 접두부 공유율, 실측)도 summary 에")
    ap.add_argument("--presummary-model", help="presummary 가 있으면 필수. data/presummaries/<모델>/ 의 요약을 쓴다")
    ap.add_argument("--presummary-dir", help="(presummary) 요약 폴더를 직접 지정 (기본 data/presummaries/<presummary-model>)")
    ap.add_argument("--notes-model", help="fact_notes 가 있으면 필수")
    ap.add_argument("--notes-reasoning-effort", choices=REASONING_EFFORT_CHOICES, help="fact_notes 가 있으면 필수")
    ap.add_argument("--notes-max-tokens", type=int, help="fact_notes 가 있으면 필수 (추론 포함 출력 한도)")
    ap.add_argument("--notes-target-ratio", type=float, default=0.25, help="메모 목표 길이 = 그 턴 문서 토큰 × 비율 (기본 0.25)")
    ap.add_argument("--history-budget", default="2000,4000,8000",
                    help="예산형 압축기 기록 토큰 예산, 쉼표로 여러 개 (파일럿 기본 2000,4000,8000)")
    ap.add_argument("--keep-recent", type=int, default=1, help="예산형 압축기가 항상 원문으로 남기는 최근 턴 수")
    ap.add_argument("--summary-model", help="요약형 압축기가 있으면 필수")
    ap.add_argument("--summary-reasoning-effort",
                    help=f"요약형 압축기가 있으면 필수. 쉼표로 여러 조건 (예: server_default,none). 값: {', '.join(REASONING_EFFORT_CHOICES)}")
    ap.add_argument("--sequential-chains", metavar="COMPRESSORS",
                    help='캐시 검증 모드: 이 압축기들의 체인을 턴 순서대로·동시 실행 없이·응답 캐시를 끄고 보낸다 (예: "none,frozen_summary(4000)")')
    ap.add_argument("--chain-scenarios", default="", help="(--sequential-chains) 시나리오 id, 쉼표 구분. 기본: 시나리오마다 전부")
    ap.add_argument("--chain-samples", default="0", help="(--sequential-chains) sample_idx, 쉼표 구분")
    ap.add_argument("--summary-max-tokens", type=int, help="요약형 압축기가 있으면 필수 (추론 포함 출력 한도)")
    ap.add_argument("--judge-mode", default=CFG.judge_mode)
    ap.add_argument("--resume", metavar="RUN_ID", help="results/runs/mt_<RUN_ID> 를 이어서")
    ap.add_argument("--allow-approx-tokenizer", action="store_true",
                    help="TOKENIZER 가 답변 모델과 달라도 근사로 돈다 (summary 에 표시). 기본은 에러로 멈춤")
    ap.add_argument("--estimate-only", action="store_true", help="API 를 부르지 않고 예상 비용만 계산")
    ap.add_argument("--assume-answer-tokens", type=int, default=300, help="(--estimate-only) 기준 궤적이 없을 때 답변 길이")
    ap.add_argument("--assume-reasoning-tokens", type=int, default=1000, help="(--estimate-only) 호출당 추론 토큰")
    ap.add_argument("--judge-model", default=CFG.judge_model, help="(--estimate-only) 채점 단가를 찾을 모델 이름")
    ap.add_argument("--judge-in-per-call", type=int, default=261, help="(--estimate-only) judge 호출당 입력 토큰")
    ap.add_argument("--judge-out-per-call", type=int, default=101, help="(--estimate-only) judge 호출당 출력 토큰")
    ap.add_argument("--assume-summary-tokens", type=int, default=300, help="(--estimate-only) 요약 출력 길이")
    ap.add_argument("--assume-summary-reasoning-tokens", type=int, default=1000,
                    help="(--estimate-only) 요약 호출당 추론 토큰 (요약 조건 none 은 0 으로 둔다)")
    return ap


def config_from_args(a) -> ReplayConfig:
    return ReplayConfig(model=a.model, reasoning_effort=a.reasoning_effort,
                        max_completion_tokens=a.max_completion_tokens,
                        compressors=split_compressor_list(a.compressors), samples=a.samples,
                        reference_sample=a.reference_sample, temperature=a.temperature, prompt_version=a.prompt,
                        judge_mode=a.judge_mode, concurrency=a.concurrency, margin=a.margin, boot=a.boot,
                        history_budgets=parse_budget_list(a.history_budget),
                        keep_recent=a.keep_recent, summary_model=a.summary_model,
                        summary_reasoning_effort=a.summary_reasoning_effort, summary_max_tokens=a.summary_max_tokens,
                        presummary_model=a.presummary_model, notes_model=a.notes_model,
                        notes_reasoning_effort=a.notes_reasoning_effort, notes_max_tokens=a.notes_max_tokens,
                        notes_target_ratio=a.notes_target_ratio, cost_mode=a.cost_mode)


def main(argv=None):
    a = build_parser().parse_args(argv)
    cfg = config_from_args(a)
    from corpus import load_corpus
    from multiturn.scenario import load_scenarios
    scenarios = load_scenarios(a.scenarios)
    corpus = load_corpus()
    presummary_store = None
    if cfg.has_presummary:
        from multiturn.history_compressors import MissingPresummaryError, PresummaryStore
        try:
            presummary_store = (PresummaryStore(Path(a.presummary_dir)) if a.presummary_dir
                                else PresummaryStore.for_model(cfg.presummary_model))
        except MissingPresummaryError as e:
            if not a.estimate_only:
                sys.exit(f"[중단] {e}")
            print(f"[추정] {e} -> 원문 × 목표 비율 길이의 자리표시 요약으로 추정합니다", flush=True)
    if a.estimate_only:
        from multiturn.estimate import estimate, print_estimate
        tk = check_tokenizer(cfg.model, allow_approx=True)      # 추정은 근사여도 된다 (출력 맨 위에 표시)
        print_estimate(estimate(cfg, scenarios, corpus, answer_tokens=a.assume_answer_tokens,
                                reasoning_tokens=a.assume_reasoning_tokens, judge_model=a.judge_model,
                                judge_in=a.judge_in_per_call, judge_out=a.judge_out_per_call, tokenizer_check=tk,
                                summary_tokens=a.assume_summary_tokens,
                                summary_reasoning_tokens=a.assume_summary_reasoning_tokens,
                                presummary_store=presummary_store))
        return
    try:
        tk = check_tokenizer(cfg.model, allow_approx=a.allow_approx_tokenizer)
    except TokenizerMismatchError as e:
        sys.exit(f"[중단] {e}")
    if tk["approx"]:
        print(f"[근사 토크나이저] {tk['problems']}", flush=True)
    from llm import LLM
    from multiturn.response_cache import CachedLLM
    answer = CachedLLM(configure_answer_llm(LLM(role="answer"), cfg))
    judge = CachedLLM(LLM(role="judge"))
    summarizer = None
    seq = split_compressor_list(a.sequential_chains) if a.sequential_chains else []
    if seq:
        seq = expand_summary_efforts(expand_budgets(seq, cfg.history_budgets), cfg.summary_efforts)
    if cfg.has_summary or any(is_stateful(c) for c in seq):
        from multiturn.history_compressors import Summarizer
        summarizer = {e: Summarizer(CachedLLM(configure_summary_llm(LLM(role="answer"), cfg, e)))
                      for e in cfg.summary_efforts}
    notes_extractor = None
    if cfg.has_notes:
        from multiturn.history_compressors import NotesExtractor
        notes_extractor = NotesExtractor(CachedLLM(configure_notes_llm(LLM(role="answer"), cfg)),
                                         target_ratio=cfg.notes_target_ratio, token_counter=lambda t: count_tokens(t))
    run_id = a.resume or datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = CFG.results_dir / "runs" / f"mt_{run_id}"
    rep = Replay(cfg, scenarios, corpus, answer, judge, out_dir, tokenizer_check=tk, summarizer=summarizer,
                 presummary_store=presummary_store, notes_extractor=notes_extractor)
    try:
        if seq:
            out = rep.run_sequential(seq, [x for x in a.chain_scenarios.split(",") if x.strip()] or None,
                                     [int(x) for x in a.chain_samples.split(",") if x.strip()])
            print("[캐시 검증] " + json.dumps({k: {kk: v[kk] for kk in ("sim_hit_rate", "measured_hit_rate",
                                                                     "mean_abs_diff_tokens")} for k, v in out.items()
                                              if isinstance(v, dict) and "sim_hit_rate" in v}, ensure_ascii=False))
            print(f"저장: {out_dir / 'sequential_summary.json'}")
            return
        summary = rep.run()
    finally:
        answer.close()
        judge.close()
        for sm in (summarizer or {}).values():
            sm.cached.close()
        if notes_extractor is not None:
            notes_extractor.cached.close()
    keys = ("input_reduction_pct", "total_token_reduction_pct", "reasoning_reduction_pct", "retention_pct",
            "non_inferiority", "non_inferiority_cluster")
    if cfg.cost_mode == "cache":
        keys += ("cost_reduction_pct_sim", "cost_reduction_pct_measured")
    print("[압축기 비교] 토큰 기준 (none 대비)" + (" + 캐시 비용 지표" if cfg.cost_mode == "cache" else ""))
    print(json.dumps({c: {k: b["all"].get(k) for k in keys} for c, b in summary["compressors"].items()},
                     ensure_ascii=False, indent=1))
    if summary.get("fact_notes_compression"):
        print("[fact_notes 압축률] " + json.dumps({c: {k: v[k] for k in ("notes", "ratio_mean", "ratio_total",
                                                                           "over_2x_target", "failed")}
                                                   for c, v in summary["fact_notes_compression"].items()},
                                                  ensure_ascii=False))
    if summary.get("presummary_build"):
        pb = summary["presummary_build"]
        print(f"[presummary 구축 비용] ${pb['build_usd']}  페이지 {pb['pages']}/{pb['pages_needed']}  압축률 평균 {pb['ratio_mean']}"
              f"  목표 2배 초과 {pb['over_2x_target']}")
        for c, b in summary["compressors"].items():
            if "presummary" in c:
                a = b["all"]
                print(f"  {c} 총 토큰 절감률: 구축 제외 {a.get('total_token_reduction_pct_without_build')}%"
                      f" / 구축 포함(상한 부담) {a.get('total_token_reduction_pct_with_build')}%"
                      f"  (구축 토큰 {a.get('presummary_build_tokens')})")
    bud = summary["budget"]
    print(f"[예산 확인] 실제 지출 답변 ${bud['answer_usd_actual_total']} (기준 궤적 ${bud['reference_usd_actual']})")
    print(f"  * {REFERENCE_SPEND_NOTE}")
    if summary.get("budget_table"):
        print("[예산별 비교표] " + json.dumps(summary["budget_table"], ensure_ascii=False))
    print(f"저장: {out_dir}")


if __name__ == "__main__":
    main()
