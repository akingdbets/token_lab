# Telegraph English (TE) 탐색 실험

> **탐색 실험, test 동결 후 추가.** `test-v1-freeze` 이후 test 결과를 본 뒤에 더한 실험이다. 사전 계획에 없었으므로 test_v1 의 주 결과를 바꾸지 않는다.
>
> **정확도는 잠정치다.** 채점은 deepseek-flash (fact_judge_v2, per_fact), 사람 라벨 검증 전.

## 요약

- **TE 는 이 문서에서 압축이 되지 않았다.** test 문항 문맥 합이 319,186 → 340,007 토큰으로 **6.5% 늘었다** (답변 입력 기준 −6.2%).
  - 설명 문장의 단어는 10.1% 줄었지만, TE 의 대문자 기본값 때문에 `o200k_base` 토큰은 8.9% 늘었다. 같은 TE 를 소문자로 바꾸면 2.3% 절감이다.
  - 출력은 사실상 원문 문장을 대문자로 바꾸고 관사·연결어 일부만 뺀 형태다. 기호(→ ∧ ¬ …)는 43페이지에 138개뿐이다.
- **정확도는 떨어지지 않았다.** te 0.987 [0.975, 0.998], 유지율 100.6%, none 대비 McNemar p = 0.69 (잠정). te 에서 틀린(accuracy < 0.5) 문항이 없다.
- **그래서 ll2_matched 는 만들 수 없었다.** TE 의 절감률이 음수라 같은 절감률의 LLMLingua-2 비율이 없다. 대신 rule>llmlingua2 (47.2% 절감) 와 짝 비교했다 (te 만 맞힘 14 / rule>llmlingua2 만 맞힘 3, p = 0.013). 절감률이 크게 달라 공정한 비교가 아니다.
- **비용은 순손실이다.** 변환 $0.105 (43페이지) 를 139문항에 상각하면 문항당 $0.00104 로 none($0.00027)의 3.8배다. 답변 비용도 none 보다 비싸 손익분기 질의 수가 없다.
- **결론:** 저자 프롬프트(compression_v5)를 gpt-6-luna 기본 설정으로 FastAPI 기술 문서에 적용하면 "대문자로 다시 쓴 원문"이 되어 압축 효과가 없다. 논문의 약 50% 절감과 다른 결과다 (원인 후보는 [해석](#해석)).

## 설정

| 항목 | 값 |
|---|---|
| 논문 | Arbuzov 외, "Telegraph English: Semantic Prompt Compression via Structured Symbolic Rewriting", arXiv:2605.04426 |
| 프롬프트 | 저자 공개 `compression_v5.txt` 그대로 ([sibmike/telegrapher](https://github.com/sibmike/telegrapher) `7aadc09`, CC BY-SA 4.0) + 이 프로젝트의 `technical_rules_v1.md` (앞에 붙임). 해시 `65fa8af4fcc0`. 실험 전에 커밋 (`5c4c4e4`) |
| 메시지 구조 | system = 규칙 + 저자 프롬프트, user = 본문 조각 (저자 참고 구현 `sync.py` 와 같음) |
| 변환 모델 | gpt-6-luna, 기본 설정 (temperature·reasoning_effort 안 보냄, seed 42, `max_completion_tokens` 4096) |
| 변환 단위 | test 문항의 근거 페이지 43개, 페이지당 1회 (`data/te_pages/`). 코드 블록을 뺀 본문을 500단어 이하 조각 78개로 |
| 답변 | gpt-6-luna 기본 설정, answer 프롬프트 v1, test 139문항, te 1회 (run `20261104-143341`) |
| 비교 | none, rule, rule>llmlingua2 = [test_v1_default](test_v1_default.md) 의 luna (기본) run `luna-default-20261103` (같은 설정이라 다시 돌리지 않음) |

기술 문서용 규칙 (`src/prompts/telegraph/technical_rules_v1.md` 와 후처리)
- 코드 블록은 `⟦CODE-n⟧` 자리표시자로 빼서 보내고 변환 뒤 원문 그대로 되돌린다
- `## Document:` 경계 줄은 변환에 보내지 않는다
- 식별자는 원문 대소문자·철자 유지 (TE 의 대문자 기본값을 적용하지 않음). 후처리에서도 대소문자만 다른 식별자를 원문 표기로 되돌린다
- 숫자·버전·하이픈 이름·따옴표 값은 그대로, 사실을 빼거나 만들지 않음

출처 메모: 논문 본문에는 저장소 링크가 없다. 저자 이름(Arbuzov, Shvets, Bei)이 적힌 논문 원고와 프롬프트·참고 구현이 함께 있는 GitHub 저장소 `sibmike/telegrapher` 를 찾아 썼다. 저장소 README 는 `compression_v5.txt` 를 "canonical Telegraph English grammar" (430행, 기호 약 40개, 12항목 품질 점검) 로 소개하고, 논문 설명과 같다.

## 1. 변환 결과와 점검

| 항목 | 값 |
|---|---|
| 페이지 / 조각 | 43 / 78 (잘린 호출 0) |
| 변환 토큰 | 입력 471,143, 출력 114,943 (그중 생각 46,577) |
| 변환 비용 | $0.105 (luna $0.10 / $0.50 per 1M) |
| 코드 블록 | 모두 원문 그대로 남음. 단 2페이지(`deployment/docker.md`, `integrations/websockets.md`)는 모델이 자리표시자 12개를 모두 빠뜨려, 후처리가 코드 블록을 페이지 끝에 붙였다 (설명과의 위치 관계를 잃음. 점검의 "바이트 일치"가 이 2페이지에서 거짓) |
| 문서 경계 수 | 139문항 모두 원문과 같음 |
| 원문 토큰 중 TE 에서 사라진 것 | 4,548 중 173 (3.8%). 식별자·숫자·하이픈 이름·따옴표 값 (`data/te_pages/index.json` 페이지별 `checks.missing`) |

토큰 (설명 부분, 코드 블록 22,054 토큰은 그대로)

| | 원문 | TE | 변화 |
|---|---|---|---|
| 단어 | 26,329 | 23,677 | −10.1% |
| 토큰 (`o200k_base`) | 58,932 | 64,194 | **+8.9%** |
| TE 를 소문자로 바꾸면 | | 57,556 | −2.3% |
| 기호 (→ ⇒ ∴ ∵ ↑ ↓ ∧ ∨ ¬ ≈ ≠ ⇔ ↛) | | 138 | |

- 페이지별 설명 토큰 비(TE / 원문)는 0.98 ~ 1.23 이다. 가장 늘어난 페이지는 `deployment/docker.md` (1.23) 다.
- 예 (`app-structure/path-operation-configuration.md`):
  > 원문: Every *path operation* decorator ... accepts parameters that configure ...
  > TE: `EVERY PATH operation DECORATOR (`@app.get()`, ...) ACCEPTS PARAMETERS CONFIGURING ITS OPENAPI AND DOCS UI APPEARANCE; PARAMETERS BELONG TO THE **DECORATOR**, NOT YOUR FUNCTION.`
  - 원문 문장을 대문자로 바꾸고 일부 단어만 줄였다. YAML 머리말은 거의 그대로 남았다.
  - "operation" 이 소문자로 남은 것은 후처리 때문이다. 원문 백틱 안에 나온 단어(`path operation` 등)도 식별자 후보로 잡아 대소문자를 되돌렸다. 토큰 수를 줄이는 쪽이라 결과에는 유리하게 작용했다 (식별자 후보 규칙의 한계).

## 2. 표 1: 조건별 결과 (정확도 잠정)

| 조건 | 입력 토큰 절감 [CI] | 문맥 토큰 절감 | 정확도 [95% CI] | 유지율 [CI] | none 대비 McNemar b/c | p | Holm p | NOT FOUND |
|---|---|---|---|---|---|---|---|---|
| none | - | - | 0.981 [0.966, 0.994] | - | - | - | - | 0.0% |
| rule | 20.8% [20.2, 21.4] | 21.9% | 0.993 [0.983, 1.000] | 101.2% [99.9, 102.6] | 1/5 | 0.22 | 0.44 | 0.0% |
| rule>llmlingua2 | 47.2% [46.4, 47.9] | 49.7% | 0.921 [0.877, 0.960] | 93.9% [89.3, 97.9] | 12/4 | 0.077 | 0.23 | 3.6% |
| **te** | **−6.2%** [−6.6, −5.7] | **−6.5%** | **0.987** [0.975, 0.998] | 100.6% [99.1, 102.1] | 2/4 | 0.69 | 0.69 | 0.0% |
| ll2_matched | 만들 수 없음 (TE 절감률이 음수) | | | | | | | |

- 정확도는 문항 paired bootstrap 10,000회 (seed 42). McNemar 는 완전 정답 짝지음, b/c = none 만 / 압축만 맞힘. Holm 은 rule, rule>llmlingua2, te 3개로 보정.
- none·rule·rule>llmlingua2 는 [test_v1_default](test_v1_default.md) 와 같은 run 이다. 이 표의 Holm p 는 검정 묶음이 달라 그 문서와 다르다.

**te vs LLMLingua-2 짝 비교 (계획 변경)**

계획은 te 와 같은 절감률의 ll2_matched 와 짝 비교였다. 만들 수 없어서 rule>llmlingua2 와 비교했다.

| 비교 | te 만 완전 정답 | 상대만 완전 정답 | McNemar p |
|---|---|---|---|
| te vs rule>llmlingua2 | 14 | 3 | 0.013 |
| te vs rule | 0 | 2 | 0.50 |

- rule>llmlingua2 는 문맥을 49.7% 줄이고 te 는 6.5% 늘렸다. 같은 예산 비교가 아니므로 "TE 가 LLMLingua-2 보다 정확하다"는 결론으로 쓰지 않는다.

## 3. 비용

문항당, 서버 보고 토큰, luna 단가 ($0.10 입력 / $0.50 출력 per 1M). judge 비용은 넣지 않았다.

| 조건 | 답변 입력 | 답변 출력 (생각 포함) | 답변 비용 | 변환 상각 | 합 | none 대비 |
|---|---|---|---|---|---|---|
| none | 2,417 | 61.2 | $0.000272 | - | $0.000272 | - |
| rule | 1,915 | 62.1 | $0.000222 | - | $0.000222 | −18.3% |
| rule>llmlingua2 | 1,275 | 94.3 | $0.000175 | - | $0.000175 | −35.9% |
| te | 2,566 | 66.4 | $0.000290 | $0.000752 | $0.001042 | **+283%** |

- 변환 상각 = 변환 비용 $0.1046 / 139문항. 페이지를 여러 문항이 나눠 쓰므로 실제 운영에서 질의가 많아지면 상각분은 줄어든다.
- **손익분기 질의 수: 없음.** te 는 답변 한 번에도 none 보다 $0.000018 비싸다. 질의가 아무리 많아도 변환 비용을 회수하지 못한다.

## 4. 유형별 정확도 (잠정)

| 유형 | none | rule | rule>llmlingua2 | te |
|---|---|---|---|---|
| fact (38) | 1.000 | 1.000 | 0.895 | 1.000 |
| code (42) | 1.000 | 1.000 | 1.000 | 1.000 |
| procedure (30) | 0.953 | 0.989 | 0.981 | 0.978 |
| multi (29) | 0.958 | 0.976 | 0.772 | 0.958 |

- te 는 모든 유형에서 none 과 같은 수준이다. rule>llmlingua2 가 약한 fact·multi 에서도 떨어지지 않는다.

## 5. 정답 핵심어 위치 A/B/C (te)

| 상태 | trial | 비율 | 정확도 | NOT FOUND |
|---|---|---|---|---|
| A | 123 | 88.5% | 0.985 | 0 |
| B | 5 | 3.6% | 1.000 | 0 |
| C | 11 | 7.9% | 1.000 | 0 |

- **A/B 구분은 te 에서 믿기 어렵다.** 근거 자리 대응(difflib)은 단어를 지우기만 하는 압축을 가정한다. TE 는 다시 쓰기라 대응이 맞지 않는다.
- **C 11 trial 은 모두 맞았다.** 그중 10 은 원문(none) 문맥에서도 정답 핵심어가 매칭되지 않는 문항이다 (중복도 0: c0008, c0009, c0012, c0043, c0049, c0061, c0073, c0102, c0139, c0173. 예 "About 10 seconds" vs 원문 `~10 seconds`). TE 때문에 사라진 것은 c0131 하나다 (6절).
- ll2_matched 의 A/B/C 는 없다. rule>llmlingua2 의 A/B/C 는 [test_v1_default 3절](test_v1_default.md#3-정답-핵심어-위치-abc-별-정확도-잠정) 에 있다.

## 6. 정보 손실 점검

none 문맥에는 정답 핵심어가 있는데 te 문맥에서 사라진 문항:

| qid | 유형 | 정답 | te 정확도 | te 답변 |
|---|---|---|---|---|
| c0131 | fact | ORJSONResponse and UJSONResponse | 1.0 | `ORJSONResponse` and `UJSONResponse` |

- 1문항뿐이고 맞혔다. 설명 문장의 목록이 바뀌었지만 같은 이름이 코드 블록에 남아 있다.
- 핵심어 단위가 아닌 토큰 단위로는 원문 식별자·숫자 등의 3.8% 가 사라졌다 (1절).

## 7. 오답 목록

맞음 = accuracy ≥ 0.5. ll2_matched 대신 rule>llmlingua2 와 비교했다.

- **te 에서만 틀림: 0 문항.** 둘 다 틀린 문항도 없다.
- **rule>llmlingua2 에서만 틀림: 9 문항.** 근거 구절의 원문 · TE · LL2 를 나란히 놓았다 (TE 는 인용문과 단어가 가장 많이 겹치는 줄).

| qid | 유형 | 근거 원문 | TE | rule>llmlingua2 | LL2 답변 |
|---|---|---|---|---|---|
| c0049 | fact | Real environment variables still take precedence over the `.env` file. | REAL ENVIRONMENT VARIABLES STILL TAKE PRECEDENCE OVER `.env` FILE. | environment variables precedence recommend adding python - dotenv … | NOT FOUND |
| c0086 | fact | … migrate to `starlette-graphene3`, which has an almost identical interface | MIGRATE TO `starlette-graphene3`, WITH ALMOST IDENTICAL INTERFACE, | Starlette GraphQLApp deprecated migrate graphene3 identical | graphene3 |
| c0099 | fact | \| 0.128.0 \| `pydantic.v1` dropped too — v2 only \| | \| 0.128.0 \| `pydantic.v1` ALSO DROPPED — v2 ONLY \| | 0 128 0 v2 only | 0.126.0 |
| c0124 | fact | With more than one body parameter, FastAPI expects a JSON object keyed by **parameter names** | WITH >1 BODY PARAMETER, FASTAPI EXPECTS JSON OBJECT KEYED BY PARAMETER NAMES: | tutorial002_py310 py one body parameter FastAPI expects JSON object | `item` and `user` |
| c0168 | multi | FastAPI warns about duplicate operation IDs (`Duplicate Operation ID ... for function ...`) | DURING GENERATION, FastAPI WARNS ABOUT Duplicate Operation IDs | FastAPI duplicate operation IDs ID | NOT FOUND |
| | | `to_remove = f"{tag}-"` | `to_remove = f"{tag}-"` | `to_remove = f"{tag` | |
| c0169 | multi | A client sending an extra field (e.g. `extra=Mr. Poopybutthole`) gets a 422 error | CLIENT SENDING extra FIELD (e.g. `extra=Mr. Poopybutthole`) GETS 422 ERROR, | client extra field 422 error | NOT FOUND |
| | | A request with an unexpected cookie (e.g. a `santa_tracker` cookie) | REQUEST WITH UNEXPECTED Cookie (e.g. `santa_tracker`) OR Header RECEIVES 422 ERROR … | request unexpected cookie santa_tracker | |
| c0170 | multi | `short=1`, `short=True`, `short=true`, `short=on` and `short=yes` all become `True` | AND `short=yes` BECOME `True`; `0`, `false`, `off`, `no` BECOME `False`. | 1 | NOT FOUND |
| c0171 | multi | FastAPI/Starlette add `Content-Length` and, for text types, the charset in `Content-Type`. | FASTAPI/STARLETTE ADD `Content-Length`; FOR text TYPES, ADD CHARSET TO | FastAPI Content | (채점 실패, 맞음 아님으로 셈) |
| c0174 | multi | `timedelta` → total seconds (`float`) | - `timedelta` → TOTAL SECONDS (`float`) | (없음) | NOT FOUND |

- TE 는 인용문의 정답 구절을 대부분 거의 그대로 남겼다. LL2 오답은 test_v1 에서 본 유형(정답 구절 삭제, 연결어 삭제, 구두점 분해)과 같다.

## 해석

- **TE 가 압축되지 않은 이유 (원인 후보)**
  1. **대문자 기본값과 토크나이저:** 최근 BPE 토크나이저(`o200k_base`)는 소문자 영어에 최적화돼 있어, 같은 단어도 대문자면 토큰이 늘어난다. 단어를 10% 줄인 이득이 대문자화로 사라졌다. 논문은 GPT-4 계열 토크나이저로 쟀다.
  2. **변환 모델:** 저자 구현은 o4-mini 로 변환했다. gpt-6-luna 기본 설정은 다시 쓰기보다 원문을 거의 옮기는 쪽이었다 (기호 138개, 단어 −10%).
  3. **기술 문서 규칙:** 식별자·숫자·따옴표 값을 그대로 두라는 규칙과 높은 밀도의 기술 문서가 줄일 여지를 줄였다. 논문은 LongBench-v2 의 일반 장문을 썼다.
  4. **조각 크기:** 500단어 조각(저자 1000단어)은 조각 사이 중복을 지우지 못한다.
- **정확도가 유지된 이유:** 출력이 원문과 거의 같기 때문이다. "TE 가 정보를 잘 보존한다"보다 "TE 변환이 거의 일어나지 않았다"에 가깝다.
- **이 결과로 말할 수 있는 것:** 이 설정(저자 프롬프트 + 기술 문서 규칙 + gpt-6-luna 기본)에서 TE 는 비용을 줄이지 못한다. TE 자체의 일반 성능에 대한 결론은 아니다.

## 한계

- 탐색 실험, test 동결 후 추가. te 1회 답변.
- ll2_matched 를 만들지 못해 같은 예산 비교가 없다.
- 프롬프트는 결과를 보기 전에 고정했고 바꾸지 않았다. 소문자 허용·변환 모델 변경·조각 크기 변경 같은 변형은 결과를 본 뒤의 일이라, 하려면 별도 사후 실험으로 해야 한다.
- 변환 점검의 "사라진 토큰"은 문자열 일치라 대문자로 바뀐 일반 단어 표기는 세지 않는다 (식별자·숫자·하이픈 이름·따옴표 값만).
- 정확도는 잠정치다.

## 재현

```
EVAL_DIR=data/evalsets/claude-v1 python src/compressors/telegraph.py convert --split test   # 과금, data/te_pages 에 있으면 재사용
EVAL_DIR=data/evalsets/claude-v1 python src/compressors/telegraph.py check --split test
EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split test --compressors te
```

표는 te run 과 `luna-default-20261103` 의 trials 를 합쳐 `src/stats.py --boot 10000 --seed 42 --by-type` 로 냈다.
