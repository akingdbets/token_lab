# LLMLingua-2 dev 측정 v1 (gpt-6-luna 답변 · deepseek-flash 채점)

> **정확도는 잠정치.** deepseek-flash 채점은 사람 라벨 검증 전이다 (`judge_check_v3.csv`). 토큰·의미 손실 지표는 채점과 무관하므로 확정값이다.
>
> **원문 대체 4문항 포함.** LLMLingua-2 를 쓰는 압축기 4개 모두 여러 문서 문항 4개(c0015, c0039, c0040, c0148)에서 압축 결과를 버리고 원문을 썼다 ([원문 대체 문항](#원문-대체-fallback-문항)).
> 아래 절감률·정확도는 이 4문항을 원문 그대로 둔 값이다.

claude-v1 평가셋 dev 35문항. 압축기 6개를 같은 run 에서 돌렸다. 답변·채점 설정은 [`baseline_dev_v2.md`](baseline_dev_v2.md) 본문(생각 토큰 끔, temperature 0)과 같다.

- none: 원문 그대로 (기준선)
- rule: 규칙 기반 정제 (머리말의 title·description·tags 를 남김)
- llmlingua2_r70 / r50 / r30: LLMLingua-2 토큰 분류기로 문맥을 압축. r 은 남길 비율(`retain_ratio`) 0.7 / 0.5 / 0.3
- rule>llmlingua2: rule 다음 LLMLingua-2 (`llmlingua2` = retain_ratio 0.5)
- run: `20261028-195811`. `results/` 는 커밋하지 않음
- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split dev --compressors "none,rule,llmlingua2_r70,llmlingua2_r50,llmlingua2_r30,rule>llmlingua2" --semantic`

## 설정

summary.json `config` 기준.

- 답변: `gpt-6-luna` (https://api.openai.com), temperature 0.0, seed 42, reasoning_effort `none`, `max_completion_tokens` 512, answer 프롬프트 v1 `d12495bd1412`
- 판정: `deepseek-flash` (https://api.deepseek.com), per_fact, fact_judge_v2 `7e441ad04bab`, temperature 0.0, seed 42,
  reasoning_effort 보내지 않음(서버 기본값), `max_tokens` 4096 (생각 토큰 포함). 답변이 NOT FOUND 뿐이면 judge 없이 0
- 토크나이저: `tiktoken:o200k_base`. 임베딩: bge-m3 (로컬 Ollama)
- LLMLingua-2 (`src/compressors/llmlingua2.py`, llmlingua 0.2.2)
  - 모델: `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank`, revision `5f0c827`
  - 장치: CPU (`device=cpu`). 로컬 토큰 분류라 압축 과정 LLM API 토큰은 0 (`compress_llm_tokens` 0 → 순 입력 절감률 = 입력 절감률)
  - force_tokens: `\n`, `?`, `## Document:`, `` ``` ``, `_`, `not`, `no`, `never`, `without`, `unless`, `don't`, `doesn't`, `isn't`, `aren't`, `won't`, `can't`, `cannot`, `default`, `defaults`, `except`, `only`
    (+ 문항마다 질문·문맥의 snake_case/CamelCase 식별자와 코드 블록 마커를 더함, 합계 100개 이하), `force_reserve_digit` true
  - safety_policy_version: `question-identifiers-v1+fenced-code-blocks-v1` (코드 블록은 마커로 바꿔 통째로 보존, 질문의 식별자가 압축 결과에 없으면 원문 대체)

## 결과

| 지표 | none | rule | llmlingua2_r70 | llmlingua2_r50 | llmlingua2_r30 | rule>llmlingua2 |
|---|---|---|---|---|---|---|
| 평균 입력 토큰 | 2208.8 | 1769.5 | 1897.6 | 1631.8 | 1363.5 | 1330.9 |
| 입력 토큰 절감률 (= 순 절감률) | 0.0% | 19.89% | 14.09% | 26.12% | 38.27% | 39.75% |
| 과금 입력 토큰 절감률 (`billed_input_reduction_pct`) | - | 19.90% | 14.10% | 26.13% | 38.29% | 39.76% |
| 문맥 토큰 절감률 | 0.0% | 21.01% | 14.92% | 27.64% | 40.51% | 42.03% |
| 의미 유사도 | 1.000 | 0.967 | 0.959 | 0.937 | 0.908 | 0.932 |
| 핵심 개체 보존율 | 1.000 | 1.000 | 0.914 | 0.900 | 0.843 | 0.900 |
| 의미 손실 | 0.000 | 0.033 | 0.121 | 0.153 | 0.225 | 0.158 |
| 의미 손실 5% 이내 문항 비율 | 100% (35) | 100% (35) | 74.3% (26) | 11.4% (4) | 11.4% (4) | 11.4% (4) |
| 답변 정확도 (잠정) | 1.000 | 1.000 | 0.986 | 0.961 (n=34) | 0.900 | 0.905 |
| 정확도 유지율 (잠정) | - | 100.0% | 98.57% | 96.08% (n=34) | 90.00% | 90.48% |
| binary 정확도 (O/X·단어 일치) | 0.971 | 0.971 | 0.943 | 0.857 | 0.800 | 0.857 |
| NOT FOUND 비율 | 0.0% | 0.0% | 0.0% | 2.9% (1) | 8.6% (3) | 2.9% (1) |
| 기억 의존 의심 (`memory_suspect`) | 0 | 0 | 4 | 4 | 3 | 3 |
| 원문 대체 (fallback) | - | - | 4 | 4 | 4 | 4 |
| 압축 시간 중앙값 (초) | 0.000 | 0.001 | 1.774 | 1.697 | 1.752 | 1.328 |
| 답변 잘림 (512 토큰 도달) | 0 | 0 | 0 | 0 | 0 | 0 |

- 입력 토큰은 채팅 템플릿을 포함한 전체 messages 기준. 절감률은 전체 합의 비율. 과금 기준 절감률과 차이 0.02%p 이하
- 정확도 유지율 = 압축 평균 정확도 / none 평균 정확도 (문항 짝 평균). none 정확도가 1.000 이라 유지율 = 정확도
- **llmlingua2_r50 의 정확도는 34문항 평균이다.** c0003 의 key_fact 3번 판정이 judge 출력 한도(4096 토큰, 생각 토큰 포함)에 걸려
  읽지 못했고(`judge_errors: length`), 문항 정확도가 비어(None) 평균·유지율에서 빠졌다. 나머지 3개 fact 는 모두 O
- 의미 손실 5% 이내 문항 4개(r50·r30·rule>llmlingua2)는 원문 대체 4문항이다. 실제로 압축된 31문항은 모두 5%를 넘는다
- 압축 시간은 CPU 추론. r70 의 평균은 2.19초인데, 첫 문항 c0001 이 모델 로드를 포함해 14.83초라서다. 그래서 중앙값을 적는다
- binary 정확도는 짧은 답을 단어 일치로 본다. 압축과 무관하게 c0004 는 모든 압축기에서 X(답이 문장형)라 none 도 0.971 이다

### 유형별 정확도와 NOT FOUND 비율

| 유형 | none | rule | llmlingua2_r70 | llmlingua2_r50 | llmlingua2_r30 | rule>llmlingua2 |
|---|---|---|---|---|---|---|
| fact (n=11) | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 0.909 / 9.1% | 0.727 / 27.3% | 0.818 / 9.1% |
| code (n=12) | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% |
| procedure (n=8) | 1.000 / 0% | 1.000 / 0% | 0.938 / 0% | 0.952 (n=7) / 0% | 0.938 / 0% | 0.896 / 0% |
| multi (n=4) | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 1.000 / 0% | 0.875 / 0% |
| type 균등 정확도 | 1.000 | 1.000 | 0.984 | 0.965 | 0.916 | 0.897 |

- 칸은 "정확도 / NOT FOUND 비율". multi 4문항은 모두 원문 대체 문항이라 LLMLingua-2 단독 압축기에서는 원문 결과와 같다

## 지연 시간 (초)

| 압축기 | TTFT 평균 | TTFT 중앙값 | 전체 평균 | 전체 중앙값 | 평균 출력 토큰 |
|---|---|---|---|---|---|
| none | 1.55 | 1.50 | 1.85 | 1.63 | 37.1 |
| rule | 1.37 | 1.32 | 1.68 | 1.53 | 39.1 |
| llmlingua2_r70 | 1.37 | 1.32 | 1.67 | 1.46 | 37.4 |
| llmlingua2_r50 | 1.42 | 1.27 | 1.71 | 1.48 | 37.0 |
| llmlingua2_r30 | 1.42 | 1.34 | 1.70 | 1.47 | 35.0 |
| rule>llmlingua2 | 1.47 | 1.27 | 1.77 | 1.42 | 37.3 |

- 답변 지연은 압축기끼리 0.2초 안쪽이다. 반면 LLMLingua-2 압축 시간(CPU 중앙값 1.3~1.8초)이 답변 전체 지연 중앙값(1.4~1.5초)과 비슷해,
  CPU 에서는 압축을 포함한 응답 시간이 none 보다 길다

## 정확도가 1 미만인 문항

| qid | 유형 | 압축기 | 점수 | NOT FOUND | memory_suspect | 비고 |
|---|---|---|---|---|---|---|
| c0003 | procedure | llmlingua2_r50 | - (판정 실패) | - | - | fact 3 판정이 judge 출력 한도에 걸림. 나머지 3/3 O |
| c0015 | multi | rule>llmlingua2 | 0.50 | - | - | 원문 대체 문항(rule 결과로 답함). fact 1 "create_access_token 으로 만든 서명된 JWT" 불충족. 기준선에서도 반복마다 O/X 가 갈린 경계 사례 |
| c0020 | fact | llmlingua2_r50 | 0.00 | O | - | |
| c0020 | fact | llmlingua2_r30 | 0.00 | O | - | |
| c0020 | fact | rule>llmlingua2 | 0.00 | O | - | |
| c0024 | procedure | llmlingua2_r70 | 0.50 | - | - | fact "yield 를 try/except 로 감싼다" 불충족 |
| c0024 | procedure | llmlingua2_r30 | 0.50 | - | - | 〃 |
| c0024 | procedure | rule>llmlingua2 | 0.50 | - | - | 〃 |
| c0031 | fact | llmlingua2_r30 | 0.00 | O | - | |
| c0031 | fact | rule>llmlingua2 | 0.00 | - | - | "WebSocket" 이라고 답함 (정답 WebSocketDisconnect) |
| c0034 | fact | llmlingua2_r30 | 0.00 | O | - | |
| c0146 | procedure | llmlingua2_r50 | 0.67 | - | - | fact "테스트 시작이나 pytest fixture 에서 override 를 설정한다" 불충족 |
| c0146 | procedure | rule>llmlingua2 | 0.67 | - | - | 〃 |

- none·rule 은 1 미만인 문항이 없다. memory_suspect 문항은 모두 정확도 1.0 이다

## 원문 대체 (fallback) 문항

| 압축기 | qid | status |
|---|---|---|
| llmlingua2_r70 | c0015, c0039, c0040, c0148 | `fallback_missing_document_boundary` |
| llmlingua2_r50 | c0015, c0039, c0040, c0148 | `fallback_missing_document_boundary` |
| llmlingua2_r30 | c0015, c0039, c0040, c0148 | `fallback_missing_document_boundary` |
| rule>llmlingua2 | c0015, c0039, c0040, c0148 | `fallback_missing_document_boundary` (llmlingua2 단계만 원문 대체, rule 단계는 적용됨) |

네 문항은 dev 의 multi 4문항 전부이고, 문맥에 문서가 2개 이상 들어간 문항이다 (입력 토큰의 19.8%).

**판정 조건** (`src/compressors/llmlingua2.py:453-468`): 원문의 `"## Document:"` 개수보다 압축 결과의 개수가 적으면 압축 결과를 버리고 원문을 돌려준다.

**원인 (코드 확인, 수정 안 함)**: `"## Document:"` 는 force_tokens (`llmlingua2.py:22`) 라서 지워지지는 않는데, 복원할 때 `##` 가 빠진다.

1. llmlingua 0.2.2 는 여러 WordPiece 로 쪼개지는 force token 을 `[NEWi]` 특수 토큰으로 바꿨다가, 남길 단어를 고른 뒤 원래 문자열로 되돌린다
2. 남긴 단어 목록을 `tokenizer.convert_tokens_to_string` 으로 이어 붙이는데, BERT WordPiece 는 이어 붙이면서 `" ##"` 를 지운다 (`##` 는 BERT 의 하위 단어 접두사)
3. 그래서 문맥 맨 앞에 있는 첫 `## Document:` 만 남고, 공백 뒤에 오는 두 번째 문서부터는 `Document:` 가 된다.
   로컬에서 확인: `convert_tokens_to_string(['## Document:', 'a', 'md', '\n', '## Document:', 'b'])` → `'## Document: a md \n Document: b'`.
   c0015 를 r50 으로 다시 압축해 보면(로컬, API 호출 없음) 원문 2개 → 결과 1개

문서가 하나인 문항은 경계가 맨 앞 한 번뿐이라 영향이 없고, 문서가 둘 이상이면 비율과 상관없이 항상 원문 대체가 된다.

## 해석

### 압축률 r 과 전체 절감률

r 은 문맥 전체가 아니라 **코드 블록을 마커로 바꾼 설명 글**에 적용된다. 코드 블록은 통째로 남고, 식별자·숫자·force token 도 남긴다.

- 문맥에서 fenced code block 이 차지하는 비중(문자 기준, `_split_fenced_blocks` 로 계산): 문항 평균 **32.4%** (중앙값 30.3%, 최소 18.0%, 최대 47.2%)
- LLMLingua-2 가 실제로 줄인 설명 글 비율(trace `reduction_pct_internal`, 압축된 31문항 평균): r70 25.6%, r50 47.5%, r30 69.5%, rule>llmlingua2 51.4%. 목표 비율대로 줄었다
- 그래도 압축된 31문항만 보면 입력 절감률은 r30 47.7%, rule>llmlingua2 45.1% 다. 문맥의 1/3 가까이가 손대지 않는 코드이고, 지시문·질문·문서 머리도 그대로라서다
- 여기에 원문 대체 4문항(입력 토큰의 19.8%)이 0% 로 더해져 35문항 전체는 r30 38.3%, rule>llmlingua2 39.8% 가 된다

따라서 지금 안전 정책(코드 블록 통째 보존)에서는 r30 도 전체 절감 50%에 못 미친다. fallback 을 고쳐도 31문항 기준 값(r30 47.7%) 근처가 상한에 가깝다.

### 목표 대비

목표: 입력 토큰 절감 ≥ 50%, 정확도 유지율 ≥ 90% (의미 손실 ≤ 5% 는 아래 별도 관찰).

| 압축기 | 입력 절감 | 유지율 (잠정) | 절감 50% | 유지율 90% |
|---|---|---|---|---|
| rule | 19.89% | 100.0% | X | O |
| llmlingua2_r70 | 14.09% | 98.57% | X | O |
| llmlingua2_r50 | 26.12% | 96.08% | X | O |
| llmlingua2_r30 | 38.27% | 90.00% | X | O (경계) |
| rule>llmlingua2 | 39.75% | 90.48% | X | O (경계) |

**두 목표를 동시에 만족한 압축기는 없다.** 절감률이 가장 큰 rule>llmlingua2 도 39.8% 이고, r30·rule>llmlingua2 의 유지율은 90% 경계에 걸쳐 있다 (35문항에서 1문항이 0.5 떨어지면 약 1.4%p 바뀜).

### 가장 취약한 유형: fact

fact 는 압축을 세게 할수록 정확도가 떨어진다 (r70 1.000 → r50 0.909 → r30 0.727). code 는 모든 압축기에서 1.000 이다. 코드 블록을 통째로 보존하고 식별자를 force token 으로 넣기 때문으로 보인다.
fact 정답은 설명 글 속 짧은 값 하나인 경우가 많아, 그 줄이 줄어들면 답할 근거가 사라진다. `contexts/` 파일로 확인한 예:

- **c0020** (정답 `"request"`, 질문 "yield 의존성의 scope 기본값"): 원문 187번째 줄 `a "request"-scoped dependency may only depend on "request"-scoped ...` 처럼 따옴표로 쓴 `"request"` 가 r70·r50·r30·rule>llmlingua2 문맥 모두에서 사라졌다 (따옴표가 지워지고 `request scope` 같은 일반 단어만 남음).
  r70 은 맞혔지만 r50·r30·rule>llmlingua2 는 NOT FOUND
- **c0034** (정답 `OAuth2PasswordRequestFormStrict`): 원문 `` `OAuth2PasswordRequestFormStrict` additionally **requires** `grant_type="password"` `` 가 r70 에서 `OAuth2 PasswordRequestFormStrict requires * grant_type = " pas...` 로 바뀌었다.
  질문 식별자 `OAuth2` 를 force token 으로 먼저 치환하면서 더 긴 식별자가 두 조각으로 쪼개졌다. 내용은 남아 있어 r70·r50 은 맞혔지만, 문자열이 달라 `memory_suspect` 로 잡혔고 r30 은 NOT FOUND
  (c0031 `WebSocketDisconnect` → `WebSocket Disconnect` 도 같은 현상. 질문 식별자 `WebSocket` 이 먼저 치환됐다)

### memory_suspect

LLMLingua-2 압축기에서 3~4문항씩(c0004, c0026, c0030, c0031, c0034) 나왔지만, 문맥을 확인하면 대부분 내용은 남고 문자열만 달라진 경우다.

- c0004 정답 "The last one added": 압축 문맥에 `last one added outermost` 가 있다 (`The`, 강조 표시만 빠짐)
- c0030 정답 "The override's own signature": `override ' s signature` 로 `own` 만 빠졌다
- c0031·c0034: 위처럼 식별자가 공백으로 쪼개졌다

`memory_suspect` 는 압축 문맥에 정답 핵심어 문자열이 있는지로 판단한다. 단어를 지우고 공백을 넣는 LLMLingua-2 에서는 실제 기억 의존보다 많이 잡힌다는 점을 감안해 읽어야 한다.

### 의미 손실과 정확도 유지율 (관찰)

LLMLingua-2 압축기는 실제로 압축된 31문항 모두 의미 손실이 5%를 넘는다 (평균 0.121~0.225). 그런데 정확도 유지율은 90% 이상이다.
의미 손실(bge-m3 문맥 임베딩 거리)이 크게 나와도 답에 필요한 정보는 대부분 남았다는 관찰이다. **의미 손실 지표·기준(5%) 조정 여부는 여기서 결론 내지 않는다** (회의 안건).

### 같은 none/rule 도 실행마다 다르다

| 압축기 | baseline_dev_v2 (`20261019-231040`) | 이번 (`20261028-195811`) |
|---|---|---|
| none 정확도 | 1.000 | 1.000 |
| rule 정확도 / 유지율 | 0.986 / 98.57% | 1.000 / 100.0% |

- 같은 설정(reasoning_effort none, temperature 0, seed 42)인데도 기준선에서 rule 의 c0015 가 0.50 이었고 이번에는 1.00 이다.
  c0015 fact 1 은 기준선 재현성 확인에서도 none 끼리 O/X 가 갈린 경계 사례다. 이번에는 rule>llmlingua2 의 c0015(원문 대체라 rule 결과와 같은 문맥)가 0.50 으로 떨어졌다
- 따라서 한 번의 실행에서 생긴 1문항 차이(유지율 약 1.4%p)는 반복 실행 변동 범위 안이다. r30·rule>llmlingua2 의 유지율 90.00%·90.48% 가 90% 를 넘는지는 한 번의 실행으로 판단하기 어렵다

## 후속 과제

1. **여러 문서 문항 fallback 수정**: 원인은 `## Document:` 의 `##` 가 BERT `convert_tokens_to_string` 에서 지워지는 것이다. 수정 방향(추정):
   문서 경계 줄을 코드 블록처럼 고유 마커(예: `__LLMLINGUA_DOC_0000__`)로 가렸다가 복원하거나, 문맥을 문서별로 나눠 문서마다 따로 압축하고 머리 줄은 원문으로 다시 붙인다.
   같은 이유로 질문 식별자가 더 긴 식별자의 앞부분과 겹칠 때(`OAuth2` / `OAuth2PasswordRequestFormStrict`) 쪼개지지 않게 긴 식별자를 먼저 보호하는 것도 함께 본다
2. **테스트셋 측정**: dev 는 none·rule 정확도가 1.000 으로 천장에 붙어 있다. fallback 을 고친 뒤 test split 으로 측정한다
3. **반복 측정**: r30·rule>llmlingua2 의 유지율이 90% 경계라, 같은 설정을 2~3회 반복해 평균과 변동을 본다. c0003 같은 judge 출력 한도 초과도 반복 시 다시 확인한다

## 실행 환경

- git commit: `3ad88f4` (summary.json git_head)
- 평가셋: `data/evalsets/claude-v1/qa_dev.json` sha256 `2ee1f1a7e1abf8a384336763efc8d251a86f8079988692a7e2f0e6fe70c2966e` (git 에 저장된 LF 기준)
- usage: 모든 호출이 서버 보고값 (`*_usage_estimated` 0)
- 실행 머신: Windows 11 Pro 10.0.26200, LLMLingua-2 는 CPU

## API 사용 토큰 (서버 보고값)

워밍업 호출은 빼고 trial 기록 합계다. 답변 모델과 채점 모델은 토크나이저가 달라 서로 더하지 않는다.

| 압축기 | 답변 입력 | 답변 출력 | 채점 입력 | 채점 출력 (생각 토큰 포함) |
|---|---|---|---|---|
| none | 77,273 | 1,297 | 18,435 | 7,657 |
| rule | 61,899 | 1,369 | 18,690 | 6,446 |
| llmlingua2_r70 | 66,380 | 1,308 | 18,478 | 8,030 |
| llmlingua2_r50 | 57,079 | 1,296 | 18,110 | 12,063 |
| llmlingua2_r30 | 47,688 | 1,226 | 17,603 | 12,509 |
| rule>llmlingua2 | 46,546 | 1,305 | 18,347 | 7,164 |
| **합계** | **356,865** | **7,801** | **109,663** | **53,869** |

- 호출 수: 답변 210회 (+ 워밍업 1), 채점 key_facts 343회 (NOT FOUND 로 5문항 생략)

## 부록: 시험 실행

- `20261028-195513` (2문항, none·llmlingua2_r50): 연결 확인용이라 본문 집계에서 뺐다
