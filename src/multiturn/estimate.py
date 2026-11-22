"""
replay 실행 행렬의 오프라인 비용 추정 (replay.py --estimate-only). API 를 부르지 않는다.

    입력 토큰   실제 시나리오 문서를 실제 압축기로 압축해 config.tokenizer(TOKENIZER) 로 센다 (count_message_tokens).
                답변 모델 토크나이저와 다르면 근사치다 (출력 맨 위에 사용한 토크나이저를 표시한다).
                기준 궤적이 없으니 과거 답변은 answer_tokens 길이의 자리표시 문자열로 둔다.
    출력 토큰   호출마다 answer_tokens + reasoning_tokens (가정값)
    채점        trial 마다 judge 호출 수(per_fact 면 key_fact 수, batch 면 1) × 호출당 입력·출력 가정값

호출 행렬 (replay.py 와 같은 순서)
    기준 궤적   시나리오 × 턴 (none, reference sample)
    replay     시나리오 × 턴 × 압축기 × sample

비용 기준 두 가지
    실험상 비용 (호출당)  압축기 비교(비용 절감률)의 기준. 응답 캐시 적중과 무관하게 모든 trial 을 "한 번 호출한 값"으로 센다.
                         none 의 reference sample 은 기준 궤적 호출과 같은 요청이므로 그 호출의 값을 쓴다.
    실제 지출 (예산 확인용)  실제로 보내는 요청만. none 의 reference sample 은 기준 궤적과 같은 요청이라 응답 캐시에
                         적중해 보내지 않으므로 0원이다 (기준 궤적 호출 비용으로 이미 한 번 낸다).

프롬프트 캐시 가정 세 가지 (모든 비용에 각각 계산)
    no_cache            적중 0% (상한). 입력 전부 input 단가
    prefix_cache        실제로 보내는 이전 요청과 앞쪽 메시지가 같은 가장 긴 접두부를 캐시 읽기로 본다 (1,024 토큰 이상일 때만,
                        OpenAI 프롬프트 캐시 최소 길이). 같은 요청을 sample 마다 다시 보내는 경우, none 처럼 기록이 앞에서부터
                        그대로 자라는 경우, window 의 앞쪽 턴처럼 아직 잘리지 않은 경우가 여기서 잡힌다. 나머지는 input 단가
    prefix_cache_write  prefix_cache 에서 캐시되지 않은 입력을 cache_write 단가로 계산 (캐시 쓰기가 따로 과금될 때의 상한)
    보존 시간(30분 등) 안에 모든 요청이 이어서 간다고 가정한다. 128 토큰 단위 절삭은 무시한다.
"""

from __future__ import annotations

from collections import defaultdict

from config import CFG
from cost import find_price, load_pricing
from llm import count_message_tokens, count_tokens
from multiturn.history_compressors import get_history_compressor
from multiturn.prompt import load_mt_prompt

CACHE_MIN_TOKENS = 1024
M = 1_000_000
VARIANTS = ("no_cache", "prefix_cache", "prefix_cache_write")
REFERENCE_NOTE = ("none 의 reference sample 은 기준 궤적과 같은 요청이라 응답 캐시에 적중해 실제 지출이 0원이다 "
                  "(기준 궤적 호출로 이미 한 번 낸다). 압축기 비교는 응답 캐시와 무관한 실험상 비용(호출당) 기준이다.")


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


def call_usd(n_in: int, cached: int, n_out: int, price: dict | None) -> dict:
    """호출 하나의 비용을 세 가지 캐시 가정으로."""
    if price is None:
        return {v: None for v in VARIANTS}
    read = price.get("cache_read") if price.get("cache_read") is not None else price["input"]
    write = price.get("cache_write") if price.get("cache_write") is not None else price["input"]
    out = n_out * price["output"] / M
    return {
        "no_cache": n_in * price["input"] / M + out,
        "prefix_cache": (n_in - cached) * price["input"] / M + cached * read / M + out,
        "prefix_cache_write": (n_in - cached) * write / M + cached * read / M + out,
    }


def _add_usd(acc: dict, usd: dict) -> None:
    for v in VARIANTS:
        acc[v] = (acc.get(v) or 0) + (usd[v] or 0) if usd[v] is not None else acc.get(v)


