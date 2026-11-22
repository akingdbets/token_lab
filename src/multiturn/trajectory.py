"""
멀티턴 / 멀티에이전트 실행 궤적 (JSONL, LLM 호출 1번 = 1줄)

규칙: 대화 기록에는 최종 답변(content)만 넣는다
    다음 턴에 보낼 대화 기록(history)에는 각 턴 assistant 의 최종 답변 response_content 만 넣는다.
    추론 원문(response_reasoning)은 기록에 넣지 않고 이 궤적 파일에 따로 저장만 한다.
    history_before_turn() 이 이 규칙대로 기록을 재구성한다.

필드 (TrajectoryStep)
    식별     run_id, scenario_id, sample_idx(반복 번호), mode("replay" | "free_run"), compressor,
             turn, agent(멀티턴은 "assistant" 고정), step_in_turn
    입력     user_input     그 턴 사용자 발화 원문 (기록 재구성용. messages_sent 는 압축됐을 수 있다)
             messages_sent  실제로 보낸 메시지 전체
             prompt_hash    messages_sent 의 sha256 (prompt_hash())
    출력     response_content, response_reasoning (추론 원문이 오면 저장, 없으면 None)
    토큰     LLMResult 의 토큰 필드 전부 (prompt_tokens, completion_tokens, cached_tokens,
             cache_write_tokens, reasoning_tokens, raw_usage, usage_source, est_prompt_tokens,
             finish_reason, model, latency, ttft, created_at)
    비용     cost (cost.CostBreakdown.to_dict()). cache_hit 이면 원래 호출 비용 그대로 = 실험상 비용
    샘플링   sampling = {reasoning_effort_requested, reasoning_effort_sent, temperature_requested,
                         temperature_sent, seed, max_tokens, reasoning_tokens}  (sampling_record())
    압축     history_tokens_raw / history_tokens_compressed (압축 전후 대화 기록 토큰),
             compression_info (압축기 config, 압축에 쓴 LLM 토큰)
    기타     cache_hit (응답 캐시 적중 여부), timestamp (기록 시각, UTC)

reasoning_effort 는 실행 설정에 명시적으로 받는다 (REASONING_EFFORT_CHOICES).
    "server_default" = 보내지 않음 (서버 기본값). 빈 값·None 은 받지 않는다 (암묵적 기본값 금지).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

MODES = ("replay", "free_run")
SERVER_DEFAULT = "server_default"
REASONING_EFFORT_CHOICES = (SERVER_DEFAULT, "none", "minimal", "low", "medium", "high", "xhigh")

# LLMResult 에서 그대로 옮기는 필드
RESULT_FIELDS = ("model", "prompt_tokens", "completion_tokens", "cached_tokens", "cache_write_tokens",
                 "reasoning_tokens", "raw_usage", "usage_source", "est_prompt_tokens", "finish_reason",
                 "latency", "ttft", "created_at")


def reasoning_effort_for_llm(setting: str) -> str:
    """실행 설정값 -> LLM.reasoning_effort 에 넣을 값. server_default 는 "" (보내지 않음)."""
    if setting not in REASONING_EFFORT_CHOICES:
        raise ValueError(f"reasoning_effort 는 명시해야 합니다: {REASONING_EFFORT_CHOICES} 중 하나 (받은 값 {setting!r})")
    return "" if setting == SERVER_DEFAULT else setting


def sampling_record(llm, res, reasoning_effort_setting: str) -> dict:
    """요청값, 실제 전송값, 응답의 reasoning_tokens 를 함께 남긴다."""
    s = llm.sampling_info()
    return {
        "reasoning_effort_requested": reasoning_effort_setting,
        "reasoning_effort_sent": s["reasoning_effort"],          # None = 보내지 않음
        "temperature_requested": s["temperature_requested"],
        "temperature_sent": s["temperature"],
        "seed": s["seed"],
        "max_tokens": s["max_tokens"],
        "max_tokens_param": s["max_tokens_param"],
        "reasoning_tokens": res.reasoning_tokens,
    }


def prompt_hash(messages: list[dict]) -> str:
    blob = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class TrajectoryStep:
    run_id: str
    scenario_id: str
    sample_idx: int
    mode: str
    compressor: str
    turn: int
    user_input: str
    messages_sent: list[dict]
    response_content: str
    agent: str = "assistant"
    step_in_turn: int = 0
    response_reasoning: str | None = None
    # LLMResult 토큰 필드
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None
    raw_usage: dict | None = None
    usage_source: str = "api"
    est_prompt_tokens: int = 0
    finish_reason: str | None = None
    latency: float | None = None
    ttft: float | None = None
    created_at: str | None = None
    cost: dict | None = None
    sampling: dict = field(default_factory=dict)
    # 압축
    history_tokens_raw: int | None = None
    history_tokens_compressed: int | None = None
    compression_info: dict = field(default_factory=dict)
    # 기타
    prompt_hash: str = ""
    cache_hit: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"mode 는 {MODES} 중 하나: {self.mode!r}")
        if not self.prompt_hash:
            self.prompt_hash = prompt_hash(self.messages_sent)

    @classmethod
    def from_result(cls, res, cache_hit: bool = False, cost: dict | None = None, **kw) -> "TrajectoryStep":
        """LLMResult 에서 토큰 필드를 옮겨 만든다. response_content 는 res.text, 추론은 res.reasoning_text."""
        kw.setdefault("response_content", res.text)
        kw.setdefault("response_reasoning", res.reasoning_text)
        return cls(cache_hit=cache_hit, cost=cost, **{k: getattr(res, k) for k in RESULT_FIELDS}, **kw)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrajectoryStep":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def append_step(path: str | Path, step: TrajectoryStep) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(step.to_dict(), ensure_ascii=False) + "\n")


def load_steps(path: str | Path, **filters) -> list[TrajectoryStep]:
    """궤적을 읽어 (run_id, scenario_id, sample_idx, turn, step_in_turn) 순으로 돌려준다.
    filters: 필드 이름=값 (예: scenario_id="s01", sample_idx=0)."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            s = TrajectoryStep.from_dict(json.loads(line))
            if all(getattr(s, k) == v for k, v in filters.items()):
                out.append(s)
    out.sort(key=lambda s: (s.run_id, s.scenario_id, s.sample_idx, s.turn, s.step_in_turn))
    return out


