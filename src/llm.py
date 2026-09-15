"""
LLM 호출 모듈

백엔드를 바꿔 끼울 수 있는 구조.
  - Ollama (기본)
  - OpenAI 호환 서버 (LM Studio, vLLM, 상용 API)

사용 예
    from llm import LLM, count_tokens

    llm = LLM()                      # config.py 설정 사용
    answer = llm.ask("파이썬이 뭐야?")
    print(count_tokens(answer))
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import requests

from config import CFG

# ---------------- 토큰 계산 ----------------
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    def count_tokens(text: str) -> int:
        return len(text) // 4


@dataclass
class LLMResult:
    """LLM 호출 결과. 실험 로그에 그대로 기록할 수 있는 형태."""
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency: float          # 전체 소요 시간(초)
    ttft: float | None = None   # 첫 토큰까지 시간(초). 스트리밍일 때만
    model: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLM:
    """단일 LLM 인스턴스. 모델·백엔드를 인자로 덮어쓸 수 있다."""

    def __init__(self, model: str | None = None, backend: str | None = None,
                 base_url: str | None = None, num_ctx: int | None = None,
                 temperature: float | None = None, api_key: str | None = None,
                 timeout: int | None = None):
        self.backend = backend or CFG.backend
        self.model = model or CFG.model
        self.base_url = (base_url or CFG.base_url).rstrip("/")
        self.num_ctx = num_ctx or CFG.num_ctx
        self.temperature = CFG.temperature if temperature is None else temperature
        self.api_key = api_key or CFG.api_key
        self.timeout = timeout or CFG.timeout

    # ---------------- 공개 메서드 ----------------

    def ask(self, prompt: str, system: str | None = None, stream_ttft: bool = False) -> LLMResult:
        """프롬프트를 보내고 결과를 받는다."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, stream_ttft=stream_ttft)

    def chat(self, messages: list[dict], stream_ttft: bool = False) -> LLMResult:
        """멀티턴 대화용. messages = [{"role": ..., "content": ...}, ...]"""
        for attempt in range(CFG.max_retries):
            try:
                if self.backend == "ollama":
                    return self._ollama_chat(messages, stream_ttft)
                return self._openai_chat(messages, stream_ttft)
            except Exception as e:
                if attempt == CFG.max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"  [재시도 {attempt + 1}/{CFG.max_retries}] {type(e).__name__}: {e} ({wait}초 후)")
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def embed(self, text: str) -> list[float]:
        """임베딩 벡터. 의미 손실률 계산에 사용."""
        if self.backend == "ollama":
            r = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": CFG.embed_model, "prompt": text},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["embedding"]

        r = requests.post(
            f"{self.base_url}/v1/embeddings",
            headers=self._headers(),
            json={"model": CFG.embed_model, "input": text},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]

    # ---------------- 백엔드별 구현 ----------------

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _ollama_chat(self, messages: list[dict], stream_ttft: bool) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream_ttft,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,      # 기본 4096이라 반드시 지정
                "seed": CFG.seed,
            },
        }
        url = f"{self.base_url}/api/chat"
        t0 = time.perf_counter()

        if not stream_ttft:
            r = requests.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            d = r.json()
            return LLMResult(
                text=d["message"]["content"],
                prompt_tokens=d.get("prompt_eval_count", 0),
                completion_tokens=d.get("eval_count", 0),
                latency=time.perf_counter() - t0,
                model=self.model,
                raw=d,
            )

        # 스트리밍: 첫 토큰 도착 시각(TTFT)을 재기 위함
        chunks, ttft, last = [], None, {}
        with requests.post(url, json=payload, stream=True, timeout=self.timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                piece = d.get("message", {}).get("content", "")
                if piece and ttft is None:
                    ttft = time.perf_counter() - t0
                chunks.append(piece)
                if d.get("done"):
                    last = d
        return LLMResult(
            text="".join(chunks),
            prompt_tokens=last.get("prompt_eval_count", 0),
            completion_tokens=last.get("eval_count", 0),
            latency=time.perf_counter() - t0,
            ttft=ttft,
            model=self.model,
            raw=last,
        )

    def _openai_chat(self, messages: list[dict], stream_ttft: bool) -> LLMResult:
        """LM Studio, vLLM, OpenAI 등 /v1/chat/completions 호환 서버."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": stream_ttft,
        }
        url = f"{self.base_url}/v1/chat/completions"
        t0 = time.perf_counter()

        if not stream_ttft:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            r.raise_for_status()
            d = r.json()
            usage = d.get("usage", {})
            return LLMResult(
                text=d["choices"][0]["message"]["content"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency=time.perf_counter() - t0,
                model=self.model,
                raw=d,
            )

        chunks, ttft, usage = [], None, {}
        with requests.post(url, headers=self._headers(), json=payload,
                           stream=True, timeout=self.timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue
                body = line[6:]
                if body.strip() == b"[DONE]":
                    break
                d = json.loads(body)
                if d.get("usage"):
                    usage = d["usage"]
                delta = d["choices"][0].get("delta", {})
                piece = delta.get("content", "")
                if piece and ttft is None:
                    ttft = time.perf_counter() - t0
                chunks.append(piece)
        text = "".join(chunks)
        return LLMResult(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0) or count_tokens(text),
            latency=time.perf_counter() - t0,
            ttft=ttft,
            model=self.model,
        )


# ---------------- 연결 확인용 ----------------

if __name__ == "__main__":
    print(f"backend={CFG.backend}  model={CFG.model}  ctx={CFG.num_ctx}")

    llm = LLM()
    res = llm.ask("Reply with exactly one short sentence about FastAPI.",
                  stream_ttft=True)
    print(f"\n응답: {res.text.strip()}")
    print(f"입력 {res.prompt_tokens} / 출력 {res.completion_tokens} 토큰")
    print(f"소요 {res.latency:.2f}초", end="")
    print(f" (첫 토큰 {res.ttft:.2f}초)" if res.ttft else "")

    try:
        v = llm.embed("hello world")
        print(f"임베딩 차원: {len(v)}  (모델: {CFG.embed_model})")
    except Exception as e:
        print(f"임베딩 실패: {e}\n  -> ollama pull {CFG.embed_model} 확인")