"""가능성 측정 공통 코드 (기존 모듈은 import 만 한다).

대화 기록 가정: [system] + 턴 0..k-1 의 {user: mt_answer_v2 user_message, assistant: 시나리오 정답(answer)}.
실험의 reference 궤적 대신 정답 텍스트를 assistant 응답으로 쓴다 (길이·내용이 비슷하다고 가정).
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from corpus import load_corpus  # noqa: E402
from llm import count_tokens  # noqa: E402
from multiturn.history_compressors.base import split_turns  # noqa: E402
from multiturn.history_compressors.budget import question_of, history_tokens  # noqa: E402
from multiturn.prompt import load_mt_prompt  # noqa: E402

DATA = ROOT / "data/evalsets/multiturn-v2"
SAMPLES = ["v2_01_auth_switch", "v2_02_response_design"]
OUT = ROOT / "results" / "feasibility"   # 큰 중간 결과 (git 제외). 커밋한 요약은 같은 폴더의 results/
OUT.mkdir(parents=True, exist_ok=True)
RATIOS = (0.25, 0.5, 0.75)
CHECK_TYPES = ("recall", "synthesis")

_corpus = None
_prompt = None


def env():
    global _corpus, _prompt
    if _corpus is None:
        _corpus = load_corpus()
        _prompt = load_mt_prompt("v2")
    return _corpus, _prompt


def load_scenario(sid: str) -> dict:
    return json.loads((DATA / f"{sid}.json").read_text(encoding="utf-8"))


def history_and_current(scn: dict, k: int):
    """턴 k 직전까지 과거 기록(system 제외)과 현재 사용자 메시지."""
    corpus, prompt = env()
    past = []
    for t in scn["turns"][:k]:
        past.append({"role": "user", "content": prompt.user_message(t, corpus)})
        past.append({"role": "assistant", "content": t["answer"]})
    return past, prompt.user_message(scn["turns"][k], corpus)


def prev_questions(scn: dict, k: int, n: int) -> list[str]:
    return [scn["turns"][j]["question"] for j in range(max(0, k - n), k)]


# ---------------- 근거 인용 잔존 검사 ----------------

_W = re.compile(r"[A-Za-z0-9_]+")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def words(s: str) -> list[str]:
    return [w.lower() for w in _W.findall(s)]


def coverage(quote: str, text_words: list[str], index: dict) -> float:
    """인용 단어가 압축 결과에 순서대로 남은 비율 (인용 길이 3배 창 안에서 최대값)."""
    q = words(quote)
    if not q:
        return 1.0
    best = 0
    win = 3 * len(q) + 5
    starts = set()
    for w in set(q[:3]):
        starts.update(index.get(w, ()))
    for i in starts:
        j, m = 0, 0
        for w in text_words[i:i + win]:
            if j < len(q) and w == q[j]:
                j += 1
                m += 1
            elif j < len(q) - 1 and w == q[j + 1]:   # 한 단어 빠진 경우 건너뛴다
                j += 2
                m += 1
        best = max(best, m)
        if best == len(q):
            break
    return best / len(q)


def word_index(ws: list[str]) -> dict:
    idx: dict[str, list[int]] = {}
    for i, w in enumerate(ws):
        idx.setdefault(w, []).append(i)
    return idx


def evidence_checks(scn: dict, k: int, raw_text: str, comp_text: str) -> list[dict]:
    """과거 기록에 있어야 할 근거 인용(사용자 발화 user_turn<k, 문서 페이지)이 압축 결과에 남았는지."""
    raw_n, comp_n = norm(raw_text), norm(comp_text)
    cw = words(comp_text)
    ci = word_index(cw)
    out = []
    for e in scn["turns"][k]["evidence"]:
        if "user_turn" in e and e["user_turn"] >= k:
            continue
        qn = norm(e["quote"])
        in_raw = qn in raw_n
        out.append({"quote": e["quote"][:60], "src": "user" if "user_turn" in e else "doc",
                    "in_raw": in_raw, "exact": qn in comp_n, "cov": round(coverage(e["quote"], cw, ci), 3)})
    return out


def text_of(msgs: list[dict]) -> str:
    return "\n".join(m["content"] for m in msgs if m["role"] != "system")


def check_turns(scn: dict) -> list[int]:
    return [t["turn"] for t in scn["turns"] if t["turn_type"] in CHECK_TYPES]


# ---------------- 메모리 측정 ----------------

class PeakRSS:
    def __init__(self, interval=0.1):
        import psutil
        self.p = psutil.Process()
        self.interval = interval
        self.peak = self.p.memory_info().rss
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop:
            self.peak = max(self.peak, self.p.memory_info().rss)
            time.sleep(self.interval)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop = True
        self._t.join()

    def reset(self):
        self.peak = self.p.memory_info().rss


def gb(b):
    return round(b / 2**30, 2)
