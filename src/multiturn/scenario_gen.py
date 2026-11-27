"""
multiturn-v2 시나리오 후보 생성 (생성 모델 gpt-6.1-sol, 프롬프트 src/prompts/mt_scenario_gen_v1.md)

    python src/multiturn/scenario_gen.py --bundle v2_01 --scenario-id v2_01_auth_switch
    python src/multiturn/scenario_gen.py --bundle v2_01 --scenario-id v2_01_auth_switch --dry-run   # 프롬프트만 저장

단계
    1. bundles.json 의 페이지 원문으로 프롬프트를 만든다
    2. 생성 모델 호출 (응답 캐시 없음). 요청 메시지·설정·응답 원문·usage 를 run 폴더에 전부 저장한다
    3. JSON 파싱 → fill_derived → validate_scenario_v2. 오류가 있으면 오류 목록을 붙여 1회만 다시 요청한다
       (근거 확인 실패는 다시 요청하지 않는다. 표시만 하고 검수로 넘긴다)
    4. check_grounding_v2 결과를 함께 저장하고, 시나리오를 data/evalsets/multiturn-v2/<scenario_id>.json 으로 쓴다 (status draft)

run 폴더: results/scenario_gen/<run_id>/
    request_<n>.json   보낸 메시지와 요청 설정 (모델, reasoning_effort, 출력 한도, temperature)
    response_<n>.json  응답 원문 (text, finish_reason, usage, raw_usage, 서버 모델, created_at)
    checks.json        validate_scenario_v2 / check_grounding_v2 오류, rule_report, 비용
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CFG  # noqa: E402

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "mt_scenario_gen_v1.md"
BUNDLES = CFG.root / "docs" / "experiments" / "multiturn_v2" / "bundles.json"
OUT_DIR = CFG.root / "data" / "evalsets" / "multiturn-v2"
GEN_MODEL = "gpt-6.1-sol"


def load_gen_prompt() -> dict:
    text = PROMPT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    sections, cur = {}, None
    for line in text.split("\n"):
        m = re.match(r"## (\w+)\s*$", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
        elif cur:
            sections[cur].append(line)
    out = {k: "\n".join(v).strip() for k, v in sections.items()}
    out["version"] = "mt_scenario_gen_v1"
    out["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return out


def build_messages(prompt: dict, scenario_id: str, topic: str, pages: list[str], corpus) -> list[dict]:
    blocks = [f"=== PAGE: {p} ===\n{corpus.get(p).text.strip()}\n=== END PAGE: {p} ===" for p in pages]
    user = prompt["user"].format(scenario_id=scenario_id, topic=topic, bundle="\n".join(f"- {p}" for p in pages),
                                 pages="\n\n".join(blocks))
    return [{"role": "system", "content": prompt["system"]}, {"role": "user", "content": user}]


def parse_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("응답에 JSON 객체가 없습니다")
    return json.loads(t[start:end + 1])


def _save(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def make_llm(max_tokens: int, reasoning_effort: str):
    from llm import LLM
    from multiturn.replay import configure_llm
    return configure_llm(LLM(role="answer"), GEN_MODEL, reasoning_effort, max_tokens, "server_default")


def generate(bundle_id: str, scenario_id: str, *, corpus, llm, run_dir: Path, max_repairs: int = 1) -> dict:
    from cost import compute_cost
    from multiturn.scenario_v2 import check_grounding_v2, fill_derived, rule_report, validate_scenario_v2

    bundles = json.loads(BUNDLES.read_text(encoding="utf-8"))
    b = bundles[bundle_id]
    prompt = load_gen_prompt()
    messages = build_messages(prompt, scenario_id, b["topic"], b["pages"], corpus)
    run_dir.mkdir(parents=True, exist_ok=True)
    attempts, usd, scenario, errs = [], 0.0, None, []
    for n in range(max_repairs + 1):
        _save(run_dir / f"request_{n}.json", {"messages": messages, "settings": llm.sampling_info(),
                                             "backend": llm.backend, "base_url": llm.base_url,
                                             "prompt": [prompt["version"], prompt["sha256"]]})
        res = llm.chat(messages)
        cost = compute_cost(res).to_dict()
        usd += cost.get("usd") or 0.0
        _save(run_dir / f"response_{n}.json", {
            "text": res.text, "finish_reason": res.finish_reason, "model": res.model, "created_at": res.created_at,
            "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
            "reasoning_tokens": res.reasoning_tokens, "raw_usage": res.raw_usage, "latency": res.latency, "cost": cost})
        try:
            scenario = parse_json(res.text)
            fill_derived(scenario)
            errs = validate_scenario_v2(scenario)
        except Exception as e:     # 파싱 실패·필드 누락도 형식 오류로 보고 재요청 대상
            errs = [f"JSON 을 읽지 못했습니다: {type(e).__name__}: {e}"]
            scenario = None
        attempts.append({"attempt": n, "finish_reason": res.finish_reason, "validate_errors": errs})
        if not errs or n == max_repairs:
            break
        messages = messages + [{"role": "assistant", "content": res.text},
                               {"role": "user", "content": prompt["repair"].format(errors="\n".join(f"- {e}" for e in errs))}]
    grounding = check_grounding_v2(scenario, corpus) if scenario else []
    if scenario:
        scenario["generation"] = {"model": GEN_MODEL, "served_model": res.model, "prompt": [prompt["version"], prompt["sha256"]],
                                  "settings": llm.sampling_info(), "run_id": run_dir.name, "attempts": len(attempts),
                                  "created_at": datetime.now().isoformat(timespec="seconds")}
        scenario["status"] = "draft"
    checks = {"bundle": bundle_id, "scenario_id": scenario_id, "attempts": attempts,
              "validate_errors": errs, "grounding_errors": grounding, "usd": round(usd, 6),
              "report": rule_report(scenario, corpus) if scenario and not errs else None}
    _save(run_dir / "checks.json", checks)
    if scenario:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        _save(OUT_DIR / f"{scenario_id}.json", scenario)
    return checks


def main(argv=None):
    ap = argparse.ArgumentParser(description="multiturn-v2 시나리오 후보 생성")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--scenario-id", required=True)
    ap.add_argument("--max-completion-tokens", type=int, default=40000)
    ap.add_argument("--reasoning-effort", default="server_default")
    ap.add_argument("--max-repairs", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true", help="API 를 부르지 않고 프롬프트만 저장")
    a = ap.parse_args(argv)
    from corpus import load_corpus
    corpus = load_corpus()
    run_dir = CFG.results_dir / "scenario_gen" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{a.scenario_id}"
    if a.dry_run:
        b = json.loads(BUNDLES.read_text(encoding="utf-8"))[a.bundle]
        run_dir.mkdir(parents=True, exist_ok=True)
        msgs = build_messages(load_gen_prompt(), a.scenario_id, b["topic"], b["pages"], corpus)
        _save(run_dir / "request_dry.json", {"messages": msgs})
        from llm import count_message_tokens
        print(f"프롬프트 {count_message_tokens(msgs)} 토큰 -> {run_dir}")
        return
    checks = generate(a.bundle, a.scenario_id, corpus=corpus,
                      llm=make_llm(a.max_completion_tokens, a.reasoning_effort), run_dir=run_dir,
                      max_repairs=a.max_repairs)
    print(json.dumps({k: checks[k] for k in ("scenario_id", "validate_errors", "grounding_errors", "usd")},
                     ensure_ascii=False, indent=1))
    print(f"run: {run_dir}")


if __name__ == "__main__":
    main()
