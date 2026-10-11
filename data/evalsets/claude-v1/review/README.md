# claude-v1 사람 검수

## 파일

| 파일 | 내용 |
|---|---|
| `review_dev_v1.csv` | dev 35문항 검수표 (UTF-8 BOM, 엑셀에서 열기). Claude Code 사전 점검 + none 답변 |
| `review_log_v1.jsonl` | `apply_review.py` 로 반영한 변경 기록 (반영 후 생김) |

## 검수표 열

| 열 | 내용 |
|---|---|
| `qid`, `assignee`, `type` | 문항 번호, 담당(A/B/C/D, type 이 섞이게 4등분), 유형 |
| `question`, `answer`, `key_facts`, `key_entities` | 현재 평가셋 값 (목록은 한 칸 안에서 줄바꿈으로 구분) |
| `evidence_page`, `evidence_quote` | 근거 페이지, `[페이지:줄] 인용문` |
| `none_answer`, `none_accuracy` | 원문 문맥(`none`)으로 낸 답변과 답변 정확도 (`results/runs/20261011-154540`, 답변 지시문 v1 `d12495bd1412`) |
| `ai_flag` | Claude Code 사전 점검 결과: `problem`(고쳐야 함) / `check`(사람 판단 필요) / `ok` |
| `ai_reason`, `ai_suggested_*` | 판단 이유와 수정안 (수정안이 없으면 빈칸) |
| `verdict` | **검수자가 채움**: `keep` / `edit` / `delete` |
| `final_answer`, `final_key_facts`, `final_key_entities` | `edit` 일 때 바꿀 필드만 채움 (빈칸이면 기존 값 유지) |
| `reviewer`, `note` | 검수자 이름, 메모 |

`problem` → `check` → `ok` 순으로 정렬돼 있다. 수정안을 그대로 쓰려면 `ai_suggested_*` 를 `final_*` 로 복사한다.
질문을 고치려면 `final_question` 열을 직접 추가해서 채운다 (질문 수정은 기존 결과를 재실행해야 한다).
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
