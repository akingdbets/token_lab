# dev baseline v2 (상용 API: gpt-6-luna 답변 · deepseek-flash 채점)

> **Qwen 로컬 결과(v1, `baseline_dev_v1.md`)와 직접 비교 불가.** 답변 모델, 채점 모델, 토크나이저(o200k_base)가 모두 바뀌어
> 토큰 단위와 정확도 기준이 다르다.
>
> **정확도는 잠정치.** deepseek-flash 채점은 아직 사람 라벨로 검증하지 않았다 (`judge_check_v3.csv` 라벨링 후 확정).
> 토큰·의미 손실 지표는 채점과 무관하므로 확정값이다.

claude-v1 평가셋 dev 35문항에 대해 압축 없음(none), 규칙 기반 압축(rule), 머리말 전체 삭제 규칙(rule_fm_all)을 비교한 기준선.

- rule: 현재 기본값. 머리말 중 title·description·tags 를 남긴다
- rule_fm_all: 머리말을 통째로 지운다 (v1 문서의 rule 과 같은 동작)
- run: `20261019-203350` (none, rule, rule_fm_all), 재현성 확인용 none 한 번 더: `20261019-205759` (29문항) + `20261019-213343` (6문항).
  재현성 run 은 30번째 문항에서 네트워크 오류(api.openai.com DNS 조회 실패)로 중단돼, 남은 6문항(`--ids`)을 따로 돌려 합쳤다. `results/` 는 커밋하지 않음
- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split dev --compressors none,rule,rule_fm_all --semantic`
- 답변: gpt-6-luna, answer_prompt v1, 답변 최대 512 토큰 (`max_completion_tokens`). **temperature 는 서버가 0 을 거부해 보내지 않음 (서버 기본값 1)**, seed 42
- 판정: deepseek-flash, per_fact, fact_judge_v2, temperature 0, seed 42, 출력 최대 4096 토큰 (생각 토큰 포함). 답변이 NOT FOUND 뿐이면 judge 없이 0

## 결과

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

## 지연 시간 (초)

API 호출이라 v1(로컬 CPU)과 달리 비교할 수 있다. 같은 문항을 압축기 순서대로 바로 이어 부른 값이다.

| 압축기 | TTFT 평균 | TTFT 중앙값 | 전체 평균 | 전체 중앙값 | 평균 출력 토큰 |
|---|---|---|---|---|---|
| none | 2.22 | 1.94 | 2.51 | 2.01 | 59.0 |
| rule | 2.16 | 2.04 | 2.44 | 2.15 | 56.9 |
| rule_fm_all | 1.98 | 1.84 | 2.22 | 1.95 | 56.0 |

- 입력이 20~24% 줄어도 지연 시간 차이는 0.1~0.3초로, 네트워크·서버 변동과 구분하기 어렵다

## none 보다 정확도가 떨어진 문항

| qid | type | none → 압축 | 원인 |
|---|---|---|---|
| c0015 | multi | 1.00 → 0.50 (rule_fm_all) | fact 1 "JWT 버전은 create_access_token 으로 만든 서명된 JWT 를 돌려준다" 불충족. 세 답변 모두 `create_access_token` 을 언급하지 않고 "signed, expiring JWT" 라고만 했는데, judge 가 none·rule 은 O, rule_fm_all 은 X 로 갈렸다. rule_fm_all 답변은 rule 답변과 거의 같다(`token_type` 한 구절만 더 있음). 압축 손실이 아니라 경계에 있는 fact 의 judge 판정 흔들림으로 보인다 (재현성 run 에서도 none 끼리 같은 fact 가 O → X 로 바뀜) |

rule 은 정확도가 떨어진 문항이 없다.

## 재현성 (none 두 번)

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

## 실행 환경

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

## API 사용 토큰 (서버 보고값)

워밍업 호출(run 마다 1회)과 연결 확인 호출은 빼고 trial 기록 합계다. 답변 모델과 채점 모델은 토크나이저가 달라 서로 더하지 않는다.

| run | 답변 입력 | 답변 출력 | 채점 입력 | 채점 출력 (생각 토큰 포함) |
|---|---|---|---|---|
| 20261019-203350 none | 77,273 | 2,066 | 18,677 | 8,816 |
| 20261019-203350 rule | 61,899 | 1,993 | 18,389 | 6,748 |
| 20261019-203350 rule_fm_all | 58,697 | 1,961 | 18,396 | 5,753 |
| 재현성 none (두 run 합) | 77,273 | 2,104 | 18,757 | 5,020 |
| **합계** | **275,142** | **8,124** | **74,219** | **26,337** |

- 호출 수: 답변 140회 (+ 워밍업 3), 채점 280회 (key_facts 232, O/X 48)

## 다음에 할 일

1. 사람 라벨링: `docs/results/judge_check_v3.csv` (none 답변 key_fact 58행 + 정확도가 바뀐 c0015 rule_fm_all 2행, 담당 A/B/C/D 각 15행).
   judge 판정은 `docs/results/judge_check_v3_judged.csv` 에 따로 있다 (라벨링 중에는 열지 않는다)
2. 라벨이 채워지면 `python src/judge_agreement.py docs/results/judge_check_v3.csv --judged docs/results/judge_check_v3_judged.csv` 로
   일치율·FP·FN·kappa 를 내고 qwen2.5:7b v2 (0.914, kappa 0.617) 와 비교. 통과하면 이 문서의 정확도를 확정
3. 절감률 목표(50%)까지 rule 만으로는 거리가 멀다 (20~24%). LLMLingua-2 측정이 다음 순서
