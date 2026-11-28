"""
응답 캐시 (SQLite, results/cache/responses.sqlite)

LLM 객체를 감싸 같은 요청이면 저장된 LLMResult 를 돌려준다. llm.py 내부는 건드리지 않는다.

    from llm import LLM
    from multiturn.response_cache import CachedLLM

    cached = CachedLLM(LLM())
    res, hit = cached.chat(messages, sample_idx=0)    # sample_idx 는 필수

키 = sha256(backend, base_url, model, messages 전체, 요청한 샘플링 설정, reasoning_effort, sample_idx, 포맷 버전)
    - sample_idx 가 빠지면 반복 실행 때 1회차 응답이 재사용되어 반복의 의미가 사라지므로 필수 인자로 받는다.
    - backend, base_url 도 넣는다. 같은 모델 이름이라도 제공사·엔드포인트가 다르면 다른 응답이다.
    - 샘플링 값은 "요청한" 값을 쓴다. 실제 전송값은 서버가 인자를 거부하면(400) 첫 호출 뒤에 바뀌어
      (예: temperature 0 -> 보내지 않음) 첫 호출과 이후 호출의 키가 달라지기 때문이다. 실제 전송값은 행에 따로 저장한다.
    - stream_ttft 는 응답 내용에 영향이 없어 키에 넣지 않는다.

적중하면 원래 호출의 토큰·비용 필드(created_at, latency 포함)를 그대로 돌려주고 hit=True 다.
집계할 때 hit=True 는 "실험상 비용"에는 넣고 "실제 지출"에서는 뺀다 (trajectory.summarize_steps).

RESPONSE_CACHE=off 면 캐시를 읽지도 쓰지도 않는다 (hit 는 항상 False).

스레드: 연결은 스레드마다 따로 연다 (sqlite3 연결은 스레드 간 공유 불가). 쓰기는 lock 으로 직렬화한다.
같은 키의 요청이 동시에 오면 키별 잠금으로 첫 요청만 API 를 부르고, 나머지는 기다렸다가 캐시에서 받는다 (hit=True).
예전에는 확인-후-호출 사이에 잠금이 없어 둘 다 미스로 호출하고 나중 응답이 행을 덮어썼다
(2026-11-23 run 에서 none 과 window(2) 가 같은 요청을 동시에 보내 none 행과 캐시 응답이 갈림).
이미 있는 행은 덮어쓰지 않는다 (먼저 저장된 응답 유지). 예외: 저장된 응답이 store_if 를 통과하지 못해 새로 부른 경우만 바꾼다.
키별 잠금은 한 프로세스 안에서만 작동한다. 프로세스가 여럿이면 중복 호출은 생길 수 있지만 먼저 저장된 행은 유지된다.
bind(sample_idx) 는 sample_idx 를 고정한 객체를 돌려준다. grader 처럼 llm.ask / llm.chat 을 그대로 부르는 코드에
넘길 때 쓴다 (그 객체의 chat 은 LLMResult 만 돌려주고, 적중 여부는 last_hit 에 남는다).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path

from config import CFG
from llm import LLMResult

CACHE_FORMAT_VERSION = 1
DEFAULT_PATH = CFG.results_dir / "cache" / "responses.sqlite"


# 키별 잠금: (캐시 파일, 키) 단위. 같은 파일을 쓰는 CachedLLM 객체가 여럿이어도(답변·요약·메모·judge) 공유한다
_KEY_GUARD = threading.Lock()
_KEY_LOCKS: dict[tuple[str, str], list] = {}      # (path, key) -> [Lock, 사용 중인 요청 수]


def cache_enabled() -> bool:
    return os.getenv("RESPONSE_CACHE", "on").strip().lower() not in ("off", "0", "false", "no")


def cache_key_payload(llm, messages: list[dict], sample_idx: int) -> dict:
    s = llm.sampling_info()
    return {
        "v": CACHE_FORMAT_VERSION,
        "backend": llm.backend,
        "base_url": llm.base_url,
        "model": llm.model,
        "messages": messages,
        "sampling": {
            "temperature": s["temperature_requested"],
            "seed": CFG.seed,
            "max_tokens": s["max_tokens"],
        },
        "reasoning_effort": s["reasoning_effort_requested"],
        "sample_idx": sample_idx,
    }


def cache_key(llm, messages: list[dict], sample_idx: int) -> str:
    blob = json.dumps(cache_key_payload(llm, messages, sample_idx), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _result_to_json(res: LLMResult) -> str:
    return json.dumps(asdict(res), ensure_ascii=False)


def _result_from_json(s: str) -> LLMResult:
    d = json.loads(s)
    names = {f.name for f in fields(LLMResult)}
    return LLMResult(**{k: v for k, v in d.items() if k in names})


class CachedLLM:
    """LLM 래퍼. chat() 이 (LLMResult, cache_hit) 를 돌려준다. 나머지 속성은 감싼 LLM 으로 넘긴다."""

    def __init__(self, llm, path: str | Path | None = None, enabled: bool | None = None):
        self.llm = llm
        self.path = Path(path) if path else DEFAULT_PATH
        self.enabled = cache_enabled() if enabled is None else enabled
        self._local = threading.local()
        self._lock = threading.Lock()
        self._conns: list[sqlite3.Connection] = []

    def _acquire_key(self, key: str) -> None:
        lk = (str(self.path.resolve()), key)
        with _KEY_GUARD:
            entry = _KEY_LOCKS.setdefault(lk, [threading.Lock(), 0])
            entry[1] += 1
        entry[0].acquire()

    def _release_key(self, key: str) -> None:
        lk = (str(self.path.resolve()), key)
        with _KEY_GUARD:
            entry = _KEY_LOCKS[lk]
            entry[0].release()
            entry[1] -= 1
            if entry[1] == 0:
                del _KEY_LOCKS[lk]

    def __getattr__(self, name):
        return getattr(self.llm, name)

    def _db(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # 스레드마다 자기 연결만 쓴다. close() 가 다른 스레드에서 열린 연결도 닫을 수 있게 check_same_thread=False
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            with self._lock:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS responses ("
                    " key TEXT PRIMARY KEY, backend TEXT, base_url TEXT, model TEXT, sample_idx INTEGER,"
                    " sampling_sent TEXT, result TEXT NOT NULL, stored_at TEXT NOT NULL)")
                conn.commit()
                self._conns.append(conn)
            self._local.conn = conn
        return conn

    def get(self, key: str) -> LLMResult | None:
        row = self._db().execute("SELECT result FROM responses WHERE key = ?", (key,)).fetchone()
        return _result_from_json(row[0]) if row else None

    def put(self, key: str, res: LLMResult, sample_idx: int, replace: bool = False) -> None:
        """기본은 이미 있는 행을 그대로 둔다 (INSERT OR IGNORE). replace=True 는 저장된 응답이 store_if 를 통과하지
        못해 새로 부른 경우에만 쓴다."""
        db = self._db()
        with self._lock:
            db.execute(
                f"INSERT OR {'REPLACE' if replace else 'IGNORE'} INTO responses VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (key, self.llm.backend, self.llm.base_url, self.llm.model, sample_idx,
                 json.dumps(self.llm.sampling_info(), ensure_ascii=False), _result_to_json(res),
                 datetime.now(timezone.utc).isoformat(timespec="seconds")))
            db.commit()

    def chat(self, messages: list[dict], *, sample_idx: int, stream_ttft: bool = False,
             store_if=None) -> tuple[LLMResult, bool]:
        """store_if(res) -> bool 을 주면 False 인 응답은 저장하지 않는다 (예: 빈 요약·length 잘림).
        같은 키로 다시 부르면 새로 호출되므로 재시도 때 같은 실패가 캐시에서 돌아오지 않는다.
        이전에 저장된 응답이 store_if 를 통과하지 못하면 적중으로 보지 않고 새로 호출한다."""
        if not isinstance(sample_idx, int) or isinstance(sample_idx, bool):
            raise TypeError(f"sample_idx 는 정수여야 합니다: {sample_idx!r}")
        if not self.enabled:
            return self.llm.chat(messages, stream_ttft=stream_ttft), False
        key = cache_key(self.llm, messages, sample_idx)
        self._acquire_key(key)                 # 같은 키는 한 번에 하나만: 기다린 요청은 아래 get 에서 적중한다
        try:
            hit = self.get(key)
            if hit is not None and (store_if is None or store_if(hit)):
                return hit, True
            res = self.llm.chat(messages, stream_ttft=stream_ttft)
            if store_if is None or store_if(res):
                self.put(key, res, sample_idx, replace=hit is not None)
            return res, False
        finally:
            self._release_key(key)

    def bind(self, sample_idx: int) -> "BoundCachedLLM":
        return BoundCachedLLM(self, sample_idx)

    def close(self) -> None:
        with self._lock:
            for c in self._conns:
                c.close()
            self._conns.clear()
        self._local = threading.local()


class BoundCachedLLM:
    """sample_idx 를 고정한 CachedLLM. LLM 과 같은 ask / chat 을 제공한다 (grader 에 그대로 넘길 수 있음)."""

    def __init__(self, cached: CachedLLM, sample_idx: int):
        self.cached = cached
        self.sample_idx = sample_idx
        self._local = threading.local()

    def __getattr__(self, name):
        return getattr(self.cached.llm, name)

    @property
    def last_hit(self) -> bool:
        return getattr(self._local, "hit", False)

    def chat(self, messages: list[dict], stream_ttft: bool = False) -> LLMResult:
        res, hit = self.cached.chat(messages, sample_idx=self.sample_idx, stream_ttft=stream_ttft)
        self._local.hit = hit
        return res

    def ask(self, prompt: str, system: str | None = None, stream_ttft: bool = False) -> LLMResult:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(messages, stream_ttft=stream_ttft)
