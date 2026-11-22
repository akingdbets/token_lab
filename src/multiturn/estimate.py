"""
replay 실행 행렬의 오프라인 비용 추정 (replay.py --estimate-only). API 를 부르지 않는다.

    입력 토큰   실제 시나리오 문서를 실제 압축기로 압축해 config.tokenizer 로 센다 (count_message_tokens).
                기준 궤적이 없으니 과거 답변은 answer_tokens 길이의 자리표시 문자열로 둔다.
    출력 토큰   호출마다 answer_tokens + reasoning_tokens (가정값)
    채점        trial 마다 judge 호출 수(per_fact 면 key_fact 수, batch 면 1) × 호출당 입력·출력 가정값

호출 행렬 (replay.py 와 같은 순서)
    기준 궤적   시나리오 × 턴 (none, reference sample)
    replay     시나리오 × 턴 × 압축기 × sample. none 의 reference sample 은 기준 궤적과 같은 요청이라
               응답 캐시에 적중해 실제로는 보내지 않는다 (actual 에서 빠지고 experimental 에는 들어감)

캐시 비용 세 가지
    no_cache          적중 0% (상한). 입력 전부 input 단가
    prefix_cache      이전 요청과 앞쪽 메시지가 같은 가장 긴 접두부를 캐시 읽기로 본다 (1,024 토큰 이상일 때만,
                      OpenAI 프롬프트 캐시 최소 길이). 같은 요청을 sample 마다 다시 보내는 경우, none 처럼 기록이 앞에서부터
                      그대로 자라는 경우, window 의 앞쪽 턴처럼 아직 잘리지 않은 경우가 여기서 잡힌다.
                      나머지는 input 단가
    prefix_cache_write  prefix_cache 에서 캐시되지 않은 입력을 cache_write 단가로 계산 (캐시 쓰기가 따로 과금될 때의 상한)
    보존 시간(30분 등) 안에 모든 요청이 이어서 간다고 가정한다. 128 토큰 단위 절삭은 무시한다.
"""

from __future__ import annotations

from collections import defaultdict

from cost import find_price, load_pricing
from llm import count_message_tokens, count_tokens
from multiturn.history_compressors import get_history_compressor
from multiturn.prompt import load_mt_prompt

CACHE_MIN_TOKENS = 1024
M = 1_000_000


def placeholder_answer(n_tokens: int) -> str:
    """대략 n_tokens 토큰짜리 자리표시 답변."""
    return " ".join(["answer"] * max(n_tokens, 0))


class PrefixCache:
    """메시지 단위 접두부 캐시 시뮬레이션."""

    def __init__(self):
        self.seen: set[tuple] = set()

    def cached_tokens(self, messages: list[dict]) -> int:
        keys = [tuple((m["role"], m["content"]) for m in messages[:i]) for i in range(1, len(messages) + 1)]
        best = 0
        for i in range(len(keys), 0, -1):
            if keys[i - 1] in self.seen:
                best = count_message_tokens(messages[:i], add_generation_prompt=False)
                break
        self.seen.update(keys)
        return best if best >= CACHE_MIN_TOKENS else 0


def _fallbacks(info) -> dict:
    """HistoryResult.info (체인이면 단계별로 중첩) 에서 fallback_* 상태를 모은다."""
    found = {}
    if isinstance(info, dict):
        for k, v in info.items():
            if k == "single_status" and isinstance(v, dict):
                found.update({s: n for s, n in v.items() if str(s).startswith("fallback")})
            elif isinstance(v, dict):
                found.update(_fallbacks(v))
    return found


def _price(model: str, pricing: dict) -> dict | None:
    return find_price(model, pricing)[1]


