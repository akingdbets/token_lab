# claude-v1 사람 검수

## 파일

| 파일 | 내용 |
|---|---|
| `review_dev_v1.csv` | dev 35문항 검수표 (UTF-8 BOM, 엑셀에서 열기). Claude Code 사전 점검 + none 답변 |
| `review_test_v1.csv` | test 139문항 검수표 (같은 형식). 사전 점검은 key_facts 범위만, none 답변 없음 |
| `review_log_v1.jsonl` | `apply_review.py` 로 반영한 변경 기록 (반영 후 생김) |

## 검수표 열

| 열 | 내용 |
|---|---|
| `qid`, `assignee`, `type` | 문항 번호, 담당(A/B/C/D, type 이 섞이게 4등분), 유형 |
| `question`, `answer`, `key_facts`, `key_entities` | 현재 평가셋 값 (목록은 한 칸 안에서 줄바꿈으로 구분) |
| `evidence_page`, `evidence_quote` | 근거 페이지, `[페이지:줄] 인용문` |
| `none_answer`, `none_accuracy` | 원문 문맥(`none`)으로 낸 답변과 답변 정확도 (`results/runs/20261011-154540`, 답변 지시문 v1 `d12495bd1412`) |
| `ai_flag` | Claude Code 사전 점검 결과: `problem`(고쳐야 함) / `check`(사람 판단 필요) / `ok` |
| `ai_reason`, `ai_suggested_*` | 판단 이유와 수정안 (질문·정답·key_facts·key_entities, 수정안이 없으면 빈칸). `[key_facts 범위]` 로 시작하는 이유는 아래 규칙에 따른 수정안 |
| `verdict` | **검수자가 채움**: `keep` / `edit` / `delete` |
| `final_question`, `final_answer`, `final_key_facts`, `final_key_entities` | `edit` 일 때 바꿀 필드만 채움 (빈칸이면 기존 값 유지) |
| `reviewer`, `note` | 검수자 이름, 메모 |

`problem` → `check` → `ok` 순으로 정렬돼 있다. 수정안을 그대로 쓰려면 `ai_suggested_*` 를 `final_*` 로 복사한다.
질문을 고치면(`final_question`) 기존 결과는 답변부터 다시 돌려야 한다 (재실행). 정답·key_facts 만 고치면 재채점만 하면 된다.

key_facts 범위 규칙: key_facts 에는 질문이 묻는 내용만 남긴다. 질문의 전제나 질문이 묻지 않은 부가 설명은 뺀다.
fact·code 는 정답 값이 든 사실 1개, procedure·multi 는 질문이 요구하는 단계·사실만. 답변 지시문이 fact·code 에 값만 답하게 하므로,
부가 사실이 있으면 원문을 줘도 정확도가 깎인다 (`ai_flag=problem` 은 값만 답하면 0.5 이하로 묶이는 문항).
근거(evidence)는 검수표로 고치지 않는다. 필요하면 note 에 적고 평가셋을 따로 고친다.

사전 점검 기준: 질문-정답 대응(한 가지만 묻는가), 정답이 위키에 있고 정확한가, 인용이 정답을 직접 뒷받침하는가,
key_facts 가 정답과 일치하고 질문 범위를 넘거나 너무 잘게 쪼개지지 않았는가, key_entities 에 정답 값이 있고 일반 단어가 없는가,
문서 없이도 알 법한 상식이 아닌가, 질문만 보고 무엇을 묻는지 알 수 있는가.

## 반영

```bash
EVAL_DIR=data/evalsets/claude-v1 python src/apply_review.py data/evalsets/claude-v1/review/review_dev_v1.csv --dry-run
EVAL_DIR=data/evalsets/claude-v1 python src/apply_review.py data/evalsets/claude-v1/review/review_dev_v1.csv
```

- `keep` → `human_checked=True`, `edit` → 채운 필드만 교체 + `human_checked=True`,
  `delete` → 문항 제거, `qa_meta.json` 의 `deleted` 에 번호 기록 (번호 재사용 안 함)
- `verdict` 가 빈칸인 문항은 그대로 두고 목록만 출력한다
- 반영 후 split x type 문항 수와, `results/runs` 중 다시 돌려야 할 실행을 안내한다
  (질문 수정·삭제 = 재실행, 정답·key_facts 수정 = 재채점만, key_entities 수정 = 엔티티 보존율만 재계산)

## 채점 모델 비교 (2026-10-11, dev 35문항, 기존 none 답변 재채점)

| | qwen2.5:7b (현재) | qwen2.5:14b |
|---|---|---|
| 평균 답변 정확도 | 0.781 | 0.786 |
| 35문항 판정 시간 | 108초 | 253초 |
| key_facts 3개 이상 12문항 중 결과를 2개만 돌려준 문항 | 11 | 8 |
| `ai_reason` 의 judge 오판 fact 7개 중 맞힌 수 | 0 | 2 |

`none_accuracy` 와 `ai_reason` 의 "judge 오판" 대부분은 모델보다 **grader 프롬프트 문제**다. `FACT_JUDGE_PROMPT` 의 출력 예시가
index 0, 1 두 개뿐이라 judge 가 그 모양을 따라 결과를 2개만 돌려주고, 빠진 3번째 이후 fact 는 불충족으로 처리된다.
procedure·multi(key_facts 3개 이상) 정확도가 구조적으로 낮게 나오므로, 기준선 전에 grader 를 먼저 고친 뒤 판정 모델을 다시 비교한다.