def _round(d: dict) -> dict:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def estimate(cfg, scenarios: list[dict], corpus, answer_tokens: int = 300, reasoning_tokens: int = 1000,
             judge_model: str = "deepseek-flash", judge_in: int = 261, judge_out: int = 101,
             pricing: dict | None = None, tokenizer_check: dict | None = None) -> dict:
    pricing = load_pricing() if pricing is None else pricing
    prompt = load_mt_prompt(cfg.prompt_version)
    ap = find_price(cfg.model, pricing)[1]
    jp = find_price(judge_model, pricing)[1]
    out_tokens = answer_tokens + reasoning_tokens
    # 압축기 생성 실패(llmlingua 없음 등)는 삼키지 않는다: 여기서 예외가 나면 추정도 멈춘다
    comps = {name: get_history_compressor(name) for name in cfg.compressors}
    cache = PrefixCache()

    # 기준 궤적 (실제로 보냄)
    reference = {"requests": 0, "input_tokens": 0, "usd": {}}
    ref_calls = {}           # (scenario, turn) -> (n_in, cached) : none reference sample 의 실험상 비용에 쓴다
    histories = {}
    for s in scenarios:
        h = [{"role": "system", "content": prompt.system}]
        hs = []
        for t in s["turns"]:
            user = prompt.user_message(t, corpus)
            msgs = h + [{"role": "user", "content": user}]
            n_in, hit = count_message_tokens(msgs), cache.cached_tokens(msgs)
            ref_calls[(s["scenario_id"], t["turn"])] = (n_in, hit)
            reference["requests"] += 1
            reference["input_tokens"] += n_in
            _add_usd(reference["usd"], call_usd(n_in, hit, out_tokens, ap))
            hs.append((list(h), user))
            h = msgs + [{"role": "assistant", "content": placeholder_answer(answer_tokens)}]
        histories[s["scenario_id"]] = hs

    rows = {name: {"requests": 0, "actual_requests": 0, "input_tokens": 0, "cached_tokens_prefix_sim": 0,
                   "history_raw": 0, "history_comp": 0, "judge_calls": 0,
                   "usd_experimental": {}, "usd_actual": {}} for name in comps}
    for s in scenarios:
        for k, t in enumerate(s["turns"]):
            history, user = histories[s["scenario_id"]][k]
            n_judge = len(t["key_facts"]) if cfg.judge_mode == "per_fact" else 1
            for name, comp in comps.items():
                r = rows[name]
                res = comp.compress_history(history, user)
                n_in = count_message_tokens(res.messages)
                for i in range(cfg.samples):
                    r["requests"] += 1
                    r["input_tokens"] += n_in
                    r["judge_calls"] += n_judge
                    if name == "none" and i == cfg.reference_sample:
                        # 응답 캐시 적중: 실제로 보내지 않는다. 실험상 비용은 같은 요청인 기준 궤적 호출의 값
                        ref_in, ref_hit = ref_calls[(s["scenario_id"], k)]
                        _add_usd(r["usd_experimental"], call_usd(ref_in, ref_hit, out_tokens, ap))
                        continue
                    hit = cache.cached_tokens(res.messages)
                    usd = call_usd(n_in, hit, out_tokens, ap)
                    r["actual_requests"] += 1
                    r["cached_tokens_prefix_sim"] += hit
                    _add_usd(r["usd_experimental"], usd)
                    _add_usd(r["usd_actual"], usd)
                r["history_raw"] += sum(count_tokens(m["content"]) for m in history[1:]) * cfg.samples
                r["history_comp"] += sum(count_tokens(m["content"]) for m in res.messages[1:-1]) * cfg.samples

    judge_call_usd = (judge_in * jp["input"] + judge_out * jp["output"]) / M if jp else None
    base = rows.get("none")
    out_rows = {}
    for name, r in rows.items():
        red = {}
        for v in VARIANTS:
            b = (base or {}).get("usd_experimental", {}).get(v)
            c = r["usd_experimental"].get(v)
            red[v] = round(100 * (1 - c / b), 2) if b and c is not None else None
        out_rows[name] = {
            "requests": r["requests"], "actual_requests": r["actual_requests"],
            "input_tokens": r["input_tokens"], "cached_tokens_prefix_sim": r["cached_tokens_prefix_sim"],
            "input_reduction_pct_vs_none": (round(100 * (1 - r["input_tokens"] / base["input_tokens"]), 2)
                                            if base and base["input_tokens"] else None),
            "history_reduction_pct": round(100 * (1 - r["history_comp"] / r["history_raw"]), 2) if r["history_raw"] else None,
            "answer_usd_experimental": _round(r["usd_experimental"]),      # 압축기 비교 기준 (호출당)
            "cost_reduction_pct_vs_none": red,                             # 실험상 비용 기준
            "answer_usd_actual": _round(r["usd_actual"]),                  # 예산 확인용
            "judge_calls": r["judge_calls"],
            "judge_usd": round(r["judge_calls"] * judge_call_usd, 4) if judge_call_usd is not None else None,
        }
    actual_total = {}
    for v in VARIANTS:
        vals = [x["answer_usd_actual"].get(v) for x in out_rows.values()] + [reference["usd"].get(v)]
        actual_total[v] = round(sum(x for x in vals if x is not None), 4) if ap else None
    ref_judge = sum((len(t["key_facts"]) if cfg.judge_mode == "per_fact" else 1) for s in scenarios for t in s["turns"])
    return {
        "tokenizer": tokenizer_check or {"tokenizer": CFG.tokenizer},
        "assumptions": {"model": cfg.model, "answer_tokens": answer_tokens, "reasoning_tokens": reasoning_tokens,
                        "judge_model": judge_model, "judge_mode": cfg.judge_mode, "judge_in_per_call": judge_in,
                        "judge_out_per_call": judge_out, "samples": cfg.samples, "compressors": cfg.compressors,
                        "scenarios": len(scenarios), "turns": sum(len(s["turns"]) for s in scenarios),
                        "pricing_found": {"answer": ap is not None, "judge": jp is not None}},
        "notes": [REFERENCE_NOTE,
                  f"기준 궤적 채점 {ref_judge}회는 none reference sample 채점과 같은 요청이라 judge 응답 캐시로 한 번만 낸다 "
                  "(채점 비용에는 none reference sample 몫으로 한 번 들어 있다)."],
        "reference": {"requests": reference["requests"], "input_tokens": reference["input_tokens"],
                      "answer_usd": _round(reference["usd"])},
        "compressors": out_rows,
        "budget_answer_usd_actual": actual_total,      # 기준 궤적 + replay 실제 요청
        "budget_judge_usd": (round(sum(x["judge_usd"] or 0 for x in out_rows.values()), 4) if jp else None),
    }


