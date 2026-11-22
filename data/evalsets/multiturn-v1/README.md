# multiturn-v1 (파일럿, 검수 전 초안)

멀티턴 replay 실험용 시나리오. 시나리오 하나 = JSON 파일 하나. 모두 `status: "draft"` 다 (사람 검수 전).
API 키가 없는 상태에서 직접 작성했고, 근거는 아래 "검사" 로 코퍼스에서 확인했다.

| 파일 | 주제 | 턴 | new / followup / recall / synthesis | 근거 페이지 |
|---|---|---|---|---|
| `mt01_security.json` | OAuth2 password flow → JWT → scopes | 9 | 3 / 2 / 2 / 2 | security/oauth2-password-flow.md, oauth2-jwt.md, oauth2-scopes.md |
| `mt02_dependencies.json` | yield 의존성 → background tasks → CORS | 9 | 3 / 2 / 2 / 2 | dependencies/dependencies-with-yield.md, integrations/background-tasks.md, middleware/cors.md |
| `mt03_responses.json` | status codes → headers·cookies → errors | 9 | 3 / 2 / 2 / 2 | responses/status-codes.md, responses/response-headers-and-cookies.md, errors/handling-errors.md |

## 스키마

```
scenario_id, title, topic, status ("draft" | "reviewed")
turns[]:
  turn            0 부터 순서대로
  turn_type       new | followup | recall | synthesis
  type            fact | code | procedure | multi | default   답변 형식 줄 (싱글턴 answer_v1 의 format 과 같음)
  question, answer, key_facts, key_entities                   싱글턴 평가셋과 같은 의미
  evidence_pages  이 턴 사용자 메시지에 첨부할 위키 페이지 (없으면 [])
  depends_on      답하려면 필요한 이전 턴 번호 (현재·미래 턴 금지)
  evidence        [{quote, page, fact_idx}]  key_fact 마다 근거 인용문 1개 이상. 메시지에는 넣지 않는다 (검사용)
```

- `new`: 새 문서 첨부. `followup`: 앞 턴 내용을 이어 묻기(문서 재첨부 없음). `recall`: 문서 재첨부 없이 몇 턴 전 문서·답변 내용을 다시 물음. `synthesis`: 여러 턴 종합 (이전 턴 2개 이상에 의존).
- recall 과 synthesis 가 압축 손실을 드러내는 핵심 문항이다. 시나리오마다 최소 2개씩 둔다 (`validate_scenario` 가 검사).
- 문맥 구성: 턴의 `evidence_pages` 원문을 그 턴 사용자 메시지에 붙인다. 그래서 기록에 문서와 답변이 누적된다 (RAG 챗봇과 같은 구조).

## 검사 (`src/multiturn/scenario.py`, `tests/test_mt_scenario_and_history.py`)

- `validate_scenario`: 필드·타입, turn 번호 순서, `depends_on` 이 현재·미래 턴을 가리키지 않음, new 는 문서 첨부, recall·synthesis 는 문서 재첨부 없음, synthesis 는 2개 이상 의존, key_fact 마다 근거 인용문, recall·synthesis 각 2개 이상.
- `check_grounding`: 근거 인용문이 근거 페이지에 글자 그대로 있는지(공백만 접음), key_entity 가 근거 페이지에 있는지(`core_match.find_normalized`).
  근거 페이지 = 그 턴의 `evidence_pages` + `depends_on` 을 거슬러 올라간 턴들의 `evidence_pages` (recall 이면 의존 턴의 근거 페이지).
- key_fact 는 문장이라 원문과 글자가 같지 않다. 그래서 fact 마다 원문 인용문(`evidence`)을 달고 그 인용문을 확인한다. 인용문이 fact 를 실제로 뒷받침하는지는 사람 검수 항목이다.

## 싱글턴 대비 차이

멀티턴 답변 지시문은 `src/prompts/mt_answer_v2.md` 다 (실제 실행 전에 v1 에서 바꿨다. 기준 궤적을 포함한 모든 압축기가 v2 를 쓴다. v1 파일은 남겨 둔다. 싱글턴 `answer_v1.md` 는 바꾸지 않음).

| 항목 | 싱글턴 (answer_v1) | 멀티턴 (mt_answer_v1) | 이유 |
|---|---|---|---|
| 형식 줄 위치 | system 마지막 규칙 `{answer_format}` | 각 턴 user 메시지 끝 `Answer format: ...` | system 은 대화 내내 고정이라 문항 유형별 형식 줄을 둘 수 없다 |
| 근거 범위 (v2) | 제공된 문서 | 첨부 문서 + 이전 대화의 요약 `<conversation_summary>` 와 발췌 `<selected_history>` 도 "이 대화에서 제공된 문서" 로 본다 | 요약·선택 압축기가 넣은 블록을 모델이 문서가 아니라고 보고 NOT FOUND 를 내면 압축 효과가 아니라 지시문 효과가 섞인다 |
| system 첫 줄 | "...using only the documentation provided." | "...using only the documentation provided in this conversation." | 문서가 여러 턴에 걸쳐 첨부된다 |
| NOT FOUND 규칙 | `If the documentation does not contain the answer, reply exactly: NOT FOUND` | **같은 문구** (v1·v2 모두) | 압축으로 기록이 사라졌을 때 지어내는지 모른다고 하는지가 recall 턴의 핵심 관찰값. turn_type 별 not_found 비율을 집계한다 |
| 문서 블록 표기 | `<documentation>` 안에 `## Document: <doc_id>` 블록 | 같음 (문서를 붙이지 않는 턴은 `<documentation>` 없이 `Question:` 만) | per_message 압축기는 과거 user 메시지의 `<documentation>` 블록만 압축 대상으로 본다 |
| 압축 대상 | 현재 문항의 문서 | **과거 기록만** (예산형 압축기의 기록 토큰 예산도 과거 기록에만 적용). 현재 턴 user 메시지(첨부 문서 포함)와 system 은 압축하지 않는다 | 이번 실험은 대화 기록 압축의 효과만 본다. 현재 턴 문서 압축은 싱글턴 결과로 이미 측정했다 |
| 기록에 들어가는 답변 | (해당 없음) | 기준 궤적(none)의 최종 답변만. 추론은 넣지 않는다 | trajectory 규칙. replay 는 기준 궤적을 고정하고 턴 k 이전 기록만 압축한다 |

## 남은 일

- 사람 검수 (질문이 앞 턴을 실제로 필요로 하는지, key_fact 가 인용문과 맞는지) 뒤 `status: "reviewed"`.
- 파일럿 실행 뒤 기준 궤적 오답(depends_on_reference_ok=False) 이 많은 턴은 질문을 고친다.
