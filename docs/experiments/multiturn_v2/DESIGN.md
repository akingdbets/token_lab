# multiturn-v2 (FastAPI 정식 시나리오) 설계안

상태: A단계 확정 (2026-11-27). B단계(샘플 2개) 진행 중, 2026-11-28 설계 변경 후 샘플 재생성 (9절 변경 이력). 기존 `data/evalsets/multiturn-v1` 과 코드 동작은 바꾸지 않는다.

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
- (2026-11-28 추가) **사용자 고유 값**: 사용자가 대화 중 정하는 프로젝트 고유 값(토큰 만료 17분, 헤더 이름 X-Tenant-Key 같은 것)을
  사용자 발화에 넣고 recall·synthesis·update 의 대상으로 쓴다. key_fact 마다 출처 `source=doc | user`.
  recall·synthesis 턴의 key_fact 중 user 가 30~50% (문서 출처도 반드시 남긴다), user 값을 바꾸는 update 턴 1개 이상.
- (2026-11-28 추가) 문서 고유 예시 값(`fake-super-secret-token`, 예시 숫자 등)을 묻는 key_fact 를 우선한다. 태그 `example` (집계용, 검사 규칙 아님).
- (2026-11-28 추가) synthesis 를 뺀 턴은 1~2가지만 묻는다 (`asks` 필드). key_fact 는 턴당 최대 3개.
- (2026-11-28 추가) `standalone_question` 에 원래 질문에 없던 key_entity 를 넣지 않는다 (답 누설, 검사기 오류).
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
| `fact_meta[i].tags` | `condition` / `negation` / `range` / `confusable` / `example` (난이도 규칙 검사용, 분석에서 태그별 집계) |
| `fact_meta[i].source` | (2026-11-28) `doc` (문서) / `user` (사용자가 대화 중 정한 값). 분석은 출처별로 따로 |
| `evidence[]` 의 사용자 발화 인용 | (2026-11-28) `{quote, user_turn, fact_idx}`. quote 는 `user_turn` 턴 질문에 글자 그대로 있어야 하고, 그 턴은 이 턴 또는 depends_on 사슬 안 |
| `asks` | (2026-11-28) 이 턴이 묻는 사항 목록. synthesis 외 1~2개 |
| `changes`, `affects` | update 턴만. 바뀐 조건과 영향 받는 뒤 턴 |
| `source_turn` | same_doc_new_topic 만. 그 문서를 첨부한 턴 |
| `recall_distance` | 자동 계산 (`turn − min(depends_on)`, 없으면 0). 손으로 쓰지 않는다 |
| `closed_book_knowledge`, `closed_book_grounded` | closed-book 검사 두 종류 결과 (검사 도구가 채운다, 6절). 예전 `closed_book` 은 `closed_book_knowledge` 로 바뀜 |

`validate_scenario_v2(s)` (새 함수, v1 의 `validate_scenario` 는 그대로)

- v1 검사 전부 + 유형별 최소 개수·배치 규칙 (2절), 거리 6 이상 recall 2개, 3턴 이상 synthesis 1개
- `fact_meta` 길이 = `key_facts` 길이, 태그 개수 규칙 (3절)
- update: `changes` 비어 있지 않음, `affects` 는 뒤 턴이고 그 턴들의 `depends_on` 에 update 턴 포함, 마지막 3턴 금지
- same_doc_new_topic: `evidence_pages` 비어 있음, `source_turn` 이 그 페이지를 첨부한 턴이고 3턴 이상 전, 인용 구간이 첨부 턴 인용과 다른 소제목
- `recall_distance` 가 자동 계산값과 같음, 질문 금지 표현 없음
- `check_grounding_v2`: v1 근거 확인 + `alt_evidence` 인용문 확인. key_entity 는 근거 페이지와 사슬 안 사용자 발화에서 찾는다.
  한두 글자 기호 entity (`/` 등) 는 정규화 매칭이 다루지 못해 근거 확인에서 빼고 경고만 한다 (2026-11-28)
- (2026-11-28) source 별 근거 (user → 사용자 발화 인용, doc → 페이지 인용), user 비율 30~50%, user update 1개 이상,
  key_fact 최대 3개, synthesis 외 asks 1~2개, standalone_question 누설 없음

grader 의 `accept_alternatives` 사용 (채점 프롬프트 새 버전 파일, 기존 v2 는 그대로)

