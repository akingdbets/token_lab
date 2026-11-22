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
from cost import compute_cost
from grader import contains_words, is_not_found_answer, word_tokens
from llm import count_message_tokens, count_tokens
from multiturn.history_compressors import get_history_compressor, split_compressor_list
from multiturn.mt_stats import bootstrap_diff, non_inferiority, pair_rows
from multiturn.prompt import load_mt_prompt
from multiturn.scenario import scenario_hash, validate_scenario
from multiturn.trajectory import (
    REASONING_EFFORT_CHOICES, SERVER_DEFAULT, TrajectoryStep, append_step, history_before_turn, load_steps,
    reasoning_effort_for_llm, sampling_record, summarize_steps,
)

REFERENCE_ROOT = CFG.results_dir / "multiturn" / "references"
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class ReplayConfig:
    model: str
    reasoning_effort: str               # REASONING_EFFORT_CHOICES (server_default 포함), 필수
    max_completion_tokens: int          # 필수
    compressors: list[str]
    samples: int = 3
    reference_sample: int = 0
    temperature: str = SERVER_DEFAULT   # server_default 또는 숫자 문자열
    prompt_version: str = "v1"
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
        if "none" not in self.compressors:
            raise ValueError("compressors 에 none(기준선)이 있어야 합니다")
        if not 0 <= self.reference_sample < self.samples:
            raise ValueError("reference_sample 은 0 이상 samples 미만")


