"""
LLM 호출 모듈

백엔드를 바꿔 끼울 수 있는 구조.
  - Ollama (기본)
  - OpenAI 호환 서버 (LM Studio, vLLM, 상용 API)

사용 예
    from llm import LLM, count_tokens

    llm = LLM()                      # config.py 설정 사용 (답변 모델)
    judge = LLM(role="judge")        # 채점 모델 접속 정보 (JUDGE_*)
    answer = llm.ask("파이썬이 뭐야?")
    print(count_tokens(answer))

count_tokens / count_message_tokens 는 config.tokenizer 기준 (hf:<저장소> 또는 tiktoken:<인코딩>).
LLMResult 의 prompt_tokens / completion_tokens 는 서버가 보고한 값(usage_source="api")이고,
서버가 보고하지 않았을 때만 config.tokenizer 추정치로 채운다(usage_source="estimate").
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

from config import CFG, tokenizer_kind

# ---------------- 토큰 계산 ----------------
# 답변 모델과 같은 토크나이저로 센다 (config.tokenizer). 대략치 대체 계산은 두지 않는다.
# tiktoken 은 채팅 템플릿이 공개돼 있지 않아 메시지마다 고정 오버헤드를 더하는 근사치다.

# OpenAI 채팅 메시지 오버헤드 (OpenAI cookbook 기준): 메시지당 3, 답변 시작 3
_TIKTOKEN_PER_MESSAGE = 3
_TIKTOKEN_REPLY_PRIMING = 3


@lru_cache(maxsize=1)
def _tokenizer():
    kind, name = tokenizer_kind(CFG.tokenizer)
    if kind == "tiktoken":
        import tiktoken
        return tiktoken.get_encoding(name)
    from transformers import AutoTokenizer
    # 모델 가중치 없이 토크나이저만 받음. 리비전을 고정해 토큰 수가 재현되게 한다
    return AutoTokenizer.from_pretrained(name, revision=CFG.tokenizer_revision)


def _is_tiktoken() -> bool:
    return tokenizer_kind(CFG.tokenizer)[0] == "tiktoken"


def count_tokens(text: str) -> int:
    """순수 텍스트 토큰 수 (특수 토큰 제외)."""
    if _is_tiktoken():
        return len(_tokenizer().encode(text, disallowed_special=()))
    return len(_tokenizer().encode(text, add_special_tokens=False))


def count_message_tokens(messages: list[dict], add_generation_prompt: bool = True) -> int:
    """채팅 템플릿(역할 태그·기본 system 포함)을 적용한 실제 입력 토큰 수.
    add_generation_prompt=True면 모델에 실제로 들어가는 assistant 시작 태그까지 센다.
    tiktoken 이면 메시지당 오버헤드를 더한 근사치."""
    if _is_tiktoken():
        n = sum(_TIKTOKEN_PER_MESSAGE + count_tokens(m["role"]) + count_tokens(m["content"])
                for m in messages)
        return n + (_TIKTOKEN_REPLY_PRIMING if add_generation_prompt else 0)
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
    finish_reason: str | None = None   # stop | length(출력 상한에 걸려 잘림) ... 서버가 안 주면 None
    temperature: float | None = None   # 실제로 보낸 값. None 이면 안 보냄 (서버 기본값, 예: gpt-6 계열은 1)
    usage_source: str = "api"       # api: 서버 보고값 | estimate: 서버가 안 줘서 config.tokenizer 로 추정
    est_prompt_tokens: int = 0      # config.tokenizer 로 센 입력 토큰 (템플릿 포함)
    ctx_overflow: bool = False      # 입력이 num_ctx를 넘었는지 (Ollama는 조용히 잘라냄)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLM:
    """단일 LLM 인스턴스. 모델·백엔드를 인자로 덮어쓸 수 있다.

    role 은 접속 정보(backend, base_url, api_key)와 기본 모델을 고른다:
        answer (기본)  ANSWER_* / LLM_*, 모델 CFG.model
        judge          JUDGE_*  / LLM_*, 모델 CFG.judge_model
        embed          EMBED_*  / LLM_*, 임베딩 전용 (embed 메서드, 모델 CFG.embed_model)
    """

    def __init__(self, model: str | None = None, backend: str | None = None,
                 base_url: str | None = None, num_ctx: int | None = None,
                 temperature: float | None = None, api_key: str | None = None,
                 timeout: int | None = None, max_tokens: int | None = None,
                 max_retries: int | None = None, role: str = "answer"):
        ep = CFG.endpoint(role)
        self.role = role
        self.backend = backend or ep["backend"]
        self.model = model or (CFG.judge_model if role == "judge" else CFG.model)
        self.base_url = (base_url or ep["base_url"]).rstrip("/")
        self.num_ctx = num_ctx or CFG.num_ctx
        self.temperature = CFG.temperature if temperature is None else temperature
        # None 일 때만 config 값을 쓴다. 빈 문자열을 넘기면 키 없이 호출 (다른 키가 섞이지 않게)
        self.api_key = ep["api_key"] if api_key is None else api_key
        self.timeout = timeout or CFG.timeout
        # 출력 토큰 상한. None 이면 서버 기본값(Ollama 는 무제한). 입력+출력이
        # num_ctx 안에 들어가야 하는 호출(긴 문서 입력 등)에서 지정한다
        self.max_tokens = max_tokens
        # 실패 시 다시 보내는 횟수 (첫 호출 포함). 유료 API 는 1 로 두어 재시도 비용을 막는다
        self.max_retries = max_retries or CFG.max_retries
        # OpenAI 호환 서버가 거부한 요청 인자 (_openai_chat 이 400 응답을 보고 채운다).
        #   "temperature" -> 보내지 않음 (서버 기본값)
        #   "max_tokens"  -> max_completion_tokens 로 보냄
        self.unsupported: set[str] = set()

    def sampling_info(self) -> dict:
        """결과 파일에 남길 실제 생성 조건. 서버가 거부해 바꾼 인자가 있으면 그대로 드러난다."""
        return {
            "model": self.model,
            "temperature": self._sent_temperature(),   # None = 보내지 않음 (서버 기본값)
            "temperature_requested": self.temperature,
            "max_tokens": self.max_tokens,
            "max_tokens_param": ("num_predict" if self.backend == "ollama" else
                                 "max_completion_tokens" if "max_tokens" in self.unsupported
                                 else "max_tokens"),
        }

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
                # 4xx(429 제외)는 다시 보내도 같은 결과라 바로 올린다
                status = getattr(getattr(e, "response", None), "status_code", None)
                if attempt == self.max_retries - 1 or (
                        isinstance(status, int) and 400 <= status < 500 and status != 429):
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
                finish_reason=d.get("done_reason"),
                temperature=self.temperature,
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
            finish_reason=last.get("done_reason"),
            temperature=self.temperature,
        )

    def _openai_payload(self, messages: list[dict], stream: bool) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": stream}
        if "temperature" not in self.unsupported:
            payload["temperature"] = self.temperature
        if stream:
            # OpenAI 는 이 옵션이 있어야 스트리밍 마지막 청크에 usage 를 보낸다
            payload["stream_options"] = {"include_usage": True}
        if self.max_tokens is not None:
            key = "max_completion_tokens" if "max_tokens" in self.unsupported else "max_tokens"
            payload[key] = self.max_tokens
        return payload

    def _learn_unsupported(self, r) -> bool:
        """400 응답이 temperature / max_tokens 를 거부한 것이면 기억하고 True (다시 보낼 것).
        예: gpt-6 계열은 temperature 기본값(1)만 받고, max_tokens 대신 max_completion_tokens 를 쓴다."""
        if r.status_code != 400:
            return False
        try:
            err = r.json().get("error") or {}
        except ValueError:
            return False
        param = err.get("param")
        if param not in ("temperature", "max_tokens") or param in self.unsupported:
            return False
        if param == "max_tokens" and self.max_tokens is None:
            return False
        self.unsupported.add(param)
        how = ("보내지 않고 서버 기본값을 씁니다" if param == "temperature"
               else "max_completion_tokens 로 보냅니다")
        warnings.warn(f"{self.model} 가 {param} 를 거부해 {how}: {err.get('message', '')}",
                      stacklevel=4)
        return True

    def _openai_post(self, url: str, messages: list[dict], stream: bool):
        """요청을 보내고 응답을 돌려준다. 서버가 거부한 인자는 바꿔서 다시 보낸다 (400 은 과금되지 않음).
        실패하면 서버의 오류 메시지를 담은 HTTPError 를 낸다."""
        while True:
            r = requests.post(url, headers=self._headers(), json=self._openai_payload(messages, stream),
                              stream=stream, timeout=self.timeout)
            if r.ok:
                return r
            if self._learn_unsupported(r):
                r.close()
                continue
            body = r.text[:500]
            r.close()
            raise requests.HTTPError(f"{r.status_code} {url}: {body}", response=r)

    def _openai_chat(self, messages: list[dict], stream_ttft: bool) -> LLMResult:
        """LM Studio, vLLM, OpenAI 등 /v1/chat/completions 호환 서버."""
        url = f"{self.base_url}/v1/chat/completions"
        t0 = time.perf_counter()

        if not stream_ttft:
            r = self._openai_post(url, messages, stream=False)
            d = r.json()
            text = d["choices"][0]["message"]["content"] or ""
            pt, ct, source = _usage_or_estimate(d.get("usage"), messages, text, self.model)
            return LLMResult(
                text=text,
                prompt_tokens=pt,
                completion_tokens=ct,
                latency=time.perf_counter() - t0,
                model=d.get("model") or self.model,
                raw=d,
                finish_reason=d["choices"][0].get("finish_reason"),
                temperature=self._sent_temperature(),
                usage_source=source,
            )

        chunks, ttft, usage, served_model, finish = [], None, {}, None, None
        with self._openai_post(url, messages, stream=True) as r:
            for line in r.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue
                body = line[6:]
                if body.strip() == b"[DONE]":
                    break
                d = json.loads(body)
                if d.get("usage"):
                    usage = d["usage"]
                if d.get("model"):
                    served_model = d["model"]
                if not d.get("choices"):   # include_usage 의 마지막 청크는 choices 가 비어 있다
                    continue
                finish = d["choices"][0].get("finish_reason") or finish
                piece = d["choices"][0].get("delta", {}).get("content") or ""
                if piece and ttft is None:
                    ttft = time.perf_counter() - t0
                chunks.append(piece)
        text = "".join(chunks)
        pt, ct, source = _usage_or_estimate(usage, messages, text, self.model)
        return LLMResult(
            text=text,
            prompt_tokens=pt,
            completion_tokens=ct,
            latency=time.perf_counter() - t0,
            ttft=ttft,
            model=served_model or self.model,
            finish_reason=finish,
            temperature=self._sent_temperature(),
            usage_source=source,
        )

    def _sent_temperature(self) -> float | None:
        return None if "temperature" in self.unsupported else self.temperature


def _usage_or_estimate(usage: dict | None, messages: list[dict], text: str,
                       model: str) -> tuple[int, int, str]:
    """서버 usage -> (입력, 출력, 출처). 없으면 config.tokenizer 로 추정하고 경고한다.
    추정치는 서버 토크나이저와 단위가 다를 수 있으므로 usage_source="estimate" 로 표시한다."""
    usage = usage or {}
    if usage.get("prompt_tokens") is not None and usage.get("completion_tokens") is not None:
        return int(usage["prompt_tokens"]), int(usage["completion_tokens"]), "api"
    warnings.warn(f"서버가 usage 를 보내지 않아 {CFG.tokenizer} 로 추정합니다 (model={model})",
                  stacklevel=3)
    return count_message_tokens(messages), count_tokens(text), "estimate"


# ---------------- 연결 확인용 ----------------

if __name__ == "__main__":
    import sys

    # python src/llm.py [answer|judge]  역할별 연결 확인
    role = sys.argv[1] if len(sys.argv) > 1 else "answer"
    llm = LLM(role=role)
    print(f"role={role}  backend={llm.backend}  model={llm.model}  base_url={llm.base_url}  "
          f"tokenizer={CFG.tokenizer}")

    res = llm.ask("Reply with exactly one short sentence about FastAPI.",
                  stream_ttft=True)
    print(f"\n응답: {res.text.strip()}  (서버 모델: {res.model})")
    print(f"입력 {res.prompt_tokens} [{res.usage_source}] (토크나이저 추정 {res.est_prompt_tokens}) "
          f"/ 출력 {res.completion_tokens} 토큰")
    print(f"소요 {res.latency:.2f}초", end="")
    print(f" (첫 토큰 {res.ttft:.2f}초)" if res.ttft else "")

    try:
        v = LLM(role="embed").embed("hello world")
        print(f"임베딩 차원: {len(v)}  (모델: {CFG.embed_model})")
    except Exception as e:
        print(f"임베딩 실패: {e}\n  -> ollama pull {CFG.embed_model} 확인")