- 새 파일 `fact_judge_v3`: per_fact 판정 때 fact 문장 아래에 "Also counts as satisfied if the answer instead states: <대안들>" 을 붙인다.
  대안이 없는 fact 는 v2 와 글자 그대로 같은 프롬프트가 되게 만든다.
- 결정 (2026-11-27): 사람 라벨 80행(judge_check_test)으로 v2 와 v3 의 일치율을 잰다. **v3 가 v2 보다 낮지 않으면 multiturn-v2 실험의 채점은 v3**
  (none 포함 모든 압축기에 똑같이, 채점 버전을 결과에 기록). 낮으면 v2 를 쓰고 `accept_alternatives` 는 분석용으로만 쓴다.
- 결과 (2026-11-27): v2 0.863, v3 0.850 (80행). 규칙대로면 v2.
- **변경 (2026-11-28): fact_judge_v3 를 쓴다.** 80행에는 대안이 없어 v3 와 v2 는 글자 그대로 같은 프롬프트를 보냈고 (테스트로 확인),
  1행 차이는 같은 프롬프트에서의 채점기 변동이다 (80행 중 3행이 뒤집힘). v3 가 나쁘다는 근거가 아니다.
  대안 블록이 붙은 판정은 v2 시나리오 검수 때 사람 라벨로 따로 확인한다 (7절 alt_judge_label).

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
- 채점: deepseek-flash, fact_judge_v3 (2026-11-28 결정, 4절), per_fact, `accept_alternatives` 를 넘긴다. `correct = accuracy == 1.0`.
- 맞힌 문항은 제외하지 않고 표시만 한다. 분석에서 맞힘/못 맞힘으로 나눠 집계한다.
- (2026-11-28) 두 종류로 나눈다. 둘 다 턴마다 표시하고 보고에 두 비율을 나란히 낸다.

| 검사 | 지시문 | 무엇을 보나 | 턴 필드 |
|---|---|---|---|
| knowledge | 싱글턴 `CLOSED_BOOK_PROMPT` (모르면 UNKNOWN) | 모델이 사전 지식으로 맞히는지 | `closed_book_knowledge` |
| grounded | 실험 답변 지시문 `mt_answer_v2` (system + user_no_docs, NOT FOUND 규칙), 문서·기록 없이 | NOT FOUND 대신 정답을 내는지. **압축 결과를 오염시키는 쪽** (압축으로 정보를 잃어도 맞힐 수 있다) | `closed_book_grounded` |

## 7. 검수 시트

- `src/multiturn/review_sheet.py` → `docs/review/multiturn_v2_<id>.csv` + 보기용 HTML (기존 `judge_check_viewer` 방식).
- 행 = 턴. 열: scenario_id, turn, turn_type, depends_on, recall_distance, question, standalone_question, answer,
  key_facts (태그·대안 포함), evidence 인용문(페이지), closed_book (응답 포함), auto_check (근거 확인·규칙 위반),
  **standalone_same_fact** (standalone_question 이 원래 질문과 같은 사실을 묻는가: 예 / 아니오), **verdict** (OK / 수정 필요 / 제외), **memo**, reviewer.
- (2026-11-28) asks, closed_book_knowledge·closed_book_grounded 두 열, key_facts 에 source 표시, 사용자 발화 인용 표시.
  **alt_judgments** (대안이 있는 fact 의 fact_judge_v3 판정) 와 **alt_judge_label** (그 판정이 맞는가: 맞음 / 틀림, 사람 라벨).
  대안 블록이 붙은 판정은 80행 비교로 잴 수 없어 검수 때 따로 확인한다.
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

## 9. 변경 이력

### 2026-11-28 샘플 closed-book 결과에 따른 설계 변경

B단계 첫 샘플 2개 (생성 프롬프트 `mt_scenario_gen_v1`) 의 closed-book 검사에서 문서·대화 없이 맞힌 턴이 38개 중 26개였다.
원인은 (1) `standalone_question` 이 앞 대화의 답을 담아 흘린 것 (원래 질문에 없던 key_entity 를 새로 담은 턴 20개 중 15개를 맞힘),
(2) FastAPI 문서의 일반 지식이었다. 그래서 아래처럼 바꾸고 샘플 2개를 `mt_scenario_gen_v2` 로 다시 만들었다.

