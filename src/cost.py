"""
API 호출 비용 계산 (USD)

단가는 data/pricing.json (USD / 1M 토큰). 입력 / 캐시 읽기 / 캐시 쓰기 / 출력 네 가지.

계산 (prompt_tokens 는 캐시 읽기·쓰기 토큰을 포함한 전체 입력, completion_tokens 는 추론 토큰을 포함한 전체 출력)
    입력 = (prompt - cached - cache_write) * input + cached * cache_read + cache_write * cache_write 단가
    출력 = completion * output          # 추론 토큰을 따로 더하지 않는다 (이중 계산 방지)

cost_source (계산 근거)
    api                  서버 usage 의 캐시 정보까지 반영
    no_cache_info        cached_tokens 가 None -> 캐시 할인 없이 입력 전부를 input 단가로
    no_cache_write_info  캐시 읽기는 반영했지만, 캐시 쓰기 단가가 있는 모델인데 cache_write_tokens 가 None
                         -> 쓰기 토큰도 input 단가로 계산 (실제보다 낮게 나올 수 있음)
    estimate             서버가 usage 를 주지 않아 토크나이저 추정치로 계산 (캐시 할인 없음)
    no_pricing           단가표에 모델이 없거나 필요한 단가가 null -> usd None

사용 예
    from cost import compute_cost
    c = compute_cost(res)            # res: llm.LLMResult
    print(c.usd, c.cost_source)

    recompute_costs("results/multiturn/<run>/trajectory.jsonl")   # 단가를 바꾼 뒤 저장된 궤적 다시 계산
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from config import ROOT

PRICING_PATH = ROOT / "data" / "pricing.json"
PER_TOKENS = 1_000_000


@dataclass
class CostBreakdown:
    usd: float | None                 # 합계. 계산할 수 없으면 None
    input_usd: float | None = None    # 캐시 안 된 입력
    cache_read_usd: float | None = None
    cache_write_usd: float | None = None
    output_usd: float | None = None   # 추론 포함 출력
    cost_source: str = "api"          # 위 docstring 참고
    pricing_model: str | None = None  # 단가표에서 고른 키

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["models"]


def load_pricing(path: str | Path | None = None) -> dict:
    return _load(str(path or PRICING_PATH))


def find_price(model: str, pricing: dict) -> tuple[str | None, dict | None]:
    """정확히 일치하는 키, 없으면 가장 긴 접두사 키."""
    if model in pricing:
        return model, pricing[model]
    keys = [k for k in pricing if not k.startswith("_") and model.startswith(k)]
    if not keys:
        return None, None
    k = max(keys, key=len)
    return k, pricing[k]


def cost_from_fields(model: str, prompt_tokens: int, completion_tokens: int,
                     cached_tokens: int | None = None, cache_write_tokens: int | None = None,
                     usage_source: str = "api", pricing: dict | None = None) -> CostBreakdown:
    """토큰 수 -> 비용. LLMResult 없이 저장된 기록에서도 쓸 수 있게 필드만 받는다."""
    pricing = load_pricing() if pricing is None else pricing
    key, p = find_price(model, pricing)
    if p is None or p.get("input") is None or p.get("output") is None:
        return CostBreakdown(usd=None, cost_source="no_pricing", pricing_model=key)

    if usage_source != "api":
        source, cached, written = "estimate", 0, 0
    elif cached_tokens is None:
        source, cached, written = "no_cache_info", 0, 0
    else:
        cached = cached_tokens
        if p.get("cache_write") is not None and cache_write_tokens is None:
            source, written = "no_cache_write_info", 0
        else:
            source, written = "api", cache_write_tokens or 0
        if cached and p.get("cache_read") is None:
            return CostBreakdown(usd=None, cost_source="no_pricing", pricing_model=key)
        if written and p.get("cache_write") is None:
            # 단가표에 쓰기 단가가 없는 모델(예: DeepSeek)은 쓰기 토큰을 일반 입력으로 본다
            written = 0

    uncached = max(prompt_tokens - cached - written, 0)
    input_usd = uncached * p["input"] / PER_TOKENS
    cache_read_usd = cached * (p.get("cache_read") or 0) / PER_TOKENS
    cache_write_usd = written * (p.get("cache_write") or 0) / PER_TOKENS
    output_usd = completion_tokens * p["output"] / PER_TOKENS
    return CostBreakdown(
        usd=input_usd + cache_read_usd + cache_write_usd + output_usd,
        input_usd=input_usd, cache_read_usd=cache_read_usd, cache_write_usd=cache_write_usd,
        output_usd=output_usd, cost_source=source, pricing_model=key,
    )


def compute_cost(res, pricing: dict | None = None) -> CostBreakdown:
    """llm.LLMResult 하나의 비용."""
    return cost_from_fields(
        model=res.model, prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens,
        cached_tokens=res.cached_tokens, cache_write_tokens=res.cache_write_tokens,
        usage_source=res.usage_source, pricing=pricing,
    )


def recompute_costs(path: str | Path, out: str | Path | None = None,
                    pricing: dict | None = None) -> int:
    """저장된 JSONL(multiturn 궤적 형식: model, prompt_tokens, completion_tokens, cached_tokens,
    cache_write_tokens, usage_source 필드)의 "cost" 를 현재 단가로 다시 계산한다.
    out 을 주지 않으면 같은 파일을 바꿔 쓴다 (임시 파일에 쓴 뒤 교체). 다시 계산한 줄 수를 돌려준다."""
    path = Path(path)
    pricing = load_pricing() if pricing is None else pricing
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    for r in rows:
        r["cost"] = cost_from_fields(
            model=r.get("model") or "", prompt_tokens=r.get("prompt_tokens") or 0,
            completion_tokens=r.get("completion_tokens") or 0,
            cached_tokens=r.get("cached_tokens"), cache_write_tokens=r.get("cache_write_tokens"),
            usage_source=r.get("usage_source") or "api", pricing=pricing,
        ).to_dict()
    target = Path(out) if out else path
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, target)
    return len(rows)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="저장된 궤적 JSONL 의 비용을 현재 단가로 다시 계산")
    ap.add_argument("path")
    ap.add_argument("--out", help="새 파일로 저장 (기본: 같은 파일을 바꿔 씀)")
    a = ap.parse_args()
    print(f"{recompute_costs(a.path, a.out)} 줄 다시 계산")
