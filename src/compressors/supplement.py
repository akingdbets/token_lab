"""
고정 앞부분 + 질문별 보충 (sup_*)

    1. 질문을 보지 않고 sentence_select 로 문서를 압축한다 (sent_{보호 수준}_r{남길 비율} 과 같은 결과)
    2. 그때 지운 문장·목록 항목 중에서만, 그 턴의 질문과 단어 일치 점수가 높은 상위 k개를 고른다
    3. 고른 단위를 원문 글자 그대로 문맥 맨 끝에 덧붙인다 (원래 문서 순서로, 출처 문서 이름과 함께)

압축본(1)은 질문과 무관해 질문이 바뀌어도 글자 하나 다르지 않다. 바뀌는 건 끝에 붙는 보충뿐이라
system + 압축본까지가 고정 앞부분으로 프롬프트 캐시에 남는다 (멀티턴·같은 문서를 쓰는 여러 질문).
답변 프롬프트는 <documentation>{context}</documentation> 다음에 질문이 오므로 보충은 질문 바로 앞에 놓인다.

feature/question-guided-repair-v1 (PR #57, llmlingua2_repair_v1) 과 같은 생각을 더 단순하게 한 것이다.
    repair_v1  LLMLingua-2 토큰 압축 → 관련 상위 3문장의 압축 구간을 SequenceMatcher 로 찾아 임베딩 유사도로
               손상을 판정 → 손상된 문장만 제자리에 원문으로 되돌린다
    sup_*      문장 단위로 지웠으므로 어떤 문장이 빠졌는지 정확히 안다. 대응 찾기·임베딩 판정이 필요 없고,
               남은 문장은 이미 원문 그대로라 지워진 문장만 되살리면 된다. 제자리 대신 끝에 붙여 앞부분을 지킨다

점수 (compressors/lexical.py)
    bm25   BM25, 식별자 조각까지 센다
    wcos   단어 빈도 코사인 (repair_v1 의 relevance() 와 같은 계산). 두 점수를 dev 에서 비교해 하나만 남긴다

이름: sup_{bm25|wcos}_{loose|structure}_r{남길 비율}_k{보충 개수}, 예: "rule>sup_bm25_loose_r70_k3"
"""

from __future__ import annotations

from compressors.lexical import SCORERS
from compressors.sentence_select import DroppedUnit, SentenceSelectCompressor

POLICY_VERSION = "supplement-v1"
SUPPLEMENT_HEADER = "## Restored sentences (omitted above, relevant to the question)"


def format_supplement(units: list[DroppedUnit]) -> str:
    lines = [SUPPLEMENT_HEADER]
    for u in units:
        lines.append(f"- [{u.source}] {u.text}" if u.source else f"- {u.text}")
    return "\n".join(lines) + "\n"


class SupplementCompressor(SentenceSelectCompressor):
    """질문을 보지 않는 문장 선택 압축본 뒤에, 지운 문장 중 질문 관련 상위 k개를 덧붙인다."""

    def __init__(
        self,
        *,
        query_scorer: str = "bm25",
        top_k: int = 3,
        keep_ratio: float = 0.7,
        protect: str = "loose",
        name: str | None = None,
        **kwargs,
    ):
        if query_scorer not in SCORERS:
            raise ValueError(f"query_scorer는 {sorted(SCORERS)} 중 하나여야 합니다")
        if top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다")
        super().__init__(keep_ratio=keep_ratio, protect=protect, **kwargs)
        self.query_scorer = query_scorer
        self.top_k = int(top_k)
        self.name = name or f"sup_{query_scorer}_{protect}_r{round(self.keep_ratio * 100):02d}_k{self.top_k}"

    def config(self) -> dict:
        cfg = super().config()
        cfg.update(
            method="supplement",
            policy_version=POLICY_VERSION,
            base_policy_version=cfg["policy_version"],     # update 전 값: sentence_select 의 것
            base_scorer=cfg["scorer"],
            query_scorer=self.query_scorer,
            top_k=self.top_k,
            supplement_header=SUPPLEMENT_HEADER,
            uses_question=True,          # 보충만 질문을 본다. 앞부분(압축본)은 질문과 무관하다
        )
        return cfg

    def _extra_info(self) -> dict:
        return {"method": "supplement", "policy_version": POLICY_VERSION, "uses_question": True,
                "query_scorer": self.query_scorer, "top_k": self.top_k}

    def select_supplement(self, question: str, dropped: list[DroppedUnit]) -> list[tuple[float, DroppedUnit]]:
        """지운 단위 중 점수 > 0 인 상위 top_k (점수 높은 순, 같으면 앞 단위 먼저)."""
        if not dropped:
            return []
        scores = SCORERS[self.query_scorer](question, [u.text for u in dropped])
        ranked = sorted(zip(scores, range(len(dropped))), key=lambda p: (-p[0], p[1]))
        return [(score, dropped[i]) for score, i in ranked[: self.top_k] if score > 0]

    def compress_context(self, question: str, context: str) -> str:
        base = super().compress_context(question, context)   # 질문을 쓰지 않는 _score_candidates 그대로
        picked = self.select_supplement(question, self._dropped)
        if not picked:
            self.add_info(base_chars=len(base), supplement_units=0, supplement_chars=0, supplement=[])
            return base
        units = sorted((u for _, u in picked), key=lambda u: (u.doc_index, u.unit_index))
        block = format_supplement(units)
        result = base + ("" if base.endswith("\n\n") else "\n" if base.endswith("\n") else "\n\n") + block
        self.add_info(
            base_chars=len(base),
            supplement_units=len(units),
            supplement_chars=len(result) - len(base),
            supplement=[{"source": u.source, "doc_index": u.doc_index, "unit_index": u.unit_index,
                         "score": round(score, 4), "text": u.text} for score, u in picked],
            output_chars=len(result),
        )
        return result