def history_before_turn(steps: list[TrajectoryStep], k: int, system: str | None = None) -> list[dict]:
    """저장된 궤적(한 시나리오·한 sample_idx)에서 턴 k 직전까지의 압축 전 대화 기록을 재구성한다.

    [system] + 턴 0..k-1 마다 {user: user_input}, {assistant: 그 턴 마지막 assistant 단계의 response_content}.
    추론(response_reasoning)은 넣지 않는다 (모듈 docstring 규칙).
    system 을 주지 않으면 첫 단계 messages_sent 의 system 메시지를 쓴다 (없으면 넣지 않음).
    """
    keys = {(s.run_id, s.scenario_id, s.sample_idx) for s in steps}
    if len(keys) > 1:
        raise ValueError(f"한 시나리오·한 sample_idx 의 궤적만 넣어야 합니다: {sorted(keys)}")
    steps = sorted(steps, key=lambda s: (s.turn, s.step_in_turn))
    if system is None and steps:
        system = next((m["content"] for m in steps[0].messages_sent if m["role"] == "system"), None)
    history = [{"role": "system", "content": system}] if system else []
    by_turn: dict[int, list[TrajectoryStep]] = {}
    for s in steps:
        if s.turn < k:
            by_turn.setdefault(s.turn, []).append(s)
    for t in sorted(by_turn):
        missing = set(range(t)) - set(by_turn)
        if missing:
            raise ValueError(f"턴 {sorted(missing)} 기록이 없습니다")
        group = by_turn[t]
        final = [s for s in group if s.agent == "assistant"][-1:] or group[-1:]
        history.append({"role": "user", "content": group[0].user_input})
        history.append({"role": "assistant", "content": final[0].response_content})
    return history


def summarize_steps(steps: list[TrajectoryStep]) -> dict:
    """실행 요약.
    - 추론이 실제로 돌았는지: 서버 기본값은 제공사가 예고 없이 바꿀 수 있어 reasoning_tokens > 0 을 센다.
    - 추론 토큰이 출력 한도를 다 쓴 경우: finish_reason="length" 와 빈 답변 비율.
    - 실제 지출(cache_hit 아님)과 실험상 비용(전체)을 나눈다."""
    n = len(steps)

    def usd(xs):
        vals = [s.cost.get("usd") for s in xs if s.cost]
        return round(sum(v for v in vals if v is not None), 6) if vals else 0.0

    live = [s for s in steps if not s.cache_hit]
    return {
        "calls": n,
        "cache_hits": n - len(live),
        "reasoning_ran": sum(1 for s in steps if (s.reasoning_tokens or 0) > 0),
        "reasoning_zero": sum(1 for s in steps if s.reasoning_tokens == 0),
        "reasoning_unknown": sum(1 for s in steps if s.reasoning_tokens is None),
        "finish_length": sum(1 for s in steps if s.finish_reason == "length"),
        "finish_length_rate": round(sum(s.finish_reason == "length" for s in steps) / n, 4) if n else None,
        "empty_response": sum(1 for s in steps if not (s.response_content or "").strip()),
        "empty_response_rate": round(sum(not (s.response_content or "").strip() for s in steps) / n, 4) if n else None,
        "prompt_tokens": sum(s.prompt_tokens for s in steps),
        "completion_tokens": sum(s.completion_tokens for s in steps),
        "cost_usd_experimental": usd(steps),      # 캐시 적중도 원래 호출 비용으로 센 값
        "cost_usd_actual": usd(live),             # 이번 실행에서 실제로 지출한 값
        "cost_sources": sorted({s.cost.get("cost_source") for s in steps if s.cost}),
    }