def configure_answer_llm(llm, cfg: ReplayConfig):
    """LLM 객체에 실험 설정을 명시적으로 넣는다 (llm.py 는 고치지 않음).
    temperature=server_default 면 처음부터 보내지 않는다 (0 을 보냈는데 서버가 받으면 서버 기본값 조건이 깨진다)."""
    llm.model = cfg.model
    llm.max_tokens = cfg.max_completion_tokens
    llm.reasoning_effort = reasoning_effort_for_llm(cfg.reasoning_effort)
    if cfg.temperature == SERVER_DEFAULT:
        llm.temperature = None
        llm.unsupported.add("temperature")
    else:
        llm.temperature = float(cfg.temperature)
    return llm


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
                 out_dir: Path, reference_root: Path = REFERENCE_ROOT, grade_fn=None, sleep=time.sleep):
        self.cfg, self.scenarios, self.corpus = cfg, scenarios, corpus
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
        self.compressors = {name: get_history_compressor(name) for name in cfg.compressors}
        self._lock = threading.Lock()
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
                if prev is not None and prev.get("response") == step.response_content:
                    grades[sid][str(step.turn)] = prev
                    continue
                g = self.grade(t, step.response_content)
                grades[sid][str(step.turn)] = {"answer_accuracy": g.answer_accuracy, "response": step.response_content}
        for w in warnings:
            print(f"  [경고] {w}", flush=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(grades, ensure_ascii=False, indent=1), encoding="utf-8")
        return refs, grades, warnings

    # ---------------- 2단계: replay ----------------

    @staticmethod
    def trial_key(row: dict) -> tuple:
        return (row["scenario_id"], row["turn"], row["compressor"], row["sample_idx"])

    def run_trial(self, scenario: dict, ref_steps: list[TrajectoryStep], ref_grades: dict, k: int,
                  comp_name: str, sample_idx: int) -> dict:
        t = scenario["turns"][k]
        history = history_before_turn(ref_steps, k, system=self.prompt.system)
        current_user = self.prompt.user_message(t, self.corpus)
        comp = self.compressors[comp_name]
        t0 = time.perf_counter()
        hres = comp.compress_history(history, current_user, None, None)
        compress_sec = time.perf_counter() - t0
        messages = hres.messages
        if messages[0] != history[0] or messages[-1]["content"] != current_user:
            raise AssertionError("압축기가 system 또는 현재 턴 메시지를 바꿨습니다")
        res, hit = with_backoff(lambda: self.answer.chat(messages, sample_idx=sample_idx), self.cfg, self.sleep)
        response = res.text.strip()
        g = self.grade(t, response)
        cost = compute_cost(res).to_dict()
        judge_cost = None
        if g.judge_prompt_tokens or g.judge_completion_tokens:
            from cost import cost_from_fields
            judge_cost = cost_from_fields(self.judge.model, g.judge_prompt_tokens, g.judge_completion_tokens,
                                          usage_source=g.judge_usage_source or "api").to_dict()
        raw_past, comp_past = history[1:], messages[1:-1]
        deps = depends_closure(scenario, k)
        step = TrajectoryStep.from_result(
            res, cache_hit=hit, cost=cost, run_id=self.run_id, scenario_id=scenario["scenario_id"],
            sample_idx=sample_idx, mode="replay", compressor=comp_name, turn=k, user_input=current_user,
            messages_sent=messages, response_content=response,
            sampling=sampling_record(self.answer.llm, res, self.cfg.reasoning_effort),
            history_tokens_raw=_history_tokens(raw_past), history_tokens_compressed=_history_tokens(comp_past),
            compression_info={"config": comp.config(), "llm_prompt_tokens": hres.llm_prompt_tokens,
                              "llm_completion_tokens": hres.llm_completion_tokens, "info": hres.info,
                              "compress_sec": round(compress_sec, 3)})
        row = {
            "run_id": self.run_id, "scenario_id": scenario["scenario_id"], "turn": k, "compressor": comp_name,
            "sample_idx": sample_idx, "turn_type": t["turn_type"], "type": t["type"],
            "depends_on": t["depends_on"], "depends_on_all": deps,
            "depends_distance_min": min((k - d for d in t["depends_on"]), default=None),
            "depends_distance_max": max((k - d for d in t["depends_on"]), default=None),
            "depends_on_reference_ok": all((ref_grades.get(str(d)) or {}).get("answer_accuracy") == 1.0 for d in deps),
            "history_tokens_raw": step.history_tokens_raw, "history_tokens_compressed": step.history_tokens_compressed,
            "input_tokens_est": count_message_tokens(messages),
            "prompt_tokens": res.prompt_tokens, "cached_tokens": res.cached_tokens,
            "cache_write_tokens": res.cache_write_tokens, "reasoning_tokens": res.reasoning_tokens,
            "completion_tokens": res.completion_tokens, "usage_source": res.usage_source,
            "compress_llm_prompt_tokens": hres.llm_prompt_tokens,
            "compress_llm_completion_tokens": hres.llm_completion_tokens,
            "cost": cost, "judge_cost": judge_cost, "cache_hit": hit, "finish_reason": res.finish_reason,
            "response": response, "empty_response": not response, "not_found": is_not_found_answer(response),
            "answer_accuracy": g.answer_accuracy, "satisfied_facts": g.satisfied_count, "total_facts": g.total_count,
            "judge_mode": g.judge_mode, "judge_skipped": g.judge_skipped, "judge_failed": list(g.judge_failed),
            "judge_prompt_tokens": g.judge_prompt_tokens, "judge_completion_tokens": g.judge_completion_tokens,
            "entity_retention": entity_retention_in_history(t["key_entities"], raw_past, comp_past),
            "prompt_hash": step.prompt_hash, "model": res.model,
        }
        self._append("trajectory.jsonl", step.to_dict())
        self._append("turn_trials.jsonl", row)
        return row

    def run(self) -> dict:
        refs, ref_grades, ref_warnings = self.build_references()
        done = {self.trial_key(r) for r in self._read("turn_trials.jsonl")}
        tasks = [(s, k, c, i) for s in self.scenarios for k in range(len(s["turns"]))
                 for c in self.cfg.compressors for i in range(self.cfg.samples)
                 if (s["scenario_id"], k, c, i) not in done]
        print(f"replay: {len(tasks)} trial (이미 끝남 {len(done)})", flush=True)
        failed = 0
        with ThreadPoolExecutor(max_workers=self.cfg.concurrency) as pool:
            futs = {pool.submit(self.run_trial, s, refs[s["scenario_id"]], ref_grades[s["scenario_id"]], k, c, i):
                    (s["scenario_id"], k, c, i) for s, k, c, i in tasks}
            for f in as_completed(futs):
                try:
                    f.result()
                except Exception as e:      # 한 trial 이 실패해도 나머지는 돈다. 이어 돌리기로 다시 시도된다
                    failed += 1
                    self._append("errors.jsonl", {"key": list(futs[f]), "error": f"{type(e).__name__}: {e}"[:500],
                                                  "time": datetime.now().isoformat(timespec="seconds")})
        summary = summarize_replay(self._read("turn_trials.jsonl"), self.cfg, ref_warnings=ref_warnings,
                                   n_scenarios=len(self.scenarios))
        summary["failed_trials_this_run"] = failed
        summary["config"] = self.config_record()
        steps = [TrajectoryStep.from_dict(d) for d in self._read("trajectory.jsonl")]
        summary["trajectory"] = summarize_steps(steps)
        (self.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        return summary

    def config_record(self) -> dict:
        return {
            "replay": asdict(self.cfg),
            "answer_sampling": self.answer.llm.sampling_info(),
            "answer_backend": {"backend": self.answer.llm.backend, "base_url": self.answer.llm.base_url},
            "judge": {"model": self.judge.model, "mode": self.cfg.judge_mode},
            "prompt": {"version": self.prompt.version, "sha256": self.prompt.sha256},
            "scenarios": {s["scenario_id"]: {"hash": scenario_hash(s), "status": s["status"], "turns": len(s["turns"])}
                          for s in self.scenarios},
            "compressor_configs": {n: c.config() for n, c in self.compressors.items()},
            "tokenizer": CFG.tokenizer,
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
    return sum(((r.get("cost") or {}).get("usd") or 0) for r in rows)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _pct_reduction(base: float, comp: float):
    return round(100 * (1 - comp / base), 2) if base else None


def compare_block(pairs: list[tuple[dict, dict]], cfg: ReplayConfig, n_scenarios: int) -> dict:
    """짝지은 (none, 압축) trial 들의 절감률·정확도·비열등 판정."""
    if not pairs:
        return {"n_pairs": 0}
    bs = [b for b, _ in pairs]
    cs = [c for _, c in pairs]
    base_total = _sum(bs, "prompt_tokens") + _sum(bs, "completion_tokens")
    comp_total = (_sum(cs, "prompt_tokens") + _sum(cs, "completion_tokens")
                  + _sum(cs, "compress_llm_prompt_tokens") + _sum(cs, "compress_llm_completion_tokens"))
    turn = bootstrap_diff(pairs, unit="turn", boot=cfg.boot, seed=cfg.seed)
    cluster = bootstrap_diff(pairs, unit="scenario", boot=cfg.boot, seed=cfg.seed)
    return {
        "n_pairs": len(pairs),
        "history_reduction_pct": _pct_reduction(_sum(bs, "history_tokens_raw"), _sum(cs, "history_tokens_compressed")),
        "input_reduction_pct": _pct_reduction(_sum(bs, "prompt_tokens"), _sum(cs, "prompt_tokens")),
        "total_token_reduction_pct": _pct_reduction(base_total, comp_total),
        "cost_reduction_pct": _pct_reduction(_usd(bs), _usd(cs)),   # 캐시 읽기·쓰기 반영 (cost.py)
        "cost_usd": {"none": round(_usd(bs), 6), "compressed": round(_usd(cs), 6)},
        "reasoning_tokens": {"none_mean": _mean(r.get("reasoning_tokens") for r in bs),
                             "compressed_mean": _mean(r.get("reasoning_tokens") for r in cs)},
        "completion_tokens": {"none_mean": _mean(r.get("completion_tokens") for r in bs),
                              "compressed_mean": _mean(r.get("completion_tokens") for r in cs)},
        "accuracy": {"none": _mean(r["answer_accuracy"] for r in bs),
                     "compressed": _mean(r["answer_accuracy"] for r in cs)},
        "retention_pct": turn.get("retention_pct"),
        "not_found_rate": {"none": _rate(bs, lambda r: r.get("not_found")),
                           "compressed": _rate(cs, lambda r: r.get("not_found"))},
        "entity_retention_mean": _mean(r.get("entity_retention") for r in cs),
        "paired_bootstrap_turn": turn,                                      # 주 판정
        "non_inferiority": non_inferiority(turn, cfg.margin),
        "cluster_bootstrap_scenario": cluster,                              # 보조
        "non_inferiority_cluster": non_inferiority(cluster, cfg.margin),
    }


def summarize_replay(rows: list[dict], cfg: ReplayConfig, ref_warnings: list[str] | None = None,
                     n_scenarios: int | None = None) -> dict:
    n_scen = n_scenarios or len({r["scenario_id"] for r in rows})
    subsets = {"all": lambda r: True, "depends_on_reference_ok": lambda r: r["depends_on_reference_ok"]}
    out: dict = {
        "notes": [
            "주 판정은 (시나리오, 턴) 단위 쌍체 부트스트랩이다. sample 은 같은 턴 안에서 평균한다.",
            f"시나리오 군집 부트스트랩은 보조 결과다. 시나리오 {n_scen}개로 재추출하므로 구간이 넓고 불안정하다"
            + (" (파일럿 규모)." if n_scen < 10 else "."),
            "none 의 reference sample 은 기준 궤적과 같은 요청이라 응답 캐시에 적중한다. 실제 지출은 trajectory.cost_usd_actual.",
            "depends_on_reference_ok=False 인 턴은 기준 궤적의 앞 턴 답변이 틀려 압축과 무관하게 틀릴 수 있다.",
        ],
        "reference_health": {"warnings": ref_warnings or [], "n_warnings": len(ref_warnings or [])},
        "n_trials": len(rows),
        "answer_health": {c: answer_health([r for r in rows if r["compressor"] == c]) for c in cfg.compressors},
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
            block[f"{name}_by_turn_type"] = {
                tt: compare_block([p for p in pairs if p[1]["turn_type"] == tt], cfg, n_scen)
                for tt in sorted({p[1]["turn_type"] for p in pairs})}
        block["by_turn"] = {str(k): compare_block([p for p in pair_rows(rows, comp) if p[1]["turn"] == k], cfg, n_scen)
                            for k in sorted({r["turn"] for r in rows})}
        out["compressors"][comp] = block
    return out


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
    ap.add_argument("--prompt", default="v1", help="src/prompts/mt_answer_<version>.md")
    ap.add_argument("--judge-mode", default=CFG.judge_mode)
    ap.add_argument("--resume", metavar="RUN_ID", help="results/runs/mt_<RUN_ID> 를 이어서")
    ap.add_argument("--estimate-only", action="store_true", help="API 를 부르지 않고 예상 비용만 계산")
    ap.add_argument("--assume-answer-tokens", type=int, default=300, help="(--estimate-only) 기준 궤적이 없을 때 답변 길이")
    ap.add_argument("--assume-reasoning-tokens", type=int, default=1000, help="(--estimate-only) 호출당 추론 토큰")
    ap.add_argument("--judge-model", default=CFG.judge_model, help="(--estimate-only) 채점 단가를 찾을 모델 이름")
    ap.add_argument("--judge-in-per-call", type=int, default=261, help="(--estimate-only) judge 호출당 입력 토큰")
    ap.add_argument("--judge-out-per-call", type=int, default=101, help="(--estimate-only) judge 호출당 출력 토큰")
    return ap


def config_from_args(a) -> ReplayConfig:
    return ReplayConfig(model=a.model, reasoning_effort=a.reasoning_effort,
                        max_completion_tokens=a.max_completion_tokens,
                        compressors=split_compressor_list(a.compressors), samples=a.samples,
                        reference_sample=a.reference_sample, temperature=a.temperature, prompt_version=a.prompt,
                        judge_mode=a.judge_mode, concurrency=a.concurrency, margin=a.margin, boot=a.boot)


def main(argv=None):
    a = build_parser().parse_args(argv)
    cfg = config_from_args(a)
    from corpus import load_corpus
    from multiturn.scenario import load_scenarios
    scenarios = load_scenarios(a.scenarios)
    corpus = load_corpus()
    if a.estimate_only:
        from multiturn.estimate import estimate, print_estimate
        print_estimate(estimate(cfg, scenarios, corpus, answer_tokens=a.assume_answer_tokens,
                                reasoning_tokens=a.assume_reasoning_tokens, judge_model=a.judge_model,
                                judge_in=a.judge_in_per_call, judge_out=a.judge_out_per_call))
        return
    from llm import LLM
    from multiturn.response_cache import CachedLLM
    answer = CachedLLM(configure_answer_llm(LLM(role="answer"), cfg))
    judge = CachedLLM(LLM(role="judge"))
    run_id = a.resume or datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = CFG.results_dir / "runs" / f"mt_{run_id}"
    try:
        summary = Replay(cfg, scenarios, corpus, answer, judge, out_dir).run()
    finally:
        answer.close()
        judge.close()
    print(json.dumps({c: {k: b["all"].get(k) for k in ("input_reduction_pct", "total_token_reduction_pct",
                                                       "cost_reduction_pct", "retention_pct", "non_inferiority")}
                      for c, b in summary["compressors"].items()}, ensure_ascii=False, indent=1))
    print(f"저장: {out_dir}")


if __name__ == "__main__":
    main()