def estimate(cfg, scenarios: list[dict], corpus, answer_tokens: int = 300, reasoning_tokens: int = 1000,
             judge_model: str = "deepseek-flash", judge_in: int = 261, judge_out: int = 101,
             pricing: dict | None = None) -> dict:
    pricing = load_pricing() if pricing is None else pricing
    prompt = load_mt_prompt(cfg.prompt_version)
    ap = _price(cfg.model, pricing)
    jp = _price(judge_model, pricing)
    out_tokens = answer_tokens + reasoning_tokens
    comps, comp_errors = {}, {}
    for name in cfg.compressors:
        try:
            comps[name] = get_history_compressor(name)
        except (ImportError, KeyError, ValueError) as e:
            comp_errors[name] = f"{type(e).__name__}: {e}"
    cache = PrefixCache()

    def add(acc, messages, actual: bool):
        n_in = count_message_tokens(messages)
        hit = cache.cached_tokens(messages)
        acc["requests"] += 1
        acc["input_tokens"] += n_in
        acc["cached_tokens"] += hit
        acc["output_tokens"] += out_tokens
        if actual:
            acc["actual_requests"] += 1
            acc["actual_input_tokens"] += n_in
            acc["actual_cached_tokens"] += hit
        return n_in

    def new_acc():
        return defaultdict(int)

    per_comp = {name: new_acc() for name in comps}
    reference = new_acc()
    judge_calls = defaultdict(int)
    history_raw = defaultdict(int)
    history_comp = defaultdict(int)

    histories = {}
    for s in scenarios:
        h = [{"role": "system", "content": prompt.system}]
        hs = []
        for t in s["turns"]:
            user = prompt.user_message(t, corpus)
            hs.append((list(h), user))
            add(reference, h + [{"role": "user", "content": user}], actual=True)
            h = h + [{"role": "user", "content": user}, {"role": "assistant", "content": placeholder_answer(answer_tokens)}]
        histories[s["scenario_id"]] = hs

    for s in scenarios:
        for k, t in enumerate(s["turns"]):
            history, user = histories[s["scenario_id"]][k]
            n_judge = len(t["key_facts"]) if cfg.judge_mode == "per_fact" else 1
            for name, comp in comps.items():
                try:
                    res = comp.compress_history(history, user)
                except ImportError as e:
                    comp_errors[name] = f"{type(e).__name__}: {e}"
                    continue
                fb = _fallbacks(res.info)
                if fb:      # 압축기가 원문을 그대로 돌려줌 (예: llmlingua 미설치). 압축 효과가 없는 값이라 뺀다
                    comp_errors[name] = f"압축 실패로 원문 반환: {fb}"
                    continue
                for i in range(cfg.samples):
                    actual = not (name == "none" and i == cfg.reference_sample)
                    add(per_comp[name], res.messages, actual=actual)
                    judge_calls[name] += n_judge
                history_raw[name] += sum(count_tokens(m["content"]) for m in history[1:]) * cfg.samples
                history_comp[name] += sum(count_tokens(m["content"]) for m in res.messages[1:-1]) * cfg.samples
    for name in list(per_comp):
        if name in comp_errors:
            per_comp.pop(name)

    def usd(acc, prefix="") -> dict:
        if ap is None:
            return {"no_cache": None, "prefix_cache": None, "prefix_cache_write": None}
        n_in, hit = acc[f"{prefix}input_tokens"], acc[f"{prefix}cached_tokens"]
        n_out = (acc["actual_requests"] if prefix else acc["requests"]) * out_tokens
        out_usd = n_out * ap["output"] / M
        write_price = ap.get("cache_write") if ap.get("cache_write") is not None else ap["input"]
        return {
            "no_cache": round(n_in * ap["input"] / M + out_usd, 4),
            "prefix_cache": round((n_in - hit) * ap["input"] / M + hit * (ap.get("cache_read") or ap["input"]) / M + out_usd, 4),
            "prefix_cache_write": round((n_in - hit) * write_price / M + hit * (ap.get("cache_read") or ap["input"]) / M + out_usd, 4),
        }

    rows = {}
    for name, acc in per_comp.items():
        rows[name] = {
            "requests": acc["requests"], "actual_requests": acc["actual_requests"],
            "input_tokens": acc["input_tokens"], "cached_tokens_prefix_sim": acc["cached_tokens"],
            "history_reduction_pct": round(100 * (1 - history_comp[name] / history_raw[name]), 2) if history_raw[name] else None,
            "input_reduction_pct_vs_none": None,
            "answer_usd_experimental": usd(acc), "answer_usd_actual": usd(acc, "actual_"),
            "judge_calls": judge_calls[name],
            "judge_usd": round(judge_calls[name] * (judge_in * jp["input"] + judge_out * jp["output"]) / M, 4) if jp else None,
        }
    if "none" in rows:
        base = rows["none"]["input_tokens"]
        for name, r in rows.items():
            r["input_reduction_pct_vs_none"] = round(100 * (1 - r["input_tokens"] / base), 2) if base else None
    ref = {"requests": reference["requests"], "input_tokens": reference["input_tokens"],
           "answer_usd": usd(reference)}
    ref_judge = sum((len(t["key_facts"]) if cfg.judge_mode == "per_fact" else 1) for s in scenarios for t in s["turns"])
    total = {}
    for variant in ("no_cache", "prefix_cache", "prefix_cache_write"):
        vals = [r["answer_usd_actual"][variant] for r in rows.values()] + [ref["answer_usd"][variant]]
        total[variant] = round(sum(v for v in vals if v is not None), 4) if ap else None
    judge_total = (round(sum(r["judge_usd"] or 0 for r in rows.values()), 4) if jp else None)
    return {
        "assumptions": {"model": cfg.model, "answer_tokens": answer_tokens, "reasoning_tokens": reasoning_tokens,
                        "judge_model": judge_model, "judge_mode": cfg.judge_mode, "judge_in_per_call": judge_in,
                        "judge_out_per_call": judge_out, "samples": cfg.samples, "compressors": cfg.compressors,
                        "scenarios": len(scenarios), "turns": sum(len(s["turns"]) for s in scenarios),
                        "pricing_found": {"answer": ap is not None, "judge": jp is not None},
                        "note_reference_judge": f"기준 궤적 채점 {ref_judge}회는 none reference sample 채점과 같은 요청이라 judge 캐시로 한 번만 센다"},
        "reference": ref,
        "compressors": rows,
        "compressor_errors": comp_errors,
        "total_answer_usd_actual": total,
        "total_judge_usd": judge_total,
    }


