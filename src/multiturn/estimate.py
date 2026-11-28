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
    prefix_cache        접두부를 캐시 읽기로 본다 (1,024 토큰 이상일 때만, OpenAI 프롬프트 캐시 최소 길이). 나머지는 input 단가.
                        압축기 비교(실험상 비용): 같은 체인의 직전 턴 요청과 겹치는 접두부 = 실제 대화의 캐시 (replay 의 *_sim).
                        예산(실제 지출): 실행 전체에서 이미 보낸 요청과 겹치는 접두부 (sample 반복처럼 같은 요청을 다시 보내는 경우 포함).
    prefix_cache_write  prefix_cache 에서 캐시되지 않은 입력을 cache_write 단가로 계산 (캐시 쓰기가 따로 과금될 때의 상한)
    보존 시간(30분 등) 안에 모든 요청이 이어서 간다고 가정한다. 128 토큰 단위 절삭은 무시한다.

요약형 압축기 (rolling_summary, frozen_summary)
    요약 출력은 summary_tokens 길이의 자리표시 요약으로 두고 상태를 실제로 굴려, 요약이 언제 일어나는지(호출 수·재압축 수)를 센다.
    요약 호출 입력은 실제 요약 프롬프트(mt_summary_v1)로 센다. 출력은 summary_tokens + summary_reasoning_tokens.
    요약은 sample 마다 따로 호출한다 (응답 캐시 키에 sample_idx). 압축기 비교 비용 = 답변 + 요약 (실험상 비용).
    요약 추론 조건([sre=...]) 별로 요약기를 따로 둔다. 조건 none 은 추론 토큰 0, 나머지는 summary_reasoning_tokens 로 가정한다.
접두부 공유율: 같은 체인의 직전 턴 요청과 메시지 단위로 겹치는 접두부 / 입력 (common_prefix_tokens, replay 와 같은 함수).

presummary
    저장된 사전 요약을 쓴다. 아직 없으면 원문 × 0.25 길이의 자리표시 요약으로 센다 (구축 비용은 build_presummaries.py --estimate-only).
fact_notes
    문서가 있는 턴 × sample 마다 메모 추출 1회. 입력은 실제 메모 프롬프트(fact_notes_v1)로, 출력은 목표 길이 + summary_reasoning_tokens
    (notes_reasoning_effort 가 none 이면 추론 0) 로 센다. 비용은 "요약" 열에 합친다 (압축 LLM 비용).
