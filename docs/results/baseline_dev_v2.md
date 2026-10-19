# dev baseline v2 (상용 API: gpt-6-luna 답변 · deepseek-flash 채점)

> **생각 토큰을 끈 설정에서 측정했다.** 답변 gpt-6-luna 는 `reasoning_effort=none`, `temperature=0`, seed 42 (summary.json `config.sampling.answer` 실제 적용값).
> 처음 측정(서버 기본값 reasoning_effort, temperature 1)은 [부록 A](#부록-a-temperature-1-측정-run-20261019-203350) 에 남겼다.
>
> **Qwen 로컬 결과(v1, `baseline_dev_v1.md`)와 직접 비교 불가.** 답변 모델, 채점 모델, 토크나이저(o200k_base)가 모두 바뀌어
> 토큰 단위와 정확도 기준이 다르다.
>
> **정확도는 잠정치.** deepseek-flash 채점은 사람 라벨 검증 전이다 (`judge_check_v3.csv`). 틀린 답 세트에서는 FP 0/30 이었다 (`judge_compare_v3.md`).
> 토큰·의미 손실 지표는 채점과 무관하므로 확정값이다.

claude-v1 평가셋 dev 35문항. 압축기 5개를 같은 run 에서 돌렸다.

- none: 원문 그대로 (기준선)
- rule: 규칙 기반 정제 (현재 기본값, 머리말의 title·description·tags 를 남김)
- rule_fm_all: 머리말을 통째로 지우는 rule (v1 문서의 rule 과 같은 동작)
- empty: 문서를 비움 (바닥값, 보정 유지율의 기준점)
- drop_evidence: 문항의 근거 인용문 줄만 지움 (진단용. 근거가 빠지고 주제 문맥은 남았을 때 기억으로 답을 채우는지 본다)
- run: `20261019-231040` (5개 압축기), 재현성 확인용 none 한 번 더: `20261019-234729`. `results/` 는 커밋하지 않음
- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split dev --compressors none,rule,rule_fm_all,empty,drop_evidence --semantic`
  (`ANSWER_REASONING_EFFORT` 기본값이 none)
- 판정: deepseek-flash, per_fact, fact_judge_v2, temperature 0, seed 42, 출력 최대 4096 토큰 (생각 토큰 포함, reasoning_effort 서버 기본값).
  답변이 NOT FOUND 뿐이거나 비어 있으면 judge 없이 0

## 결과

| 지표 | none | rule | rule_fm_all | empty | drop_evidence |
|---|---|---|---|---|---|
| 평균 입력 토큰 | 2208.8 | 1769.5 | 1678.1 | 120.9 | 2160.0 |
| 입력 토큰 절감률 | 0.0% | 19.89% | 24.03% | 94.52% | 2.21% |
| 순 입력 토큰 절감률 | 0.0% | 19.89% | 24.03% | 94.52% | 2.21% |
| 과금 입력 토큰 절감률 (`billed_input_reduction_pct`) | - | 19.90% | 24.04% | 94.57% | 2.21% |
| 의미 유사도 | 1.000 | 0.967 | 0.947 | 0.000 | 0.988 |
| 핵심 개체 보존율 | 1.000 | 1.000 | 1.000 | 0.000 | 0.586 |
| 의미 손실 | 0.000 | 0.033 | 0.054 | 1.000 | 0.419 |
| 의미 손실 5% 이내 문항 비율 | 100% | 100% | 54.3% | 0% | 40.0% |
| 답변 정확도 (잠정) | 1.000 | 0.986 | 0.971 | 0.000 | 0.619 |
| 정확도 유지율 (잠정) | - | 98.57% | 97.14% | 0.0% | 61.90% |
| 보정 유지율 (잠정, empty 기준) | - | 98.57% | 97.14% | - | 61.90% |
| NOT FOUND 비율 | 0.0% | 0.0% | 0.0% | 100.0% | 31.4% (11/35) |
| 기억 의존 의심 (`memory_suspect`) | 0 | 0 | 0 | 0 | 7 (20.0%) |
| 정확도 fact (n=11) | 1.000 | 1.000 | 1.000 | 0.000 | 0.545 |
| 정확도 code (n=12) | 1.000 | 1.000 | 1.000 | 0.000 | 0.333 |
| 정확도 procedure (n=8) | 1.000 | 1.000 | 0.938 | 0.000 | 1.000 |
| 정확도 multi (n=4) | 1.000 | 0.875 | 0.875 | 0.000 | 0.917 |
| 정확도 type 균등 | 1.000 | 0.969 | 0.953 | 0.000 | 0.699 |
| 답변 잘림 (512 토큰 도달) | 0 | 0 | 0 | 0 | 0 |
| judge 호출 key_facts / 생략 (NOT FOUND) | 58 / 0 | 58 / 0 | 58 / 0 | 0 / 35 | 47 / 11 |
| judge 응답 못 읽음 | 0 | 0 | 0 | 0 | 0 |

- 입력 토큰은 채팅 템플릿을 포함한 전체 messages 기준 (`tiktoken:o200k_base`). 절감률은 전체 합의 비율. 과금 기준 절감률과 차이 0.05%p 이하
- 정확도 유지율 = 압축 평균 정확도 / none 평균 정확도. 보정 유지율 = (압축 − empty) / (none − empty) (문항 짝 평균).
  empty 정확도가 0 이라 두 값이 같다
- empty 의 의미 유사도는 임베딩하지 않고 0 으로 둔다 (빈 문맥)
- 기억 의존 의심: 압축 문맥에 정답 핵심어(짧은 답은 정답 단어, 긴 답은 핵심 개체 절반 이상)가 없는데 정확도 ≥ 0.5

## 지연 시간 (초)

| 압축기 | TTFT 평균 | TTFT 중앙값 | 전체 평균 | 전체 중앙값 | 평균 출력 토큰 |
|---|---|---|---|---|---|
| none | 3.74 | 2.19 | 4.08 | 2.51 | 38.8 |
| rule | 3.20 | 1.93 | 3.49 | 2.18 | 38.8 |
| rule_fm_all | 3.74 | 2.30 | 4.04 | 2.43 | 38.7 |
| empty | 3.79 | 2.29 | 3.83 | 2.32 | 5.0 |
| drop_evidence | 3.18 | 1.76 | 3.49 | 2.58 | 37.7 |

- 입력이 95% 줄어든 empty 도 중앙값이 none 과 비슷하다. 이 규모(입력 2천 토큰 안팎)에서는 지연 시간이 입력 길이보다 서버·네트워크 변동에 좌우된다.
  평균이 중앙값보다 1초 이상 큰 것은 몇 건의 느린 응답 때문이다

## none 보다 정확도가 떨어진 문항 (rule, rule_fm_all)

| qid | type | none → 압축 | 원인 |
|---|---|---|---|
| c0015 | multi | 1.00 → 0.50 (rule, rule_fm_all) | fact 1 "create_access_token 으로 만든 서명된 JWT" 불충족. 답변은 "signed, expiring JWT" 라고만 했다. 이 fact 는 none 끼리도 반복마다 O/X 가 갈린다 (재현성). 압축 손실이 아니라 judge 경계 사례 |
| c0024 | procedure | 1.00 → 0.50 (rule_fm_all) | fact 0 "yield 를 try/except 로 감싼다" 불충족. 답변이 "yield 의존성 안에서 예외를 잡는다" 고만 하고 try 블록을 말하지 않았다. 핵심 개체는 모두 남아 있어(보존율 1.0) 답변 생성 쪽 변동으로 보인다 |

## drop_evidence: 근거 줄만 지우면

근거 인용문이 든 줄만 지웠다 (문항당 1~6줄, 7~139 토큰, 입력의 2.2%). 35문항 모두 인용문을 문맥에서 찾았다.

- **NOT FOUND 11문항 (31.4%)**: c0002, c0005, c0017, c0020, c0021, c0023, c0027, c0031, c0034, c0036, c0037. 근거가 없으면 지시대로 NOT FOUND 로 답한 경우
- **틀린 값으로 답함 2문항**: c0018 정답 500 → "1000", c0022 정답 400 → "404". 근거가 빠지자 값을 지어냈다
- **맞힘 (정확도 ≥ 0.5) 22문항** 중
  - 정답 핵심어가 문서의 다른 곳에 남아 있음: 15문항 (근거 줄 말고도 코드 예시·다른 문단에 같은 값이 나옴)
  - **정답 핵심어도 문맥에 없는데 맞힘 (기억 의존 의심): 7문항** — c0004, c0026, c0030, c0039, c0145, c0147, c0148
- code·fact 유형은 근거 한 줄에 값이 몰려 있어 대부분 NOT FOUND 가 됐고 (정확도 0.33·0.55), procedure·multi 는 정보가 문서 여러 곳에 흩어져 있어 근거 줄을 지워도 대부분 맞혔다 (1.00·0.92)

근거가 지워졌는데 맞힌 22문항

| qid | type | 정확도 | 문맥에 핵심어 | 기억 의존 의심 | 지운 줄/토큰 | 답변 (앞부분) |
|---|---|---|---|---|---|---|
| c0001 | fact | 1.00 | 있음 | - | 1 / 46 | DUMMY_HASH |
| c0003 | procedure | 1.00 | 있음 | - | 1 / 81 | 1. It receives the bearer token through `oauth2_scheme`. 2. It decodes the token with `jwt.decode(token, SECRET_KEY, ... |
| c0004 | fact | 1.00 | 없음 | 의심 | 1 / 21 | The last middleware registered wraps all the others. |
| c0006 | procedure | 1.00 | 있음 | - | 6 / 139 | 1. Import `time`, `FastAPI`, and `Request`, then create your app. 2. Define an async middleware that records `time.pe... |
| c0015 | multi | 1.00 | 있음 | - | 2 / 92 | The simple password-flow login returns the username itself as `access_token` (with `token_type="bearer"`). The JWT ve... |
| c0019 | code | 1.00 | 있음 | - | 1 / 15 | `*.example.com` |
| c0024 | procedure | 1.00 | 있음 | - | 2 / 95 | 1. Catch the exception in a `try/except` around `yield`. 2. After any logging or cleanup, re-raise it with `raise`. I... |
| c0025 | fact | 1.00 | 있음 | - | 1 / 49 | `@pytest.mark.anyio` |
| c0026 | fact | 1.00 | 없음 | 의심 | 1 / 54 | asgi_lifespan |
| c0028 | code | 1.00 | 있음 | - | 1 / 19 | StaticPool |
| c0029 | procedure | 1.00 | 있음 | - | 3 / 50 | 1. Create a pytest `session` fixture that builds an in-memory SQLite engine and creates the tables: ```python @pytest... |
| c0030 | fact | 1.00 | 없음 | 의심 | 1 / 37 | The replacement dependency’s parameters. |
| c0032 | code | 1.00 | 있음 | - | 1 / 19 | 10 |
| c0033 | code | 1.00 | 있음 | - | 1 / 11 | client.websocket_connect("/ws") |
| c0035 | fact | 1.00 | 있음 | - | 1 / 22 | 400 |
| c0038 | procedure | 1.00 | 있음 | - | 1 / 43 | 1. The frontend sends the user’s `username` and `password` as **form fields** to `POST /token` (not as JSON). 2. The ... |
| c0039 | multi | 1.00 | 없음 | 의심 | 6 / 69 | In the simple password-flow tutorial, wrong credentials at `/token` return **400**. In the JWT tutorial, failed authe... |
| c0040 | multi | 1.00 | 있음 | - | 2 / 100 | Use `httpx.AsyncClient` with `ASGITransport(app=app)`, because the test itself is async and must `await` the database... |
| c0145 | procedure | 1.00 | 없음 | 의심 | 3 / 67 | 1. Define the app’s lifespan logic, including startup work before `yield` and cleanup after it. 2. Create a `TestClie... |
| c0146 | procedure | 1.00 | 있음 | - | 2 / 96 | 1. Set `app.dependency_overrides` using the original dependency callable as the key and a replacement callable as the... |
| c0147 | procedure | 1.00 | 없음 | 의심 | 2 / 41 | 1. Set the dependency’s `scope` to `"function"` in `Depends()`. 2. Its cleanup code will then run before the response... |
| c0148 | multi | 0.67 | 없음 | 의심 | 2 / 100 | Using `TestClient(app)` without a `with` context manager does not run lifespan; use `with TestClient(app) as client:`... |

- 기억 의존 의심 7문항은 "의심" 이다. 핵심어 문자열이 없을 뿐, 같은 내용이 다른 표현으로 남아 있을 수 있다 (예: c0004 "last middleware registered" 는 문서의 다른 문장에서 추론 가능할 수 있음).
  다만 empty 에서는 35문항 모두 NOT FOUND 였는데, 문맥이 일부 남으면 일부 문항은 기억으로 빈칸을 채운다는 신호다
- **함의**: 많이 지우는 압축(LLMLingua-2 등)에서는 정확도 유지율이 근거 보존을 과대평가할 수 있다. 압축기 결과를 볼 때 `memory_suspect` 비율을 함께 본다

## 재현성 (none 두 번)

같은 설정(reasoning_effort none, temperature 0, seed 42)으로 none 을 한 번 더 돌려(`20261019-234729`) 문항별로 비교했다.

| 비교 | 다른 문항 수 (/35) | 문항 |
|---|---|---|
| 답변 문자열 | 10 | c0006, c0015, c0024, c0029, c0038, c0040, c0145, c0146, c0147, c0148 |
| key_fact 판정 | 1 | c0015 (fact 1: O → X) |
| 문항 정확도 | 1 | c0015 (1.00 → 0.50) |
| O/X 판정 | 0 | |
| 평균 정확도 | | 1.000 → 0.986 |

- temperature 0 인데도 긴 답(procedure 7, multi 3)은 문자열이 달라졌다. 짧은 답(fact·code 23문항)은 모두 같았다.
  temperature 1 이던 부록 A 의 재현성(11문항)과 거의 같아, temperature 를 0 으로 둔 효과는 작다
- 정확도가 바뀐 문항은 이번에도 c0015 하나다. rule·rule_fm_all 의 c0015 하락은 반복 실행 차이와 같은 크기다
- 정확도가 바뀐 문항이 1개라(기준 3개 이상이면 반복 확대) 반복 횟수는 늘리지 않는다

## 실행 환경

- git commit: `d94173d` (summary.json git_head, 실행 중 코드 변경 없음)
- 평가셋: `data/evalsets/claude-v1/qa_dev.json` sha256 `2ee1f1a7e1abf8a384336763efc8d251a86f8079988692a7e2f0e6fe70c2966e` (git 에 저장된 LF 기준)
- 답변: `gpt-6-luna` (https://api.openai.com), 응답에 적힌 모델(`answer_model`)도 `gpt-6-luna`
- 판정: `deepseek-flash` (https://api.deepseek.com), 응답에 적힌 모델도 `deepseek-flash`
- 실제 생성 조건 (summary.json `config.sampling`)
  - answer: temperature 0.0, seed 42, reasoning_effort `none`, `max_completion_tokens` 512 (`max_tokens` 는 서버가 거부해 바꿔 보냄)
  - judge (O/X, key_facts): temperature 0.0, seed 42, reasoning_effort 보내지 않음(서버 기본값), `max_tokens` 4096
- 토크나이저: `tiktoken:o200k_base`. usage 는 모든 호출이 서버 보고값 (`*_usage_estimated` 0)
- 임베딩: bge-m3 (로컬 Ollama 0.40.5)
- answer 프롬프트 v1 `d12495bd1412`, fact_judge_v2 `7e441ad04bab`
- 실행 머신: Windows 11 Pro 10.0.26200

## API 사용 토큰 (서버 보고값)

워밍업 호출(run 마다 1회)은 빼고 trial 기록 합계다.

| run | 답변 입력 | 답변 출력 | 채점 입력 | 채점 출력 (생각 토큰 포함) |
|---|---|---|---|---|
| 20261019-231040 none | 77,273 | 1,358 | 18,674 | 6,317 |
| 20261019-231040 rule | 61,899 | 1,359 | 18,687 | 5,340 |
| 20261019-231040 rule_fm_all | 58,697 | 1,355 | 18,659 | 8,766 |
| 20261019-231040 empty | 4,198 | 175 | 1,995 | 344 |
| 20261019-231040 drop_evidence | 75,566 | 1,321 | 16,687 | 9,391 |
| 20261019-234729 none (재현성) | 77,273 | 1,341 | 18,596 | 6,355 |
| **합계** | **354,906** | **6,909** | **93,298** | **36,513** |

- 생각 토큰을 끄자 답변 출력이 부록 A(평균 59 토큰)보다 줄었다 (평균 39 토큰)

## 다음에 할 일

1. 사람 라벨링: `docs/results/judge_check_v3.csv` (부록 A run 의 none 답변). 이번 run 의 답변과는 10문항 문자열이 다르지만 judge 검증 목적에는 그대로 쓸 수 있다
2. LLMLingua-2 를 이 설정(reasoning_effort none)으로 측정하고 `memory_suspect` 비율을 함께 본다
3. 절감률 목표(50%)까지 rule 만으로는 거리가 멀다 (20~24%)

## 부록 A: temperature 1 측정 (run 20261019-203350)

처음 측정한 결과. 답변 gpt-6-luna 에 reasoning_effort 를 보내지 않았고(서버 기본값), temperature 0 은 서버가 거부해 서버 기본값 1 로 생성됐다.
본문 결과와 같은 평가셋·채점 조건이다. 압축기는 none, rule, rule_fm_all.

claude-v1 평가셋 dev 35문항에 대해 압축 없음(none), 규칙 기반 압축(rule), 머리말 전체 삭제 규칙(rule_fm_all)을 비교한 기준선.

- rule: 현재 기본값. 머리말 중 title·description·tags 를 남긴다
- rule_fm_all: 머리말을 통째로 지운다 (v1 문서의 rule 과 같은 동작)
- run: `20261019-203350` (none, rule, rule_fm_all), 재현성 확인용 none 한 번 더: `20261019-205759` (29문항) + `20261019-213343` (6문항).
  재현성 run 은 30번째 문항에서 네트워크 오류(api.openai.com DNS 조회 실패)로 중단돼, 남은 6문항(`--ids`)을 따로 돌려 합쳤다. `results/` 는 커밋하지 않음
- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split dev --compressors none,rule,rule_fm_all --semantic`
- 답변: gpt-6-luna, answer_prompt v1, 답변 최대 512 토큰 (`max_completion_tokens`). **temperature 는 서버가 0 을 거부해 보내지 않음 (서버 기본값 1)**, seed 42
- 판정: deepseek-flash, per_fact, fact_judge_v2, temperature 0, seed 42, 출력 최대 4096 토큰 (생각 토큰 포함). 답변이 NOT FOUND 뿐이면 judge 없이 0

### 결과

| 지표 | none | rule | rule_fm_all |
|---|---|---|---|
| 평균 입력 토큰 | 2208.8 | 1769.5 | 1678.1 |
| 입력 토큰 절감률 | 0.0% | 19.89% | 24.03% |
| 순 입력 토큰 절감률 | 0.0% | 19.89% | 24.03% |
| 과금 입력 토큰 절감률 (`billed_input_reduction_pct`) | - | 19.90% | 24.04% |
| 의미 유사도 | 1.000 | 0.967 | 0.947 |
| 핵심 개체 보존율 | 1.000 | 1.000 | 1.000 |
| 의미 손실 | 0.000 | 0.033 | 0.054 |
| 의미 손실 5% 이내 문항 비율 | 100% | 100% | 54.3% |
| 답변 정확도 (잠정) | 1.000 | 1.000 | 0.986 |
| 정확도 유지율 (잠정) | - | 100.0% | 98.6% |
| NOT FOUND 비율 | 0.0% (0/35) | 0.0% (0/35) | 0.0% (0/35) |
| 정확도 fact (n=11) | 1.000 | 1.000 | 1.000 |
| 정확도 code (n=12) | 1.000 | 1.000 | 1.000 |
| 정확도 procedure (n=8) | 1.000 | 1.000 | 1.000 |
| 정확도 multi (n=4) | 1.000 | 1.000 | 0.875 |
| 정확도 type 균등 | 1.000 | 1.000 | 0.969 |
| 답변 잘림 (512 토큰 도달) | 0 | 0 | 0 |
| judge 호출 key_facts / O·X / NOT FOUND 로 생략 | 58 / 12 / 0 | 58 / 12 / 0 | 58 / 12 / 0 |
| judge 응답 못 읽음 | 0 | 0 | 0 |

- 입력 토큰은 채팅 템플릿을 포함한 전체 messages 기준 (`tiktoken:o200k_base`). 절감률은 문항별 비율의 평균이 아니라 전체 합의 비율
- 과금 입력 토큰 절감률은 서버가 보고한 `prompt_tokens` 기준. 토크나이저 추정 절감률과 차이 0.01%p 이하
  (서버 보고값이 문항당 정확히 1 토큰 적다. 예: none 평균 2207.8 vs 추정 2208.8)
- 정확도 유지율 = 압축 평균 정확도 / none 평균 정확도. rule 은 LLM 을 쓰지 않으므로 순 절감률 = 입력 절감률
- 의미 유사도는 로컬 Ollama bge-m3 임베딩

### 지연 시간 (초)

API 호출이라 v1(로컬 CPU)과 달리 비교할 수 있다. 같은 문항을 압축기 순서대로 바로 이어 부른 값이다.

| 압축기 | TTFT 평균 | TTFT 중앙값 | 전체 평균 | 전체 중앙값 | 평균 출력 토큰 |
|---|---|---|---|---|---|
| none | 2.22 | 1.94 | 2.51 | 2.01 | 59.0 |
| rule | 2.16 | 2.04 | 2.44 | 2.15 | 56.9 |
| rule_fm_all | 1.98 | 1.84 | 2.22 | 1.95 | 56.0 |

- 입력이 20~24% 줄어도 지연 시간 차이는 0.1~0.3초로, 네트워크·서버 변동과 구분하기 어렵다

### none 보다 정확도가 떨어진 문항

| qid | type | none → 압축 | 원인 |
|---|---|---|---|
| c0015 | multi | 1.00 → 0.50 (rule_fm_all) | fact 1 "JWT 버전은 create_access_token 으로 만든 서명된 JWT 를 돌려준다" 불충족. 세 답변 모두 `create_access_token` 을 언급하지 않고 "signed, expiring JWT" 라고만 했는데, judge 가 none·rule 은 O, rule_fm_all 은 X 로 갈렸다. rule_fm_all 답변은 rule 답변과 거의 같다(`token_type` 한 구절만 더 있음). 압축 손실이 아니라 경계에 있는 fact 의 judge 판정 흔들림으로 보인다 (재현성 run 에서도 none 끼리 같은 fact 가 O → X 로 바뀜) |

rule 은 정확도가 떨어진 문항이 없다.

### 재현성 (none 두 번)

같은 설정으로 none 을 한 번 더 돌려 문항별로 비교했다. gpt-6-luna 는 temperature 를 고정할 수 없다(서버 기본값 1). seed 는 보내지만 같은 답을 보장하지 않는다.

| 비교 | 다른 문항 수 (/35) | 문항 |
|---|---|---|
| 답변 문자열 | 11 | c0003, c0006, c0015, c0024, c0029, c0038, c0039, c0040, c0145, c0146, c0147 |
| key_fact 판정 | 1 | c0015 (fact 1: O → X) |
| 문항 정확도 | 1 | c0015 (1.00 → 0.50) |
| O/X 판정 | 0 | |
| 평균 정확도 | | 1.000 → 0.986 |

- 답변 문자열이 바뀐 11문항은 모두 긴 답(procedure 8, multi 3)이다. 짧은 답(fact·code 23문항)은 두 번 모두 같았다
- 정확도가 바뀐 문항은 c0015 하나로, rule_fm_all 의 하락과 같은 문항·같은 fact 다.
  따라서 rule_fm_all 의 정확도 차이 0.014 (1.000 vs 0.986) 는 none 을 반복했을 때의 차이와 같은 크기이고, 압축 효과로 볼 수 없다
- 비결정성이 정확도에 준 영향은 1문항(기준: 3문항 이상이면 반복 횟수 확대)이라 지금은 반복 횟수를 늘리지 않는다.
  다만 none·rule 정확도가 모두 1.000 으로 천장에 붙어 있어, 압축 기법 간 차이를 보려면 더 어려운 문항(test split, multi)이 필요하다

### 실행 환경

- git commit: 실행 시작 `6ca09ba`, summary.json 의 git_head `16b5161`
  (git_head 는 실행이 끝날 때 읽는다. 그사이 커밋은 실험과 무관한 `label_sheet.py`·`judge_agreement.py`·테스트뿐)
- 평가셋: `data/evalsets/claude-v1/qa_dev.json` sha256 `2ee1f1a7e1abf8a384336763efc8d251a86f8079988692a7e2f0e6fe70c2966e` (git 에 저장된 LF 기준)
- 답변: `gpt-6-luna` (https://api.openai.com). 서버가 응답에 적은 모델(`answer_model`)도 `gpt-6-luna`
- 판정: `deepseek-flash` (https://api.deepseek.com). 응답에 적힌 모델도 `deepseek-flash` (세부 버전은 응답에 없음)
- 실제 생성 조건 (summary.json `config.sampling`)
  - answer: temperature `null`(서버 기본값, 요청 0.0 거부), seed 42, `max_completion_tokens` 512
  - judge (O/X, key_facts): temperature 0.0, seed 42, `max_tokens` 4096
- 토크나이저: `tiktoken:o200k_base`. 연결 확인에서 c0001 입력 추정 2105 vs 서버 보고 2104 (−0.05%)
- usage: 모든 호출이 서버 보고값 (`answer_usage_estimated` 0, `judge_usage_estimated` 0)
- 임베딩: bge-m3 `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`, Ollama 0.40.5 (로컬)
- answer 프롬프트 v1 `d12495bd1412`, fact_judge_v2 `7e441ad04bab`
- 실행 머신: Windows 11 Pro 10.0.26200

### API 사용 토큰 (서버 보고값)

워밍업 호출(run 마다 1회)과 연결 확인 호출은 빼고 trial 기록 합계다. 답변 모델과 채점 모델은 토크나이저가 달라 서로 더하지 않는다.

| run | 답변 입력 | 답변 출력 | 채점 입력 | 채점 출력 (생각 토큰 포함) |
|---|---|---|---|---|
| 20261019-203350 none | 77,273 | 2,066 | 18,677 | 8,816 |
| 20261019-203350 rule | 61,899 | 1,993 | 18,389 | 6,748 |
| 20261019-203350 rule_fm_all | 58,697 | 1,961 | 18,396 | 5,753 |
| 재현성 none (두 run 합) | 77,273 | 2,104 | 18,757 | 5,020 |
| **합계** | **275,142** | **8,124** | **74,219** | **26,337** |

- 호출 수: 답변 140회 (+ 워밍업 3), 채점 280회 (key_facts 232, O/X 48)
