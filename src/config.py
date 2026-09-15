"""
프로젝트 전역 설정

모델, 경로, 실험 조건을 한 곳에 모아둔다.
여기 값만 바꾸면 전체 실험이 따라 바뀌도록 하는 것이 목적.

환경변수로도 덮어쓸 수 있다.
    $env:LLM_MODEL = "qwen2.5:3b"     (PowerShell, 노트북에서 실행할 때)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# 프로젝트 최상위 경로 (config.py는 src/ 안에 있으므로 한 단계 위)
ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default):
    v = os.getenv(key)
    if v is None:
        return default
    if isinstance(default, bool):
        return v.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        return int(v)
    if isinstance(default, float):
        return float(v)
    return v


@dataclass
class Config:
    # ---------- 백엔드 ----------
    # "ollama" | "openai"  ("openai"는 LM Studio, vLLM, 상용 API 모두 해당)
    backend: str = _env("LLM_BACKEND", "ollama")
    base_url: str = _env("LLM_BASE_URL", "http://localhost:11434")
    api_key: str = _env("LLM_API_KEY", "")

    # ---------- 모델 ----------
    model: str = _env("LLM_MODEL", "qwen2.5:7b")          # 답변 생성
    judge_model: str = _env("JUDGE_MODEL", "qwen2.5:7b")  # 채점
    summary_model: str = _env("SUMMARY_MODEL", "qwen2.5:3b")  # 재귀 요약용
    embed_model: str = _env("EMBED_MODEL", "bge-m3")      # 의미 손실률

    # ---------- 생성 조건 (실험 통제) ----------
    temperature: float = _env("LLM_TEMPERATURE", 0.0)
    seed: int = _env("LLM_SEED", 42)
    num_ctx: int = _env("LLM_NUM_CTX", 16384)   # Ollama 기본 4096 -> 늘려둠
    timeout: int = _env("LLM_TIMEOUT", 300)
    max_retries: int = _env("LLM_MAX_RETRIES", 3)

    # ---------- 경로 ----------
    root: Path = ROOT
    raw_dir: Path = ROOT / "data" / "raw"
    wiki_dir: Path = ROOT / "data" / "wiki"
    eval_dir: Path = ROOT / "data" / "eval"
    results_dir: Path = ROOT / "results"

    # ---------- 실험 조건 ----------
    repeats: int = _env("REPEATS", 3)           # 반복 횟수 (평균·표준편차용)
    context_lengths: tuple = (4000, 8000, 16000)  # 긴 문맥 실험 조건

    # 압축률 목표 (LLMLingua 등)
    compression_rates: tuple = (0.3, 0.5, 0.7)

    def ensure_dirs(self):
        for d in (self.wiki_dir, self.eval_dir, self.results_dir):
            d.mkdir(parents=True, exist_ok=True)

    def summary(self) -> str:
        return (f"backend={self.backend} model={self.model} "
                f"ctx={self.num_ctx} temp={self.temperature} seed={self.seed}")


CFG = Config()
CFG.ensure_dirs()


if __name__ == "__main__":
    print(CFG.summary())
    print(f"루트    : {CFG.root}")
    print(f"위키    : {CFG.wiki_dir}  ({len(list(CFG.wiki_dir.rglob('*.md')))}개 문서)")
    print(f"평가셋  : {CFG.eval_dir}")
    print(f"결과    : {CFG.results_dir}")