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

토큰 수는 모두 Qwen 토크나이저 기준(config.tokenizer).
응답 캐시는 두지 않는다. 호출 기록은 호출하는 쪽의 실험 로그에 남긴다.
"""

from __future__ import annotations

import json
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

import requests

from config import CFG

# ---------------- 토큰 계산 ----------------
# 실험 모델(qwen2.5)과 같은 토크나이저로 통일. 대략치 대체 계산은 두지 않는다.

@lru_cache(maxsize=1)
def _tokenizer():
    from transformers import AutoTokenizer
    # 모델 가중치 없이 토크나이저만 받음. 리비전을 고정해 토큰 수가 재현되게 한다
    return AutoTokenizer.from_pretrained(CFG.tokenizer, revision=CFG.tokenizer_revision)


def count_tokens(text: str) -> int:
    """순수 텍스트 토큰 수 (특수 토큰 제외)."""
    return len(_tokenizer().encode(text, add_special_tokens=False))


def count_message_tokens(messages: list[dict], add_generation_prompt: bool = True) -> int:
    """채팅 템플릿(역할 태그·기본 system 포함)을 적용한 실제 입력 토큰 수.
    add_generation_prompt=True면 모델에 실제로 들어가는 assistant 시작 태그까지 센다."""
    ids = _tokenizer().apply_chat_template(
        messages, tokenize=True, add_generation_prompt=add_generation_prompt)
    if not isinstance(ids, list):   # transformers 버전에 따라 BatchEncoding으로 옴
        ids = ids["input_ids"]
    return len(ids)


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
    est_prompt_tokens: int = 0      # Qwen 토크나이저로 센 입력 토큰 (템플릿 포함)
    ctx_overflow: bool = False      # 입력이 num_ctx를 넘었는지 (Ollama는 조용히 잘라냄)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLM:
    """단일 LLM 인스턴스. 모델·백엔드를 인자로 덮어쓸 수 있다."""

    def __init__(self, model: str | None = None, backend: str | None = None,
                 base_url: str | None = None, num_ctx: int | None = None,
                 temperature: float | None = None, api_key: str | None = None,
                 timeout: int | None = None, max_tokens: int | None = None,
                 max_retries: int | None = None):
        self.backend = backend or CFG.backend
        self.model = model or CFG.model
        self.base_url = (base_url or CFG.base_url).rstrip("/")
        self.num_ctx = num_ctx or CFG.num_ctx
        self.temperature = CFG.temperature if temperature is None else temperature
        # None 일 때만 config 값을 쓴다. 빈 문자열을 넘기면 키 없이 호출 (다른 키가 섞이지 않게)
        self.api_key = CFG.api_key if api_key is None else api_key
        self.timeout = timeout or CFG.timeout
        # 출력 토큰 상한. None 이면 서버 기본값(Ollama 는 무제한). 입력+출력이
        # num_ctx 안에 들어가야 하는 호출(긴 문서 입력 등)에서 지정한다
        self.max_tokens = max_tokens
        # 실패 시 다시 보내는 횟수 (첫 호출 포함). 유료 API 는 1 로 두어 재시도 비용을 막는다
        self.max_retries = max_retries or CFG.max_retries

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
        est = count_message_tokens(messages)
        overflow = self._check_ctx(messages, est)
        res = self._call_with_retry(messages, stream_ttft)
        res.est_prompt_tokens = est
        res.ctx_overflow = overflow
        return res

    def _call_with_retry(self, messages: list[dict], stream_ttft: bool) -> LLMResult:
        for attempt in range(self.max_retries):
            try:
                if self.backend == "ollama":
                    return self._ollama_chat(messages, stream_ttft)
                return self._openai_chat(messages, stream_ttft)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"  [재시도 {attempt + 1}/{self.max_retries}] {type(e).__name__}: {e} ({wait}초 후)")
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def _check_ctx(self, messages: list[dict], est: int) -> bool:
        """입력이 num_ctx를 넘으면 경고하고 results/ctx_overflow.jsonl 에 기록.
        Ollama는 넘친 앞부분을 에러 없이 잘라내므로 여기서 잡아야 한다."""
        if self.backend != "ollama" or est <= self.num_ctx:
            return False
        warnings.warn(f"입력 {est} 토큰 > num_ctx {self.num_ctx}: "
                      f"Ollama가 입력을 잘라냅니다 (model={self.model})", stacklevel=3)
        rec = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "model": self.model, "num_ctx": self.num_ctx,
            "est_prompt_tokens": est, "overflow": est - self.num_ctx,
            "head": next((m["content"][:200] for m in messages if m["role"] == "user"), ""),
        }
        with open(CFG.ctx_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True

    def embed(self, text: str) -> list[float]:
        """임베딩 벡터. 의미 손실률 계산에 사용.
        Ollama 기본값은 입력을 2048 토큰에서 조용히 잘라내므로, 모델 한도(embed_ctx)까지
        늘리고 truncate=False 로 넘치면 오류(HTTP 400)를 내게 한다. 긴 문맥은 호출하는 쪽에서 나눈다."""
        if self.backend == "ollama":
            r = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": CFG.embed_model, "input": text, "truncate": False,
                      "options": {"num_ctx": CFG.embed_ctx, "num_batch": CFG.embed_ctx}},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["embeddings"][0]

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
        if self.max_tokens is not None:
            payload["options"]["num_predict"] = self.max_tokens
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
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
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
            # 스트리밍 응답에 usage를 안 주는 서버가 있어 Qwen 토크나이저로 보완
            prompt_tokens=usage.get("prompt_tokens", 0) or count_message_tokens(messages),
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
    print(f"입력 {res.prompt_tokens} (Qwen 토크나이저 {res.est_prompt_tokens}) "
          f"/ 출력 {res.completion_tokens} 토큰")
    print(f"소요 {res.latency:.2f}초", end="")
    print(f" (첫 토큰 {res.ttft:.2f}초)" if res.ttft else "")

    try:
        v = llm.embed("hello world")
        print(f"임베딩 차원: {len(v)}  (모델: {CFG.embed_model})")
    except Exception as e:
        print(f"임베딩 실패: {e}\n  -> ollama pull {CFG.embed_model} 확인")