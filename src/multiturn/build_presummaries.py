"""
사전 요약(presummary) 구축: 위키 페이지마다 요약을 한 번 만들어 data/presummaries/<요약 모델>/<페이지 경로>.md 에 저장한다.

    python src/multiturn/build_presummaries.py --scenarios data/evalsets/multiturn-v1 \
        --model gpt-6-luna --reasoning-effort server_default --max-tokens 4096 --presummary-target-ratio 0.25

    --model, --reasoning-effort, --max-tokens 는 필수 (config 기본값에 기대지 않는다).
    --estimate-only 는 API 를 부르지 않고 예상 비용만 출력한다.

- 시나리오의 evidence_pages 에 나오는 페이지만 만든다 (--pages 로 직접 줄 수도 있다). 이미 있는 파일은 건너뛴다.
- 요약 입력은 답변 메시지에 첨부되는 것과 같은 본문(corpus.expanded_text) 이다. 질문·정답·key_facts 는 넣지 않는다.
- 빈 출력·finish_reason=length 는 응답 캐시에 저장하지 않고 최대 3번 시도한다. 그래도 실패하면 그 페이지를 오류로 남기고 끝에 실패로 종료한다.
- 같은 폴더에 _manifest.json (프롬프트·모델·추론·출력 한도·목표 비율) 을 둔다. 설정이 다른 폴더에 이어 쓰려 하면 멈춘다
  (다른 설정은 --out 으로 다른 폴더에).
- 구축 비용: _build_log.jsonl 에 페이지별 토큰·비용·실제 압축률(요약 토큰 / 원문 토큰) 을 남긴다. 실험 run 비용과 따로 본다.
  응답 캐시 적중이면 실제 지출은 0 이고, 기록에는 원래 호출의 usage 를 그대로 남긴다 (cache_hit 로 구분).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from datetime import datetime

from config import CFG
from cost import compute_cost, find_price, load_pricing
from llm import count_message_tokens, count_tokens
from multiturn.history_compressors.notes import (
    PRESUMMARY_ROOT, load_section_prompt, output_ok, target_tokens_for,
)
from multiturn.trajectory import REASONING_EFFORT_CHOICES, SERVER_DEFAULT

MAX_ATTEMPTS = 3


def pages_of(scenarios: list[dict]) -> list[str]:
    return sorted({p for s in scenarios for t in s["turns"] for p in t["evidence_pages"]})


def build_messages(prompt, page: str, document: str, target_tokens: int, source_tokens: int) -> list[dict]:
    user = prompt.sections["user"].format(page=page, document=document.strip(), target_tokens=target_tokens,
                                          source_tokens=source_tokens)
    return [{"role": "system", "content": prompt.sections["system"]}, {"role": "user", "content": user}]


def manifest_for(prompt, model, effort, max_tokens, ratio, temperature, llm=None) -> dict:
    m = {"prompt": [prompt.version, prompt.sha256], "model": model, "reasoning_effort": effort,
         "max_tokens": max_tokens, "target_ratio": ratio, "temperature": temperature,
         "min_target_tokens": 60, "tokenizer": CFG.tokenizer}
    if llm is not None:
        m["backend"], m["base_url"] = llm.backend, llm.base_url
    return m


SETTING_KEYS = ("prompt", "model", "reasoning_effort", "max_tokens", "target_ratio", "temperature")


def check_manifest(out: Path, manifest: dict) -> None:
    mf = out / "_manifest.json"
    if mf.exists():
        old = json.loads(mf.read_text(encoding="utf-8"))
        diff = {k: (old.get(k), manifest.get(k)) for k in SETTING_KEYS if old.get(k) != manifest.get(k)}
        if diff:
            raise SystemExit(f"[중단] {out} 의 기존 요약과 설정이 다릅니다: {diff}. 다른 설정은 --out 으로 다른 폴더에 만드세요.")
    else:
        out.mkdir(parents=True, exist_ok=True)
        mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def build(pages: list[str], corpus, cached, prompt, out: Path, ratio: float, log=print) -> dict:
    """요약이 없는 페이지만 만든다. cached 는 CachedLLM. 반환: {"built": [...], "skipped": [...], "failed": [...]}"""
    res_all = {"built": [], "skipped": [], "failed": []}
    for page in pages:
        path = out / page
        if path.exists() and path.read_text(encoding="utf-8").strip():
            res_all["skipped"].append(page)
            continue
        doc = corpus.expanded_text(page)
        src = count_tokens(doc)
        target = target_tokens_for(src, ratio)
        messages = build_messages(prompt, page, doc, target, src)
        attempts, text, reason = [], None, None
        for _ in range(MAX_ATTEMPTS):
            r, hit = cached.chat(messages, sample_idx=0, store_if=output_ok)
            attempts.append((r, hit))
            if output_ok(r):
                text = r.text.strip()
                break
            reason = "length" if r.finish_reason == "length" else "empty"
        rec = {"page": page, "source_tokens": src, "target_tokens": target, "target_ratio": ratio,
               "prompt_tokens": sum(r.prompt_tokens for r, _ in attempts),
               "completion_tokens": sum(r.completion_tokens for r, _ in attempts),
               "reasoning_tokens": sum(r.reasoning_tokens or 0 for r, _ in attempts),
               "usd": round(sum(compute_cost(r).usd or 0 for r, _ in attempts), 8),
               "usd_actual": round(sum(compute_cost(r).usd or 0 for r, hit in attempts if not hit), 8),
               "attempts": len(attempts), "cache_hits": sum(hit for _, hit in attempts),
               "finish_reasons": [r.finish_reason for r, _ in attempts], "model": attempts[-1][0].model,
               "created_at": datetime.now().isoformat(timespec="seconds")}
        if text is None:
            rec.update(failed=True, fail_reason=reason)
            res_all["failed"].append(page)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
            n = count_tokens(text)
            rec.update(failed=False, summary_tokens=n, ratio=round(n / src, 4) if src else None,
                       over_2x_target=n > 2 * target)
            res_all["built"].append(page)
        with open(out / "_build_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        desc = (f"실패 {reason}" if text is None
                else f"{rec['summary_tokens']}/{src} 토큰 (비율 {rec['ratio']}, 목표 {target})")
        log(f"  {page}: {desc}" + (" [캐시]" if rec["cache_hits"] else ""))
    return res_all


def estimate(pages, corpus, prompt, model, ratio, reasoning_tokens, out: Path) -> dict:
    price = find_price(model, load_pricing())[1]
    rows, tot_in, tot_out = [], 0, 0
    for page in pages:
        if (out / page).exists():
            continue
        doc = corpus.expanded_text(page)
        src = count_tokens(doc)
        target = target_tokens_for(src, ratio)
        n_in = count_message_tokens(build_messages(prompt, page, doc, target, src))
        n_out = target + reasoning_tokens
        tot_in, tot_out = tot_in + n_in, tot_out + n_out
        rows.append({"page": page, "source_tokens": src, "target_tokens": target, "input_tokens": n_in})
    usd = (tot_in * price["input"] + tot_out * price["output"]) / 1e6 if price else None
    return {"pages_to_build": len(rows), "pages_existing": len(pages) - len(rows), "input_tokens": tot_in,
            "output_tokens_assumed": tot_out, "usd": round(usd, 4) if usd is not None else None, "rows": rows}


def build_report(out: Path) -> dict:
    """_build_log.jsonl 의 페이지별 압축률 요약 (마지막 기록 기준)."""
    p = out / "_build_log.jsonl"
    last = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                last[r["page"]] = r
    ok = [r for r in last.values() if not r.get("failed")]
    ratios = [r["ratio"] for r in ok if r.get("ratio") is not None]
    return {"pages": len(last), "failed": sum(bool(r.get("failed")) for r in last.values()),
            "ratio_mean": round(sum(ratios) / len(ratios), 4) if ratios else None,
            "ratio_total": (round(sum(r["summary_tokens"] for r in ok) / sum(r["source_tokens"] for r in ok), 4)
                            if ok else None),
            "over_2x_target": sum(bool(r.get("over_2x_target")) for r in ok),
            "build_usd": round(sum(r.get("usd") or 0 for r in last.values()), 6),
            "build_prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in last.values()),
            "build_completion_tokens": sum(r.get("completion_tokens") or 0 for r in last.values()),
            "build_reasoning_tokens": sum(r.get("reasoning_tokens") or 0 for r in last.values()),
            "by_page": {k: {kk: r.get(kk) for kk in ("source_tokens", "target_tokens", "summary_tokens", "ratio",
                                                     "over_2x_target", "usd", "cache_hits")}
                        for k, r in sorted(last.items())}}


def build_parser():
    ap = argparse.ArgumentParser(description="presummary 구축 (페이지별 사전 요약)")
    ap.add_argument("--scenarios", help="시나리오 폴더. evidence_pages 의 페이지만 만든다")
    ap.add_argument("--pages", default="", help="쉼표 구분 페이지 목록 (--scenarios 대신)")
    ap.add_argument("--model", required=True, help="필수. 요약 모델")
    ap.add_argument("--reasoning-effort", required=True, choices=REASONING_EFFORT_CHOICES, help="필수")
    ap.add_argument("--max-tokens", type=int, required=True, help="필수. 추론 포함 출력 한도")
    ap.add_argument("--presummary-target-ratio", type=float, default=0.25, help="목표 길이 = 원문 토큰 × 비율 (기본 0.25)")
    ap.add_argument("--temperature", default=SERVER_DEFAULT)
    ap.add_argument("--prompt", default="v1", help="src/prompts/presummary_<version>.md")
    ap.add_argument("--out", help="기본 data/presummaries/<model>")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--assume-reasoning-tokens", type=int, default=1000, help="(--estimate-only) 호출당 추론 토큰")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    if not 0 < a.presummary_target_ratio <= 1:
        sys.exit("--presummary-target-ratio 는 0 초과 1 이하")
    if a.max_tokens <= 0:
        sys.exit("--max-tokens 는 양의 정수")
    from corpus import load_corpus
    corpus = load_corpus()
    if a.pages:
        pages = [p.strip() for p in a.pages.split(",") if p.strip()]
    elif a.scenarios:
        from multiturn.scenario import load_scenarios
        pages = pages_of(load_scenarios(a.scenarios))
    else:
        sys.exit("--scenarios 또는 --pages 가 필요합니다")
    for p in pages:
        corpus.get(p)                              # 없는 페이지면 KeyError
    prompt = load_section_prompt("presummary", a.prompt)
    out = Path(a.out) if a.out else PRESUMMARY_ROOT / a.model
    if a.estimate_only:
        est = estimate(pages, corpus, prompt, a.model, a.presummary_target_ratio, a.assume_reasoning_tokens, out)
        print(f"[presummary 예상] 페이지 {len(pages)}개 중 새로 만들 것 {est['pages_to_build']}개  입력 {est['input_tokens']:,}  "
              f"출력 가정 {est['output_tokens_assumed']:,} (목표 + 추론 {a.assume_reasoning_tokens})  ${est['usd']}")
        return
    from llm import LLM
    from multiturn.replay import configure_llm
    from multiturn.response_cache import CachedLLM
    llm = configure_llm(LLM(role="answer"), a.model, a.reasoning_effort, a.max_tokens, a.temperature)
    manifest = manifest_for(prompt, a.model, a.reasoning_effort, a.max_tokens, a.presummary_target_ratio,
                            a.temperature, llm)
    check_manifest(out, manifest)
    cached = CachedLLM(llm)
    try:
        print(f"presummary 구축: {len(pages)}개 페이지 -> {out}")
        r = build(pages, corpus, cached, prompt, out, a.presummary_target_ratio)
    finally:
        cached.close()
    rep = build_report(out)
    print(f"만듦 {len(r['built'])}  건너뜀 {len(r['skipped'])}  실패 {len(r['failed'])}")
    print(f"[압축률] 평균 {rep['ratio_mean']}  전체 {rep['ratio_total']}  목표 2배 초과 {rep['over_2x_target']}/{rep['pages']}  "
          f"구축 비용 ${rep['build_usd']}")
    if r["failed"]:
        sys.exit(f"[실패] {r['failed']}")


if __name__ == "__main__":
    main()