| 변경 | 내용 |
|---|---|
| 누설 방지 | standalone_question 에 원래 질문에 없던 key_entity 가 있으면 검사기 오류. 생성 프롬프트에도 금지 |
| 사용자 고유 값 | `fact_meta.source = doc / user`, 사용자 발화 인용 `{quote, user_turn, fact_idx}`. recall·synthesis key_fact 의 user 30~50%, user 값 update 1개 이상 |
| 문서 고유 예시 값 | 생성 프롬프트에서 우선. 태그 `example` 로 집계 |
| 질문 크기 | synthesis 외 1~2가지만 (`asks`), key_fact 턴당 최대 3개 |
| closed-book 두 종류 | knowledge (기존) + grounded (실험 지시문 mt_answer_v2, NOT FOUND 규칙) |
| 채점 | fact_judge_v3 (4절) |
| 기호 entity | 한두 글자 기호 key_entity 는 근거 확인에서 빼고 경고만 |

**"모델 성능을 보고 문항을 거르지 않는다" 원칙과 충돌하지 않는 이유.** 샘플은 draft 이고, 이 변경은 압축 결과(실험 결과)가 아니라
closed-book 검사 결과(문항 설계의 타당성 점검)에 따른 **설계 변경**이다. 특정 문항을 골라 빼거나 정답률을 보고 다시 만든 것이 아니라,
생성 규칙과 검사기를 바꾼 뒤 같은 묶음으로 처음부터 다시 생성했다. 압축기 결과는 아직 하나도 보지 않았다.

### 2026-11-28 샘플 검수 결정 (생성 프롬프트 `mt_scenario_gen_v3`)

사람 검수 결과를 생성 규칙과 검증기에 반영했다. 샘플 2개는 다시 생성하지 않고 손으로 고쳤다 (각 시나리오의 `edits` 필드).
나머지 18개는 v3 로 생성한다.

| 규칙 | 검증기 |
|---|---|
| setup: 이번 턴 사용자 발화에 답이 그대로 있는 key_fact (이번 턴에 정한 값, update 로 바뀐 값을 그대로 쓰기) 에 태그 `setup`. 주 정확도에서 빼고 따로 집계 | 이번 턴 사용자 발화를 인용한 source=user 항목은 setup 이어야 하고, 그 밖에는 setup 금지. 모든 턴에 setup 이 아닌 key_fact 1개 이상 |
| synthesis 는 묻는 사항을 하나씩 명시. 계획·체크리스트·요약처럼 답의 범위가 열린 요청 금지 | asks 와 key_facts 길이가 같다 (i 번째 fact 가 i 번째 사항). 열린 요청 표현(plan, checklist, summarize 등)이 질문에 있으면 오류 |
| 대안 답은 문서 또는 앞 대화에 근거 인용이 있을 때만 | alt_evidence 는 페이지 또는 사용자 발화(user_turn) 인용, 근거 확인에 포함 |
| depends_on 의 모든 턴은 채점된다 | 턴마다 depends_on 의 각 턴에 대해, 그 턴의 사용자 발화·첨부 페이지·그 턴이 인용한 페이지를 근거로 한 key_fact 가 1개 이상 |
| 한 턴은 한 주제 | 한 턴에 다른 폴더(주제)의 문서를 둘 이상 붙이면 경고 (사람이 판단) |

closed-book 의 `correct` 도 주 정확도와 같게 setup 을 뺀 key_fact 기준 (`accuracy_main`) 으로 바꿨다.
검수 시트에 시나리오별 보기, 자동 의심 사유(`suspect`), 검수 표시(`review` 필드: standalone_same_fact, flags) 를 더했다.

### 2026-11-28 검수 2차 결정 (손 수정, 재생성 없음)

- 검사기 오탐 2종 수정 (승인): key_entity 는 정규화 매칭이 실패하면 원문 글자 그대로 한 번 더 찾는다.
  출처 단서 검사에서 한 단어 제목과 흔한 낱말(알파벳만) 두 단어 제목(Middleware, Background Tasks, WebSockets, Lifespan Events 등)은 뺀다.
- 실제 실패 5건과 의심 턴 손 수정 (각 시나리오 `edits` 필드). 바뀐 턴만 closed-book 을 다시 돌렸다 (`closed_book_v2.py --missing-only`).
- 간접 의존·기억 답·recall 인데 knowledge 로 맞힌 턴은 고치지 않고 표시만 유지한다. 기억 답 턴은 `review.flags = grounded_memory` 로 남긴다.
- 사람 검수 대상 `review.target` (`src/multiturn/review_targets.py`, 시드 20261128): (a) 질문을 고친 턴, (b) 대안 판정 턴,
  (c) 남은 의심 턴(한 턴 한 주제 경고 포함), (d) 나머지에서 시나리오마다 10% 무작위. 검수 시트의 "검수 대상만" 보기.