def print_estimate(est: dict) -> None:
    tk = est["tokenizer"]
    flag = "" if tk.get("ok", True) else "  ** 근사: 답변 모델 토크나이저와 다름 **"
    print(f"토크나이저: {tk.get('tokenizer')}" + (f" (기대값 {tk.get('expected')})" if tk.get("expected") else "") + flag)
    a = est["assumptions"]
    print(f"\n예상 비용 (API 호출 없음) model={a['model']}  시나리오 {a['scenarios']}개 / 턴 {a['turns']}개  "
          f"sample {a['samples']}  답변 {a['answer_tokens']} + 추론 {a['reasoning_tokens']} 토큰 가정")
    if not a["pricing_found"]["answer"]:
        print("  [경고] 답변 모델 단가가 data/pricing.json 에 없습니다")

    print("\n[압축기 비교] 실험상 비용 (호출당, 응답 캐시와 무관). 절감률은 none 대비")
    print(f"{'압축기':<24}{'trial':>6}{'입력 토큰':>12}{'입력 절감':>9}{'기록 절감':>9}"
          f"{'캐시0%':>10}{'절감':>8}{'접두캐시':>10}{'절감':>8}{'+쓰기':>10}{'절감':>8}")
    for name, x in est["compressors"].items():
        u, red = x["answer_usd_experimental"], x["cost_reduction_pct_vs_none"]
        cells = "".join(f"{(u.get(v) or 0):>10.4f}{(red.get(v) or 0):>7.1f}%" for v in VARIANTS)
        print(f"{name:<24}{x['requests']:>6}{x['input_tokens']:>12,}{x['input_reduction_pct_vs_none'] or 0:>8.1f}%"
              f"{x['history_reduction_pct'] or 0:>8.1f}%{cells}")

    print("\n[예산 확인] 실제 지출 (실제로 보내는 요청만)")
    r = est["reference"]
    print(f"  기준 궤적: 요청 {r['requests']}  입력 {r['input_tokens']:,} 토큰  "
          + "  ".join(f"{v} ${r['answer_usd'].get(v)}" for v in VARIANTS))
    for name, x in est["compressors"].items():
        print(f"  {name:<24} 실제 요청 {x['actual_requests']:>3}/{x['requests']:<3}  "
              + "  ".join(f"{v} ${x['answer_usd_actual'].get(v) or 0}" for v in VARIANTS)
              + f"  채점 ${x['judge_usd']}")
    t = est["budget_answer_usd_actual"]
    print(f"  합계 답변 (기준 궤적 포함): 캐시0% ${t['no_cache']}  접두캐시 ${t['prefix_cache']}  "
          f"쓰기과금 ${t['prefix_cache_write']}   채점 ${est['budget_judge_usd']}")
    for n in est["notes"]:
        print(f"  * {n}")
