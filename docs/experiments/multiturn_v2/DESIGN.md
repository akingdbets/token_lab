# multiturn-v2 (FastAPI 정식 시나리오) 설계안

상태: A단계 확정 (2026-11-27). B단계(샘플 2개) 진행 중. 기존 `data/evalsets/multiturn-v1` 과 코드 동작은 바꾸지 않는다.

## 0. 전제 (멘토 회의 결정)

- 프롬프트 캐시는 평가에서 뺀다. 캐시가 없는 LLM 을 가정하고 **문맥 토큰과 정확도**로만 본다.
  replay 의 비용 열 중 `nocache` 와 토큰 절감률만 쓴다 (sim·sim_write 는 보고하지 않음).
- 순서: FastAPI 정식 시나리오로 압축 기법을 개별 평가하고 조합을 고른다. 그다음 같은 기법 집합을 다른 도메인에 그대로 적용한다.

### 가정과 범위

- **별도의 문맥 한도를 설정하지 않은 일반적인 LLM 사용 상황을 가정한다.** 이런 환경에서는 문맥 한도 근처에서 강제로 요약하는
  compaction 이 일어나지 않으므로 범위에서 뺀다.
- 연구 대상은 **문맥 한도 안에서 토큰을 줄이려고 매 턴 미리 하는 압축(선제 압축)** 이다.
- 예산(r25 / r50 / r75, 절대 예산 2000·4000·8000)은 문맥 한도가 아니라 **압축 강도**다.
- `rolling_summary` 는 compaction 이 아니라 **선제 요약(계획서 기법 2: 재귀 요약)** 이다. 한도에 닿아서가 아니라 정한 압축 강도를 넘을 때마다 요약한다.
- 답변 모델 gpt-6-luna 의 문맥 창은 **1,050,000 토큰, 최대 입력 922,000 토큰**이다
  ([OpenAI 모델 문서](https://developers.openai.com/api/docs/models/gpt-6-luna), 2026-11-27 확인).
  시나리오 최대 기록(약 21k 토큰, 1절 표의 최대 21,145)은 최대 입력의 약 2.3% 로 충분히 작다. 압축하지 않은 none 도 한도에 닿지 않는다.
  272k 입력을 넘으면 단가가 달라지는 구간이 있지만 이 실험의 입력은 그보다 훨씬 작다.

파일럿(v1)에서 고칠 점과 v2 대응

| v1 한계 | v2 대응 |
|---|---|
| 기준 정확도 100% (천장 효과) | 헷갈리는 묶음, 조건·부정 key_fact, 먼 recall, update, same_doc_new_topic (아래 규칙) |
| 질문에 출처 단서 ("In the JWT tutorial") | 출처 단서 금지 + 검사기에서 금지 표현 검사 |
| recall 거리 4~6턴 | 6턴 이상 떨어진 recall 을 시나리오당 2개 이상 |
| 헷갈릴 요소 없음 | 비슷한 값·이름이 여러 페이지에 나오도록 페이지를 묶음 |
| 사전 지식으로 맞힐 수 있음 | closed-book 검사 결과를 턴마다 표시 (제외하지 않고 따로 집계) |
| 사람 검수 없음 | 검수 시트, `reviewed` 전에는 본 실험에 쓰지 않음 |
| 다른 정당한 해법을 오답 처리 (mt03 턴 1) | key_fact 마다 `accept_alternatives` |
| 9턴 기록 최대 6.5k 토큰 | 16~20턴, 마지막 턴 기록 15k 이상 |

## 1. 규모와 페이지 묶음

- 시나리오 20개, 각 16~20턴 (기본 18턴). 문서 첨부 턴 8~9개 (턴당 1페이지가 기본, synthesis 준비용으로 2페이지도 허용).
- 코퍼스: `data/openwiki/en` 66페이지, 합계 98,098 토큰 (tiktoken o200k_base, gpt-6-luna 와 같은 토크나이저),
  페이지 평균 1,486 / 중앙값 1,714 / 최대 2,668. `index.md` 류(60~500 토큰)는 묶음에서 뺐다.
- 마지막 턴 기록 = 첨부 문서 합 + 턴마다 질문·형식 줄·답변 약 110토큰 (파일럿 실측: 답변 평균 56토큰) × 18 + system 150.
- 66페이지가 모두 한 번 이상 쓰인다. 가장 많이 쓰인 페이지는 `errors/handling-errors.md`, `middleware/middleware.md` (각 7회).

| ID | 주제 | 페이지 수 | 문서 토큰 | 예상 마지막 턴 기록 |
|---|---|---|---|---|
| v2_01 | 인증 방식 전환 (헤더 토큰·쿠키·API 키) | 9 | 16,081 | 18,211 |
| v2_02 | 응답 상태·형식 설계 | 9 | 18,585 | 20,715 |
| v2_03 | 요청 입력 검증 | 8 | 17,797 | 19,927 |
| v2_04 | 의존성 수명과 정리 | 9 | 15,283 | 17,413 |
| v2_05 | 배포 구성 (서버·컨테이너·프록시) | 9 | 14,857 | 16,987 |
| v2_06 | 미들웨어와 교차 출처 | 9 | 15,469 | 17,599 |
| v2_07 | 스트리밍·실시간 | 8 | 15,548 | 17,678 |
| v2_08 | 모델 설계와 직렬화 | 8 | 17,460 | 19,590 |
| v2_09 | OpenAPI 문서 꾸미기 | 8 | 16,706 | 18,836 |
| v2_10 | 큰 앱 구조와 라우터 | 9 | 17,632 | 19,762 |
| v2_11 | 테스트 전략 | 9 | 15,238 | 17,368 |
| v2_12 | 데이터베이스 연동 | 9 | 17,266 | 19,396 |
| v2_13 | 에러 처리 일관성 | 9 | 19,015 | 21,145 |
| v2_14 | 파일·폼·정적 파일 | 8 | 16,954 | 19,084 |
| v2_15 | 설정과 환경 분리 | 9 | 15,096 | 17,226 |
| v2_16 | 권한 범위와 사용자 모델 | 9 | 18,635 | 20,765 |
| v2_17 | 요청 객체와 내부 동작 | 8 | 14,718 | 16,848 |
| v2_18 | 외부 연동 (GraphQL·관측·백그라운드) | 9 | 15,247 | 17,377 |
| v2_19 | 첫 서비스 만들기 (입문에서 운영까지) | 9 | 17,440 | 19,570 |
| v2_20 | 클라이언트 생성과 API 계약 | 8 | 16,548 | 18,678 |

묶음별 페이지 목록: `docs/experiments/multiturn_v2/bundles.json`. 모든 시나리오가 15k 를 넘는다 (최소 16,848).

### 헷갈리는 값이 겹치는 묶음 (코퍼스에서 센 값)

| 겹치는 값 | 나오는 페이지 | 쓰는 묶음 |
|---|---|---|
| 401 대 403 (인증 실패 상태) | security 4페이지, errors, http-basic-and-api-keys, bigger-applications | v2_01, v2_16, v2_10 |
| 422 (검증 오류) | 8페이지 (errors, forms-and-files, headers-and-cookies, status-codes ...) | v2_03, v2_13 |
| 200·201·204·304 / "body 금지" 코드 | status-codes, custom-responses, internals, errors | v2_02, v2_13, v2_20 |
| 포트 8000 / 80 / 8080 | 9페이지 (deployment, docker, first-steps, cors ...) | v2_05, v2_15, v2_19 |
| OpenAPI 버전 "3.1.0", 기본 title "FastAPI", version "0.1.0" | metadata-and-docs-ui, extending-openapi | v2_09, v2_20 |
| GZip `minimum_size` 500 / 압축 수준 9, response_model 기본값 | middleware, response-model | v2_06, v2_08 |
| 쿠키 대 헤더 (samesite 기본 "lax", httponly) | response-headers-and-cookies, headers-and-cookies, security | v2_01, v2_06, v2_17 |
| yield 정리 순서 / 500 처리 / lifespan 시작·종료 | dependencies-with-yield, lifespan-events, middleware, errors | v2_04, v2_12, v2_13 |

## 2. 턴 유형과 배치 규칙

| 유형 | 정의 | 시나리오당 최소 (18턴 기준 권장) |
|---|---|---|
| new | 새 문서를 첨부하고 그 문서로 답 | 7 (권장 8) |
| followup | 직전 턴(거리 1)에 의존 | 2 (권장 3) |
| recall | 문서 재첨부 없이 앞 턴 정보에 의존 | 3, 그중 **거리 6 이상 2개** |
| synthesis | 2개 이상 턴을 묶음 | 2, 그중 **3개 이상 턴을 묶는 것 1개** |
| update (신규) | 사용자가 앞 조건·요구를 바꿈. 이후 턴은 바뀐 조건 기준 | **2** |
| same_doc_new_topic (신규) | 3턴 이상 전에 첨부한 문서의 **다른 부분**을 재첨부 없이 물음 | 2 |

배치 규칙

- 턴 0·1 은 new. 문서 첨부 턴은 앞 1/3, 가운데 1/3, 뒤 1/3 에 각 2개 이상 (기록이 고르게 자란다).
- update 턴은 마지막 3턴 안에 두지 않는다. update 뒤에 그 변경을 따라야 하는 턴(`affects`)이 1개 이상 있어야 하고,
  그 턴의 `depends_on` 에 update 턴을 넣는다. 영향 턴의 정답은 **바뀐 조건 기준**이다. 옛 조건 기준 답은 `accept_alternatives` 에 넣지 않는다.
- same_doc_new_topic 은 그 문서가 첨부된 턴과 3턴 이상 떨어진다. 첨부 당시 물은 부분과 다른 소제목(`##`)의 내용을 묻는다
  (검사기: 근거 인용문이 그 페이지에 있고, 첨부 턴의 인용문과 같은 소제목 구간이 아님).
- 마지막 3턴 안에 거리 6 이상 recall 1개와 synthesis 1개를 둔다.
- 같은 유형을 3턴 넘게 연달아 두지 않는다.

## 3. 난이도 규칙 (설계로만 올린다)

- recall: 거리(현재 턴 − 가장 먼 depends_on) 6 이상을 시나리오당 2개 이상.
- 질문에 출처 단서를 넣지 않는다. 대화 맥락으로만 가리킨다 ("the limit we settled on earlier", "that setting").
  검사기 금지 표현: 페이지 제목·파일 이름, `tutorial`, `the (first|second|earlier) (doc|document|page)`, `going back to`, `in the docs about`.
- 헷갈리는 묶음: 위 표처럼 비슷한 값이 다른 페이지에 다른 의미로 나오게 묶는다. 시나리오당 confusable 태그 key_fact 2개 이상.
- 조건·부정·범위가 핵심인 key_fact (`below 200`, `does not`, `only when`, `at least`) 를 시나리오당 3개 이상. 태그 `condition`/`negation`/`range`.
- synthesis 중 1개 이상은 3개 이상 턴을 묶는다.
- **모델 성능을 보고 문항을 거르거나 다시 만들지 않는다.** 제외 사유는 (1) 근거 확인 실패, (2) closed-book 검사 결과에 따른 별도 집계 표시,
  (3) 사람 검수의 "제외" 판정 세 가지뿐이다. 이 원칙과 제외 기록은 `data/evalsets/multiturn-v2/README.md` 에 적는다.

## 4. 스키마 v2

v1 필드는 그대로 두고 추가한다 (`schema_version: 2`). 압축기·replay 는 v1 필드만 읽으므로 그대로 돈다.

```json
{
  "schema_version": 2, "scenario_id": "v2_01_auth_switch", "title": "...", "topic": "security", "status": "draft",
  "bundle": ["security/oauth2-password-flow.md", "..."],
  "generation": {"model": "...", "prompt": ["mt_scenario_gen_v1", "<sha256>"], "created_at": "...", "run_id": "..."},
  "turns": [{
    "turn": 7, "turn_type": "update", "type": "procedure",
    "question": "...", "standalone_question": "...",
    "answer": "...", "key_facts": ["...", "..."],
    "fact_meta": [{"accept_alternatives": ["..."], "tags": ["negation"]}, {"accept_alternatives": [], "tags": []}],
    "key_entities": ["..."], "evidence_pages": [], "depends_on": [2],
    "evidence": [{"quote": "...", "page": "...", "fact_idx": 0}],
    "alt_evidence": [{"quote": "...", "page": "...", "fact_idx": 0, "alt_idx": 0}],
    "changes": [{"what": "auth transport", "from": "cookie", "to": "Authorization header"}],
    "affects": [9, 12],
    "source_turn": null,
    "recall_distance": 5,
    "closed_book": {"correct": false, "accuracy": 0.0, "response": "UNKNOWN", "model": "gpt-6-luna", "run_id": "..."}
  }]
}
```

| 필드 | 뜻 |
|---|---|
| `turn_type` | v1 4종 + `update`, `same_doc_new_topic` |
| `standalone_question` | 대화 맥락 없이도 뜻이 통하게 다시 쓴 질문 (출처 단서는 여전히 금지). closed-book 검사에만 쓴다. 대화 맥락으로 가리키는 질문을 그대로 물으면 closed-book 이 의미가 없기 때문. 검수 시트에서 "원래 질문과 같은 사실을 묻는가" 를 확인한다 |
| `fact_meta[i].accept_alternatives` | key_fact i 대신 받아 줄 문서상 정당한 다른 답. 각각 `alt_evidence` 로 근거 인용 |
| `fact_meta[i].tags` | `condition` / `negation` / `range` / `confusable` (난이도 규칙 검사용, 분석에서 태그별 집계) |
| `changes`, `affects` | update 턴만. 바뀐 조건과 영향 받는 뒤 턴 |
| `source_turn` | same_doc_new_topic 만. 그 문서를 첨부한 턴 |
| `recall_distance` | 자동 계산 (`turn − min(depends_on)`, 없으면 0). 손으로 쓰지 않는다 |
| `closed_book` | closed-book 검사 결과 (검사 도구가 채운다) |

`validate_scenario_v2(s)` (새 함수, v1 의 `validate_scenario` 는 그대로)

- v1 검사 전부 + 유형별 최소 개수·배치 규칙 (2절), 거리 6 이상 recall 2개, 3턴 이상 synthesis 1개
- `fact_meta` 길이 = `key_facts` 길이, 태그 개수 규칙 (3절)
- update: `changes` 비어 있지 않음, `affects` 는 뒤 턴이고 그 턴들의 `depends_on` 에 update 턴 포함, 마지막 3턴 금지
- same_doc_new_topic: `evidence_pages` 비어 있음, `source_turn` 이 그 페이지를 첨부한 턴이고 3턴 이상 전, 인용 구간이 첨부 턴 인용과 다른 소제목
- `recall_distance` 가 자동 계산값과 같음, 질문 금지 표현 없음
- `check_grounding_v2`: v1 근거 확인 + `alt_evidence` 인용문 확인

grader 의 `accept_alternatives` 사용 (채점 프롬프트 새 버전 파일, 기존 v2 는 그대로)

- 새 파일 `fact_judge_v3`: per_fact 판정 때 fact 문장 아래에 "Also counts as satisfied if the answer instead states: <대안들>" 을 붙인다.
  대안이 없는 fact 는 v2 와 글자 그대로 같은 프롬프트가 되게 만든다.
- 결정 (2026-11-27): 사람 라벨 80행(judge_check_test)으로 v2 와 v3 의 일치율을 잰다. **v3 가 v2 보다 낮지 않으면 multiturn-v2 실험의 채점은 v3**
  (none 포함 모든 압축기에 똑같이, 채점 버전을 결과에 기록). 낮으면 v2 를 쓰고 `accept_alternatives` 는 분석용으로만 쓴다.

## 5. 생성 파이프라인

생성 모델 후보 (답변 gpt-6-luna, 채점 deepseek-flash 와 달라야 한다)

| 후보 | 장점 | 단점 |
|---|---|---|
| **gpt-6.1-sol (결정)** | 키가 이미 있다, 추론 품질, 스크립트로 재현 가능 (프롬프트·응답 저장) | luna 와 같은 회사 계열이라 사전 지식이 겹칠 수 있다. closed-book 검사로 따로 확인 |
| deepseek-flash | 싸다 | 채점 모델이라 생성자 = 채점자 편향. 쓰지 않는다 |
| Claude (이 세션 또는 API) | 회사가 달라 편향이 적다 | API 키 없음. 세션 생성은 재현 기록이 약하다 |

단계 (`src/multiturn/scenario_gen.py`, 단계마다 결과 파일을 남기고 이어 돌릴 수 있게). 생성 프롬프트·요청 설정·응답 원문을 run 폴더에 전부 저장해 재현할 수 있게 한다

1. 페이지 묶음 선정: `bundles.json` (1절 표)
2. 시나리오 후보 생성: 묶음 페이지 원문 + 스키마 + 규칙 + 예시 1개를 넣고 JSON 생성. 프롬프트는 `src/prompts/mt_scenario_gen_v1.md`
3. 스키마 검증 `validate_scenario_v2`. 실패하면 오류 목록을 붙여 1회까지 고쳐 달라고 다시 요청 (모델 성능 때문이 아니라 형식 오류일 때만)
4. 근거 확인 `check_grounding_v2` (인용문이 원문에 글자 그대로 있는지). 실패 턴은 표시만 하고 검수 시트에 올린다 (자동으로 다시 만들지 않음)
5. closed-book 검사 (6절)
6. 검수 시트 생성 (7절)
7. 사람 검수 → 반영 → `status: reviewed`

비용 추정 (gpt-6.1-sol 입력 $2 / 출력 $10 per 1M)

| 항목 | 토큰 (시나리오 1개) | 비용 |
|---|---|---|
| 생성 입력 | 묶음 문서 약 17k + 지시·스키마·예시 4k = 21k | $0.042 |
| 생성 출력 | JSON 약 6k + 추론 약 8k = 14k | $0.14 |
| 형식 오류 재요청 (30% 가정) | 위의 약 절반 | $0.03 |
| closed-book (luna 서버 기본값 18회 + 채점 약 40회) | 작음 | $0.01~0.02 |
| **시나리오 1개** | | **약 $0.22~0.25** |
| **B단계 (샘플 2개)** | | **약 $0.5** |
| **전체 20개** | | **약 $4.5~5** |

## 6. closed-book 검사

- 새 모듈 `src/multiturn/closed_book_v2.py`. 싱글턴 `closed_book_check.py` 의 `CLOSED_BOOK_PROMPT` 와 판정 방식
  (`grade_answer_accuracy`, UNKNOWN·빈 답변 처리)을 그대로 import 해서 쓴다. 싱글턴 파일은 고치지 않는다.
- 질문은 `standalone_question`, 문서와 이전 대화 없이. 답변 모델 설정은 실험과 같게 replay 의 `configure_llm` 을 쓴다
  (gpt-6-luna, reasoning_effort server_default, 출력 한도 4096, temperature 보내지 않음).
- 채점: deepseek-flash, fact_judge_v2, per_fact. `closed_book.correct = accuracy == 1.0`.
- 맞힌 문항은 제외하지 않고 표시만 한다. 분석에서 closed_book=true/false 로 나눠 집계한다.

## 7. 검수 시트

- `src/multiturn/review_sheet.py` → `docs/review/multiturn_v2_<id>.csv` + 보기용 HTML (기존 `judge_check_viewer` 방식).
- 행 = 턴. 열: scenario_id, turn, turn_type, depends_on, recall_distance, question, standalone_question, answer,
  key_facts (태그·대안 포함), evidence 인용문(페이지), closed_book (응답 포함), auto_check (근거 확인·규칙 위반),
  **standalone_same_fact** (standalone_question 이 원래 질문과 같은 사실을 묻는가: 예 / 아니오), **verdict** (OK / 수정 필요 / 제외), **memo**, reviewer.
- 검수 결과 반영: `apply_review` 류 스크립트로 verdict 를 시나리오 JSON 의 `review` 필드에 넣고, 제외 턴과 사유를 README 의 제외 기록 표에 남긴다.
- 제외 턴을 빼면 depends_on 이 깨지는 경우: 그 턴에 의존하는 턴도 함께 표시해 검수자가 판단한다 (자동 삭제 없음).

## 8. 압축 강도를 기록 대비 비율로 (구현은 다음 단계)

예산은 문맥 한도가 아니라 압축 강도다 (0절 가정과 범위).

- 이름 예: `window_budget(r50)`, `query_select(r25)`, `frozen_summary(r75)`. 턴 k 의 예산 = ⌈r × 그 턴 과거 기록 원문 토큰⌉.
- 과거 기록 기준으로 잡는다 (현재 턴은 압축 대상이 아니므로). `on_arrival` 은 현재 턴 문서도 압축하므로 따로 표시한다.
- 시나리오 설계와 맞는지
  - 기록이 고르게 자라도록 첨부 턴을 세 구간에 나눴다 (2절). 앞 몇 턴은 기록이 작아 비율 예산이 의미가 작다 → 분석은 기록 4k 이상인 턴부터 따로 집계.
  - 거리 6 이상 recall 은 keep_recent(최근 1턴) 밖에 있어 비율 예산에서 실제로 압축 대상이 된다.
  - 문서 한 페이지(최대 2.7k)가 r25 예산보다 큰 경우가 생긴다 → 기존 overflow 표시를 그대로 쓴다.
- 절대 예산(2000·4000·8000)도 함께 돌릴 수 있게 둔다 (v1 과 비교용).