"""

from __future__ import annotations

from collections import defaultdict

from config import CFG
from cost import find_price, load_pricing
from llm import count_message_tokens, count_tokens
from multiturn.history_compressors import get_history_compressor, is_stateful
from multiturn.history_compressors.summary import SummaryOutcome, Summarizer
from multiturn.prompt import load_mt_prompt

CACHE_MIN_TOKENS = 1024
M = 1_000_000
VARIANTS = ("no_cache", "prefix_cache", "prefix_cache_write")
REFERENCE_NOTE = ("none 의 reference sample 은 기준 궤적과 같은 요청이라 응답 캐시에 적중해 실제 지출이 0원이다 "
                  "(기준 궤적 호출로 이미 한 번 낸다). 압축기 비교는 응답 캐시와 무관한 실험상 비용(호출당) 기준이다.")


def placeholder_answer(n_tokens: int) -> str:
    """대략 n_tokens 토큰짜리 자리표시 답변."""
    return " ".join(["answer"] * max(n_tokens, 0))


def common_prefix_tokens(a: list[dict] | None, b: list[dict], count_fn=None) -> int:
    """두 요청의 앞쪽 메시지가 (role, content) 까지 같은 가장 긴 접두부의 토큰 수 (1,024 기준 없이 원래 값)."""
    if not a:
        return 0
    count_fn = count_fn or count_message_tokens
    n = 0
    for x, y in zip(a, b):
        if x["role"] != y["role"] or x["content"] != y["content"]:
            break
        n += 1
    return count_fn(b[:n], add_generation_prompt=False) if n else 0


class EstimateSummarizer(Summarizer):
    """API 를 부르지 않는 요약기: summary_tokens 길이의 자리표시 요약을 돌려주고 토큰만 센다."""

    def __init__(self, model: str, summary_tokens: int, reasoning_tokens: int):
        super().__init__(cached=None)
        self.model, self.summary_tokens, self.reasoning_tokens = model, summary_tokens, reasoning_tokens

    def summarize(self, turns, previous, target_tokens, sample_idx):
        from llm import LLMResult
        msgs = self.build_messages(turns, previous, target_tokens)
        text = " ".join(["summary"] * self.summary_tokens)
        res = LLMResult(text=text, prompt_tokens=count_message_tokens(msgs),
                        completion_tokens=self.summary_tokens + self.reasoning_tokens, latency=0.0, model=self.model,
                        finish_reason="stop", reasoning_tokens=self.reasoning_tokens)
        return SummaryOutcome(text=text, results=[res], cache_hits=[False])

    def config(self):
        return {"estimate": True, "model": self.model, "summary_tokens": self.summary_tokens,
                "reasoning_tokens": self.reasoning_tokens}


class EstimateNotesExtractor:
    """API 를 부르지 않는 메모 추출기: 목표 길이의 자리표시 메모를 돌려주고 토큰만 센다."""

    def __init__(self, model: str, target_ratio: float, reasoning_tokens: int):
        from multiturn.history_compressors.notes import load_section_prompt
        self.model, self.target_ratio, self.reasoning_tokens = model, target_ratio, reasoning_tokens
        self.prompt = load_section_prompt("fact_notes", "v1")

    def extract(self, turn, documentation, question, answer, sample_idx):
        from llm import LLMResult
        from multiturn.history_compressors.notes import NotesExtractor, NotesOutcome, target_tokens_for
        src = count_tokens(documentation)
        target = target_tokens_for(src, self.target_ratio)
        msgs = NotesExtractor.build_messages(self, turn, documentation, question, answer, target)
        text = " ".join(["note"] * target)
        res = LLMResult(text=text, prompt_tokens=count_message_tokens(msgs),
                        completion_tokens=target + self.reasoning_tokens, latency=0.0, model=self.model,
                        finish_reason="stop", reasoning_tokens=self.reasoning_tokens)
        return NotesOutcome(turn=turn, text=text, source_tokens=src, target_tokens=target, results=[res],
                            cache_hits=[False], notes_tokens=target)

    def config(self):
        return {"estimate": True, "model": self.model, "target_ratio": self.target_ratio,
                "reasoning_tokens": self.reasoning_tokens}


class PlaceholderPresummaryStore:
    """사전 요약이 아직 없을 때: 원문 × ratio 길이의 자리표시 요약.
    real(PresummaryStore)을 주면 있는 페이지는 실제 요약을 쓰고, 없는 페이지만 자리표시로 센다 (추정 전용)."""

    def __init__(self, corpus, ratio: float = 0.25, real=None):
        self.corpus, self.ratio, self.real = corpus, ratio, real
        self.manifest = {"placeholder": True, "target_ratio": ratio}
        self.placeholder_pages: set[str] = set()

    def get(self, page: str) -> str:
        from multiturn.history_compressors.notes import MissingPresummaryError, target_tokens_for
        if self.real is not None:
            try:
                return self.real.get(page)
            except MissingPresummaryError:
                pass
        self.placeholder_pages.add(page)
        n = target_tokens_for(count_tokens(self.corpus.expanded_text(page)), self.ratio)
        return " ".join(["summary"] * n)

    def config(self):
        return {"placeholder": True, "target_ratio": self.ratio, "real": self.real is not None,
                "placeholder_pages": sorted(self.placeholder_pages)}


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
             pricing: dict | None = None, tokenizer_check: dict | None = None,
             summary_tokens: int = 300, summary_reasoning_tokens: int = 1000, presummary_store=None) -> dict:
    pricing = load_pricing() if pricing is None else pricing
    prompt = load_mt_prompt(cfg.prompt_version)
    ap = find_price(cfg.model, pricing)[1]
    jp = find_price(judge_model, pricing)[1]
    out_tokens = answer_tokens + reasoning_tokens
    sp = find_price(cfg.summary_model, pricing)[1] if cfg.summary_model else None
    summarizer = ({e: EstimateSummarizer(cfg.summary_model, summary_tokens,
                                         0 if e == "none" else summary_reasoning_tokens)
                   for e in cfg.summary_efforts} if cfg.has_summary else None)
    # 압축기 생성 실패(llmlingua 없음 등)는 삼키지 않는다: 여기서 예외가 나면 추정도 멈춘다
    if getattr(cfg, "has_presummary", False) and not isinstance(presummary_store, PlaceholderPresummaryStore):
        # 추정은 요약이 없는 페이지에서 멈추지 않는다: 있는 요약은 쓰고 없는 페이지는 자리표시 (실제 run 은 멈춘다)
        presummary_store = PlaceholderPresummaryStore(corpus, real=presummary_store)
    notes_extractor = (EstimateNotesExtractor(cfg.notes_model, cfg.notes_target_ratio,
                                              0 if cfg.notes_reasoning_effort == "none" else summary_reasoning_tokens)
                       if getattr(cfg, "has_notes", False) else None)
    comps = {name: get_history_compressor(name, token_counter=lambda t: count_tokens(t), summarizer=summarizer,
                                          keep_recent=cfg.keep_recent, presummary_store=presummary_store,
                                          notes_extractor=notes_extractor)
             for name in cfg.compressors}
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
                   "history_raw": 0, "history_comp": 0, "judge_calls": 0, "overflow": 0,
                   "summary_calls": 0, "summary_in": 0, "summary_out": 0, "recompress": 0, "recompress_turns": [],
                   "prefix_share": [], "usd_experimental": {}, "usd_actual": {}, "summary_usd": 0.0}
            for name in comps}

    def record(name, s_, k, i, res, prev):
        r = rows[name]
        n_in = count_message_tokens(res.messages)
        r["requests"] += 1
        r["input_tokens"] += n_in
        r["judge_calls"] += len(s_["turns"][k]["key_facts"]) if cfg.judge_mode == "per_fact" else 1
        r["overflow"] += bool(res.info.get("overflow"))
        r["history_comp"] += sum(count_tokens(m["content"]) for m in res.messages[1:-1])
        shared = common_prefix_tokens(prev, res.messages)
        r["prefix_share"].append(shared / n_in if n_in else 0)
        sim_hit = shared if shared >= CACHE_MIN_TOKENS else 0
        for call in res.info.get("_llm_results", []) or []:
            r["summary_calls"] += 1
            r["summary_in"] += call.prompt_tokens
            r["summary_out"] += call.completion_tokens
            cp = find_price(call.model, pricing)[1] if call.model else sp
            if cp:
                r["summary_usd"] += (call.prompt_tokens * cp["input"] + call.completion_tokens * cp["output"]) / M
        if res.info.get("recompressed"):
            r["recompress"] += 1
            r["recompress_turns"].append(k)
        # 압축기 비교 (실험상 비용): 같은 체인의 직전 턴 요청과 겹치는 접두부를 캐시 읽기로 본다 (replay 의 *_sim 과 같은 정의)
        _add_usd(r["usd_experimental"], call_usd(n_in, sim_hit, out_tokens, ap))
        if name == "none" and i == cfg.reference_sample:
            return      # 응답 캐시 적중: 실제로 보내지 않는다
        # 예산 (실제 지출): 실행 전체에서 이미 보낸 요청과 겹치는 접두부 (sample 반복 등) 를 캐시 읽기로 본다
        hit = cache.cached_tokens(res.messages)
        r["actual_requests"] += 1
        r["cached_tokens_prefix_sim"] += hit
        _add_usd(r["usd_actual"], call_usd(n_in, hit, out_tokens, ap))

    for s_ in scenarios:
        sid = s_["scenario_id"]
        for name, comp in comps.items():
            for k in range(len(s_["turns"])):
                rows[name]["history_raw"] += sum(count_tokens(m["content"])
                                                 for m in histories[sid][k][0][1:]) * cfg.samples
            if is_stateful(name):
                for i in range(cfg.samples):
                    state, prev = comp.initial_state(i), None
                    for k in range(len(s_["turns"])):
                        history, user = histories[sid][k]
                        res = comp.compress_history(history, user, None, state)
                        state = res.state
                        record(name, s_, k, i, res, prev)
                        prev = res.messages
            elif hasattr(comp, "turn_end"):          # fact_notes: 턴 k 메모 추출은 턴 k trial 에 귀속 (sample 마다)
                for i in range(cfg.samples):
                    prev = None
                    for k in range(len(s_["turns"])):
                        history, user = histories[sid][k]
                        res = comp.compress_history(history, user, None, {"sample_idx": i})
                        o = comp.turn_end(k, user, placeholder_answer(answer_tokens), i)
                        res.info["_llm_results"] = list(o.results) if o is not None else []
                        record(name, s_, k, i, res, prev)
                        prev = res.messages
            else:
                prev = None
                for k in range(len(s_["turns"])):
                    history, user = histories[sid][k]
                    res = comp.compress_history(history, user)
                    for i in range(cfg.samples):
                        record(name, s_, k, i, res, prev)
                    prev = res.messages

    judge_call_usd = (judge_in * jp["input"] + judge_out * jp["output"]) / M if jp else None
    base = rows.get("none")
    out_rows = {}
    for name, r in rows.items():
        red = {}
        for v in VARIANTS:
            b = (base or {}).get("usd_experimental", {}).get(v)
            c = r["usd_experimental"].get(v)
            c = c + r["summary_usd"] if c is not None else None
            red[v] = round(100 * (1 - c / b), 2) if b and c is not None else None
        out_rows[name] = {
            "requests": r["requests"], "actual_requests": r["actual_requests"],
            "input_tokens": r["input_tokens"], "cached_tokens_prefix_sim": r["cached_tokens_prefix_sim"],
            "input_reduction_pct_vs_none": (round(100 * (1 - r["input_tokens"] / base["input_tokens"]), 2)
                                            if base and base["input_tokens"] else None),
            "history_reduction_pct": round(100 * (1 - r["history_comp"] / r["history_raw"]), 2) if r["history_raw"] else None,
            "answer_usd_experimental": _round(r["usd_experimental"]),      # 압축기 비교 기준 (호출당)
            "summary_usd": round(r["summary_usd"], 4),     # 요약·메모 호출 (호출의 모델 단가로)
            "total_usd_experimental": _round({v: (r["usd_experimental"].get(v) or 0) + r["summary_usd"]
                                              for v in VARIANTS}) if ap else None,
            "cost_reduction_pct_vs_none": red,                             # 실험상 비용 (답변 + 요약) 기준
            "overflow_rate": round(r["overflow"] / r["requests"], 4) if r["requests"] else None,
            "summary_calls": r["summary_calls"], "summary_input_tokens": r["summary_in"],
            "summary_output_tokens": r["summary_out"],
            "recompress_count": r["recompress"],
            "recompress_per_chain": round(r["recompress"] / (len(scenarios) * cfg.samples), 2) if is_stateful(name) else None,
            "recompress_turns": sorted(set(r["recompress_turns"])),
            "prefix_share_mean": round(sum(r["prefix_share"]) / len(r["prefix_share"]), 4) if r["prefix_share"] else None,
            "answer_usd_actual": _round(r["usd_actual"]),                  # 예산 확인용
            "judge_calls": r["judge_calls"],
            "judge_usd": round(r["judge_calls"] * judge_call_usd, 4) if judge_call_usd is not None else None,
        }
    actual_total = {}
    for v in VARIANTS:
        vals = [x["answer_usd_actual"].get(v) for x in out_rows.values()] + [reference["usd"].get(v)]
        actual_total[v] = round(sum(x for x in vals if x is not None), 4) if ap else None
    summary_total = round(sum(r["summary_usd"] for r in rows.values()), 4)
    from multiturn.history_compressors import summary_effort_of
    by_effort = {}
    for name, r in rows.items():
        e = summary_effort_of(name)
        if e:
            d = by_effort.setdefault(e, {"summary_calls": 0, "summary_usd": 0.0, "reasoning_tokens_assumed":
                                         0 if e == "none" else summary_reasoning_tokens})
            d["summary_calls"] += r["summary_calls"]
            d["summary_usd"] = round(d["summary_usd"] + r["summary_usd"], 4)
    ref_judge = sum((len(t["key_facts"]) if cfg.judge_mode == "per_fact" else 1) for s in scenarios for t in s["turns"])
    return {
        "tokenizer": tokenizer_check or {"tokenizer": CFG.tokenizer},
        "assumptions": {"model": cfg.model, "answer_tokens": answer_tokens, "reasoning_tokens": reasoning_tokens,
                        "judge_model": judge_model, "judge_mode": cfg.judge_mode, "judge_in_per_call": judge_in,
                        "judge_out_per_call": judge_out, "samples": cfg.samples, "compressors": cfg.compressors,
                        "scenarios": len(scenarios), "turns": sum(len(s["turns"]) for s in scenarios),
                        "history_budgets": cfg.history_budgets, "keep_recent": cfg.keep_recent,
                        "summary_model": cfg.summary_model, "summary_tokens": summary_tokens,
                        "summary_reasoning_tokens": summary_reasoning_tokens,
                        "pricing_found": {"answer": ap is not None, "judge": jp is not None,
                                          "summary": (sp is not None) if cfg.summary_model else None}},
        "notes": [REFERENCE_NOTE,
                  f"기준 궤적 채점 {ref_judge}회는 none reference sample 채점과 같은 요청이라 judge 응답 캐시로 한 번만 낸다 "
                  "(채점 비용에는 none reference sample 몫으로 한 번 들어 있다)."],
        "reference": {"requests": reference["requests"], "input_tokens": reference["input_tokens"],
                      "answer_usd": _round(reference["usd"])},
        "compressors": out_rows,
        "budget_answer_usd_actual": actual_total,      # 기준 궤적 + replay 실제 요청
        "budget_summary_usd": summary_total,           # 요약 호출 (sample 마다 실제로 보냄)
        "summary_usd_by_effort": by_effort,
        "budget_judge_usd": (round(sum(x["judge_usd"] or 0 for x in out_rows.values()), 4) if jp else None),
        "presummary_placeholder_pages": (sorted(presummary_store.placeholder_pages)
                                         if isinstance(presummary_store, PlaceholderPresummaryStore) else None),
    }


def print_estimate(est: dict) -> None:
    tk = est["tokenizer"]
    flag = "" if tk.get("ok", True) else "  ** 근사: 답변 모델 토크나이저와 다름 **"
    print(f"토크나이저: {tk.get('tokenizer')}" + (f" (기대값 {tk.get('expected')})" if tk.get("expected") else "") + flag)
    a = est["assumptions"]
    print(f"\n예상 비용 (API 호출 없음) model={a['model']}  시나리오 {a['scenarios']}개 / 턴 {a['turns']}개  "
          f"sample {a['samples']}  답변 {a['answer_tokens']} + 추론 {a['reasoning_tokens']} 토큰 가정")
    if a.get("summary_model"):
        print(f"요약 model={a['summary_model']}  요약 출력 {a['summary_tokens']} + 추론 {a['summary_reasoning_tokens']} 토큰 가정  "
              f"예산 {a['history_budgets']}  keep_recent {a['keep_recent']}")
    if not a["pricing_found"]["answer"]:
        print("  [경고] 답변 모델 단가가 data/pricing.json 에 없습니다")
    if a["pricing_found"].get("summary") is False:
        print("  [경고] 요약 모델 단가가 data/pricing.json 에 없습니다")

    print("\n[압축기 비교] 실험상 비용 (호출당, 응답 캐시와 무관) = 답변 + 요약. 절감률은 none 대비")
    print("  sim = 직전 턴 요청과 겹치는 접두부를 캐시 읽기로 본 시뮬레이션 캐시 비용 (주 지표, 대화 간격이 캐시 보존 시간 30분 안이라는 가정)")
    print("  sim_write = sim 에서 미스 부분을 캐시 쓰기 단가로. 캐시0% = 캐시가 만료된 경우의 경계값")
    print(f"{'압축기':<44}{'입력 절감':>9}{'기록 절감':>9}{'overflow':>9}{'접두공유':>9}"
          f"{'답변(캐시0%)':>12}{'요약':>9}{'절감':>8}{'답변(sim)':>11}{'절감':>8}{'sim_write':>11}{'절감':>8}"
          f"{'요약호출':>8}{'재압축':>7}")
    for name, x in est["compressors"].items():
        u, red = x["answer_usd_experimental"], x["cost_reduction_pct_vs_none"]
        print(f"{name:<44}{x['input_reduction_pct_vs_none'] or 0:>8.1f}%{x['history_reduction_pct'] or 0:>8.1f}%"
              f"{(x['overflow_rate'] or 0) * 100:>8.1f}%{(x['prefix_share_mean'] or 0) * 100:>8.1f}%"
              f"{(u.get('no_cache') or 0):>12.4f}{(x['summary_usd'] or 0):>9.4f}{(red.get('no_cache') or 0):>7.1f}%"
              f"{(u.get('prefix_cache') or 0):>11.4f}{(red.get('prefix_cache') or 0):>7.1f}%"
              f"{(u.get('prefix_cache_write') or 0):>11.4f}{(red.get('prefix_cache_write') or 0):>7.1f}%"
              f"{x['summary_calls']:>8}{x['recompress_count']:>7}")
    if est.get("summary_usd_by_effort"):
        print("\n[요약 추론 조건별 요약 비용]")
        for e, d in est["summary_usd_by_effort"].items():
            print(f"  sre={e:<16} 요약 호출 {d['summary_calls']:>4}회  추론 {d['reasoning_tokens_assumed']} 토큰 가정  "
                  f"요약 비용 ${d['summary_usd']}")
    frozen = {n: x for n, x in est["compressors"].items() if n.startswith("frozen_summary(")}
    if frozen:
        print("\n[frozen_summary 재압축] 예산별 (체인 = 시나리오 × sample)")
        for name, x in frozen.items():
            print(f"  {name:<24} 재압축 {x['recompress_count']}회 (체인당 {x['recompress_per_chain']})  "
                  f"요약 호출 {x['summary_calls']}회  재압축 턴 {x['recompress_turns']}")

    if est.get("presummary_placeholder_pages"):
        print(f"\n[presummary] 사전 요약이 없는 페이지 {len(est['presummary_placeholder_pages'])}개는 원문 × 목표 비율 길이의 "
              "자리표시 요약으로 셌다 (구축 비용은 build_presummaries.py --estimate-only)")
    print("\n[예산 확인] 실제 지출 (실제로 보내는 요청만)")
    r = est["reference"]
    print(f"  기준 궤적: 요청 {r['requests']}  입력 {r['input_tokens']:,} 토큰  "
          + "  ".join(f"{v} ${r['answer_usd'].get(v)}" for v in VARIANTS))
    for name, x in est["compressors"].items():
        print(f"  {name:<44} 실제 요청 {x['actual_requests']:>3}/{x['requests']:<3}  "
              + "  ".join(f"{v} ${x['answer_usd_actual'].get(v) or 0}" for v in VARIANTS)
              + f"  요약 ${x['summary_usd'] or 0}  채점 ${x['judge_usd']}")
    t = est["budget_answer_usd_actual"]
    print(f"  합계 답변 (기준 궤적 포함): 캐시0% ${t['no_cache']}  접두캐시 ${t['prefix_cache']}  "
          f"쓰기과금 ${t['prefix_cache_write']}   요약 ${est['budget_summary_usd']}   채점 ${est['budget_judge_usd']}")
    for n in est["notes"]:
        print(f"  * {n}")