def print_estimate(est: dict) -> None:
    a = est["assumptions"]
    print(f"\n예상 비용 (API 호출 없음) model={a['model']}  시나리오 {a['scenarios']}개 / 턴 {a['turns']}개  "
          f"sample {a['samples']}  답변 {a['answer_tokens']} + 추론 {a['reasoning_tokens']} 토큰 가정")
    if not a["pricing_found"]["answer"]:
        print("  [경고] 답변 모델 단가가 data/pricing.json 에 없습니다")
    r = est["reference"]
    print(f"\n기준 궤적: 요청 {r['requests']}  입력 {r['input_tokens']:,} 토큰  비용 {r['answer_usd']}")
    print(f"\n{'압축기':<26}{'요청(실제)':>12}{'입력 토큰':>12}{'입력 절감':>9}{'기록 절감':>9}"
          f"{'캐시0%':>10}{'접두캐시':>10}{'+쓰기':>10}{'채점':>9}")
    for name, x in est["compressors"].items():
        u = x["answer_usd_actual"]
        print(f"{name:<26}{x['requests']:>6}({x['actual_requests']:>3}){x['input_tokens']:>12,}"
              f"{x['input_reduction_pct_vs_none'] or 0:>8.1f}%{x['history_reduction_pct'] or 0:>8.1f}%"
              f"{u['no_cache'] or 0:>10.4f}{u['prefix_cache'] or 0:>10.4f}{u['prefix_cache_write'] or 0:>10.4f}"
              f"{x['judge_usd'] or 0:>9.4f}")
    for name, e in est["compressor_errors"].items():
        print(f"  [제외] {name}: {e}")
    t = est["total_answer_usd_actual"]
    print(f"\n합계 (실제 지출 예상, 기준 궤적 포함) 답변: 캐시0% ${t['no_cache']}  접두캐시 ${t['prefix_cache']}  "
          f"쓰기과금 ${t['prefix_cache_write']}   채점 ${est['total_judge_usd']}")
