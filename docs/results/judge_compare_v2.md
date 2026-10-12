# judge 조합 비교 v2 (dev)

같은 none 답변 35개(dev)를 judge 모델 2개 x 모드 2개로 채점한 결과. 채점 기준은 현재 `qa_dev.json` 의 key_facts (58개).

- 정확도 = 충족 key_fact 수 / 전체 key_fact 수 의 문항 평균. 답변이 NOT FOUND 면 0 (NOT FOUND 1문항)
- batch: 한 번에 모든 fact 판정 (응답 index 가 어긋나면 1회 재요청, 그래도 안 되면 fact 별 폴백). per_fact: fact 하나당 호출 1회
- 판정 시간은 judge 호출 벽시계 시간 합계 (모델 로딩 포함 가능)

## 결과

| 조합 | 평균 정확도 | type 균등 | fact (n=11) | code (n=12) | procedure (n=8) | multi (n=4) | 재요청 | 폴백 | judge 호출 | 판정 시간(초) |
|---|---|---|---|---|---|---|---|---|---|---|
| j7b_batch | 0.919 | 0.849 | 1.000 | 1.000 | 0.896 | 0.500 | 0 | 0 | 35 | 444.5 |
| j7b_perfact | 0.914 | 0.844 | 1.000 | 1.000 | 0.875 | 0.500 | 0 | 0 | 58 | 243.2 |
| j14b_batch | 0.871 | 0.800 | 0.909 | 0.917 | 1.000 | 0.375 | 0 | 0 | 35 | 925.7 |
| j14b_perfact | 0.914 | 0.828 | 1.000 | 1.000 | 0.938 | 0.375 | 0 | 0 | 58 | 343.6 |

## 답변

- c0148: 질문 수정 후 재생성한 답변 (run `20261012-143736`, `results/runs/20261012-143736/trials.jsonl`)
- 나머지 34문항: `data/evalsets/claude-v1/review/review_dev_v1.csv` 의 `none_answer` (run `20261011-154540`)
- 답변 생성 설정: qwen2.5:7b, temperature 0, seed 42, answer_prompt v1
- 합친 답변: `results/judge_compare_v2/answers.jsonl` (커밋 안 함)

## 사람 라벨링

- 시트: `docs/results/judge_check_v2.csv` (key_fact 58행). human 열에 O/X, judge 열은 숨기고 라벨링
- 일치율·false positive·false negative·Cohen's kappa: `python src/judge_agreement.py docs/results/judge_check_v2.csv`
- judge 조합끼리 판정이 갈린 key_fact: 11/58행 (사람 라벨로 어느 쪽이 맞는지 가린다)

| qid | type | fact_idx | j7b_batch | j7b_perfact | j14b_batch | j14b_perfact | key_fact |
|---|---|---|---|---|---|---|---|
| c0015 | multi | 0 | O | O | X | X | The simple password-flow login returns the username itself as the access token. |
| c0024 | procedure | 0 | O | O | O | X | The yield is wrapped in try/except. |
| c0033 | code | 0 | O | O | X | O | The test opens the connection with client.websocket_connect("/ws"). |
| c0034 | fact | 0 | O | O | X | O | OAuth2PasswordRequestFormStrict requires grant_type="password". |
| c0039 | multi | 0 | O | X | O | X | The simple password-flow login returns 400 for wrong credentials. |
| c0040 | multi | 1 | X | O | X | O | AsyncClient is used with ASGITransport. |
| c0145 | procedure | 0 | X | X | O | O | The TestClient is used as a context manager: with TestClient(app) as client. |
| c0145 | procedure | 1 | O | X | O | O | Lifespan startup runs when the with block is entered and shutdown when it exits. |
| c0146 | procedure | 2 | X | O | O | O | The overrides are cleared at the end, e.g. with app.dependency_overrides.clear(). |
| c0148 | multi | 1 | O | X | X | X | With httpx.AsyncClient, the app is wrapped in LifespanManager from asgi-lifespan. |
| c0148 | multi | 2 | O | X | X | X | manager.app is passed to ASGITransport. |

## 실행 환경

- git commit: `7553bba61ef3f92accd519805a5131ee65c19540` + 커밋 전 변경 `src/rejudge.py`, `src/judge_agreement.py`, `src/judge_compare.py`
- Ollama: 0.40.3
- qwen2.5:14b: `7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`
- qwen2.5:7b: `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
- key_facts judge 프롬프트: fact_judge_v2 (7e441ad04bab)
- judge 설정: temperature 0.0, seed 42, num_ctx 16384
