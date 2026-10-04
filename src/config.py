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
    # 토큰 계산 기준. 모델 가중치 없이 토크나이저만 내려받는다
    tokenizer: str = _env("TOKENIZER", "Qwen/Qwen2.5-7B-Instruct")
    # 토크나이저 리비전(허깅페이스 커밋 해시) 고정. 저장소가 갱신돼도 토큰 수가 바뀌지 않게 한다
    tokenizer_revision: str = _env("TOKENIZER_REVISION", "a09a35458c702b33eeacc393d103063234e8bc28")

    # ---------- 생성 조건 (실험 통제) ----------
    temperature: float = _env("LLM_TEMPERATURE", 0.0)
    seed: int = _env("LLM_SEED", 42)
    num_ctx: int = _env("LLM_NUM_CTX", 16384)   # Ollama 기본 4096 -> 늘려둠
    timeout: int = _env("LLM_TIMEOUT", 300)
    max_retries: int = _env("LLM_MAX_RETRIES", 3)

    # ---------- 경로 ----------
    root: Path = ROOT
    raw_dir: Path = ROOT / "data" / "raw"
    # OpenWiki 로 생성한 위키 (openwiki/ 폴더를 그대로 복사). 실험 입력이므로 생성 후 고정
    openwiki_dir: Path = ROOT / "data" / "openwiki"
    eval_dir: Path = ROOT / "data" / "eval"
    results_dir: Path = ROOT / "results"
    # FastAPI 저장소 스냅샷 루트 (docs/en 이 있는 곳). 연구 기간 내내 고정
    raw_repo: Path = ROOT / "data" / "raw" / "fastapi"
    corpus_manifest: Path = ROOT / "data" / "corpus_manifest.jsonl"
    index_dir: Path = ROOT / "data" / "index"        # 탐색용 인덱스 변형들 ({이름}.md)
    ctx_log_path: Path = ROOT / "results" / "ctx_overflow.jsonl"   # num_ctx 초과 기록

    # ---------- 실험 조건 ----------
    repeats: int = _env("REPEATS", 1)           # 반복 횟수 (평균·표준편차용)
    context_lengths: tuple = (4000, 8000, 16000)  # 긴 문맥 실험 조건

    # 압축률 목표 (LLMLingua 등)
    compression_rates: tuple = (0.3, 0.5, 0.7)

    # ---------- 코퍼스 범위 ----------
    # 문서: docs/en/docs/**/*.md 중 아래 corpus_exclude 를 뺀 것
    # 코드: docs_src 폴더 전체(**/*.py) + 코퍼스 문서가 {* ... *} 로 참조하는 그 외 파일
    #       (예: fastapi/openapi/docs.py). 참조의 ln[...] 줄 범위는 펼칠 때만 적용하고
    #       코드 문서 자체는 파일 전체를 원문 그대로 갖는다.
    # 아래는 기술 설명이 아닌 페이지. docs/en/docs 기준 경로, "/"로 끝나면 폴더 전체
    corpus_exclude: tuple = (
        "release-notes.md", "newsletter.md", "help-fastapi.md", "contributing.md",
        "benchmarks.md", "history-design-future.md", "external-links.md",
        "fastapi-people.md", "project-generation.md", "management.md",
        "management-tasks.md", "alternatives.md", "resources/",
        "about/", "learn/",
        "reference/",       # 대부분 ::: fastapi.X 자동 생성 구문이라 본문이 거의 없음
        "_llm-test.md", "translations.md", "translation-banner.md",   # 번역 작업용
        "environment-variables.md", "virtual-environments.md",   # 일반 파이썬 환경 안내, nav 에 없음
    )

    def ensure_dirs(self):
        for d in (self.eval_dir, self.results_dir):
            d.mkdir(parents=True, exist_ok=True)

    def summary(self) -> str:
        return (f"backend={self.backend} model={self.model} "
                f"ctx={self.num_ctx} temp={self.temperature} seed={self.seed}")


CFG = Config()
CFG.ensure_dirs()


if __name__ == "__main__":
    print(CFG.summary())
    print(f"루트    : {CFG.root}")
    print(f"위키    : {CFG.openwiki_dir}  ({len(list(CFG.openwiki_dir.rglob('*.md')))}개 문서)")
    print(f"평가셋  : {CFG.eval_dir}")
    print(f"결과    : {CFG.results_dir}")