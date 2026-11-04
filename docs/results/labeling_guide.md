# 라벨링 안내

사람이 채우는 시트 두 개의 기준이다. 다 채우면 `python src/label_report.py` 로 집계한다 ([집계](#집계)).

| 시트 | 채울 열 | 무엇을 보나 |
|---|---|---|
| [`judge_check_test.csv`](judge_check_test.csv) | `human` (O/X), `메모` | judge(deepseek-flash)의 key_fact 판정이 맞는지 |
| [`test_error_review.csv`](test_error_review.csv) | `사람 분류` (1~5), `메모` | test_v1 압축 오답이 왜 틀렸는지 |

공통
- 한 행씩 독립으로 본다. 같은 문항의 다른 행을 보고 맞추지 않는다.
- 판단이 어려우면 가장 가까운 값을 넣고 `메모` 에 이유를 쓴다. 빈칸으로 두지 않는다.
- Excel 로 열어도 된다. 저장할 때 CSV 를 유지한다 (UTF-8 이 아니어도 집계 스크립트가 읽는다).

## 1. judge 검증: `judge_check_test.csv`

test_v1(생각 끔)과 luna 기본 설정 run 에서 judge 가 채점한 key_fact 80개다. 담당자 A~D 가 20행씩 맡는다.
- **judge 판정은 시트에 없다** (블라인드). 판정은 `judge_check_test_key.csv` 에 `row_id` 로 따로 있다. 라벨을 다 채울 때까지 열지 않는다.
- NOT FOUND 답변은 judge 가 채점하지 않았으므로 들어 있지 않다.

열
- `질문`, `참고 정답`: 문항 정보. 참고 정답은 판단을 돕는 용도이고, 채점 대상은 `핵심 사실` 하나다.
- `핵심 사실`: 이 행에서 확인할 사실 하나 (`fact_idx` 는 문항의 몇 번째 사실인지, 0 부터).
- `모델 답변`: 채점할 답변. `설정`(생각 끔 / 기본)과 `압축 조건` 은 참고용이다.

### 라벨 기준

**모델 답변이 이 핵심 사실을 의미상 전달했으면 O, 아니면 X.**

- 표현이 달라도 의미가 같으면 **O**
- 관련 단어만 있고 사실을 말하지 않으면 **X**
- 사실과 모순되면 **X**

예
| 핵심 사실 | 모델 답변 | 라벨 | 이유 |
|---|---|---|---|
| The keep-alive ping is sent every 15 seconds. | 15 seconds | O | 표현은 짧지만 같은 사실 |
| A mounted sub-application keeps its own OpenAPI schema and docs UI. | The sub-app has its own `/docs`. | O | 다른 표현, 같은 의미 |
| FastAPI keeps only the text before the first \f for the docs. | Use `\f` in the docstring. | X | `\f` 는 나오지만 "앞부분만 남긴다"는 사실을 말하지 않음 |
| HTTPBasic sends WWW-Authenticate: Basic. | It sends `WWW-Authenticate: Bearer`. | X | 사실과 모순 |

- 답변의 다른 부분이 틀렸더라도 이 핵심 사실을 전달했으면 O 다 (사실 하나씩 본다).
- 답변이 사실을 말하면서 "문서에 없다"는 말을 덧붙여도, 사실을 전달했으면 O 다.

## 2. 오답 분류: `test_error_review.csv`

test_v1 에서 LLMLingua-2 세 조건(r50, r30, rule>llmlingua2)의 accuracy < 0.5 trial 50개다. `근거 인용문 원문` 과 `압축 후 같은 구절` 을 나란히 보고 고른다.
- `자동 분류` 열(A/B/C)은 참고용이다. 사람 분류를 자동 분류에 맞출 필요는 없다.

| 값 | 분류 | 기준 |
|---|---|---|
| 1 | 정답 구절 삭제 | 정답에 필요한 단어·값이 압축 후 문맥에 없다 |
| 2 | 연결어·조건 삭제 | 정답 단어는 남았지만, 그것과 질문을 잇는 말(주어·동사·조건절·괄호 구조)이 지워졌다 |
| 3 | 표기 분해 | 정답 표기가 쪼개졌다. 버전 번호의 점(`0.95.0` → `0 95 0`), 하이픈 이름, 식별자 |
| 4 | 정답 남음·추론 가능한데 틀림 | 압축 후 문맥만으로 정답을 낼 수 있었는데 모델이 틀렸거나 NOT FOUND 를 냈다 |
| 5 | 기타 | 위에 없음: 채점 문제, 질문 해석 차이, 근거와 무관한 오답 등. 메모에 이유 |

- 둘 이상에 해당하면 **정답에서 가장 먼 쪽**을 고른다 (1 > 3 > 2 > 4 순). 예: 정답 값 일부가 지워지고 표기도 쪼개졌으면 1.
- 압축 후 같은 구절이 `(없음)` 이어도 정답이 문맥의 다른 곳(코드 예시 등)에 남아 있을 수 있다. 다른 곳에 남아 있으면 1 이 아니라 2·3·4 중에서 고른다.

## 집계

라벨이 채워진 뒤 실행한다 (API 호출 없음).

```
EVAL_DIR=data/evalsets/claude-v1 python src/label_report.py
```

결과는 `docs/results/label_report.md` 에 쓴다. 사람 라벨이 일부만 채워져도 돌아가고, 채워진 행만 센다.
