# dev baseline v1 (none vs rule)

claude-v1 평가셋 dev 35문항에 대해 압축 없음(none)과 규칙 기반 압축(rule)을 비교한 기준선.
판정은 `judge_compare_v2.md` 에서 확정한 qwen2.5:7b per_fact.

- 이 문서의 rule 은 머리말을 통째로 지우던 버전이다. 이후 rule 기본값은 머리말의 title·description·tags 를 남기며,
  이 문서의 rule 과 같은 동작은 `rule_fm_all` 로 남아 있다
- run: `20261013-103450` (none, rule), 재현성 확인용 `20261013-140130` (none 한 번 더). `results/` 는 커밋하지 않음
- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split dev --compressors none,rule --semantic`
- 답변: qwen2.5:7b, temperature 0, seed 42, num_ctx 16384, answer_prompt v1, 답변 최대 512 토큰
- 판정: qwen2.5:7b, per_fact, fact_judge_v2. 답변이 NOT FOUND 뿐이면 judge 없이 0 (`judge_skipped="not_found"`)

## 결과

| 지표 | none | rule |
|---|---|---|
| 평균 입력 토큰 | 2328 | 1713 |
| 입력 토큰 절감률 | 0.0% | 26.4% |
| 순 입력 토큰 절감률 | 0.0% | 26.4% |
| 의미 유사도 | 1.000 | 0.947 |
| 핵심 개체 보존율 | 1.000 | 1.000 |
| 의미 손실 | 0.000 | 0.053 |
| 답변 정확도 | 0.962 | 0.929 |
| 정확도 유지율 | - | 96.5% |
| NOT FOUND 비율 | 2.9% (1/35) | 2.9% (1/35) |
| 정확도 fact (n=11) | 1.000 | 1.000 |
| 정확도 code (n=12) | 1.000 | 1.000 |
| 정확도 procedure (n=8) | 1.000 | 0.812 |
| 정확도 multi (n=4) | 0.667 | 0.750 |
| 정확도 type 균등 | 0.917 | 0.891 |
| judge 호출 / NOT FOUND 로 생략 | 55 / 1 | 55 / 1 |

- 입력 토큰은 채팅 템플릿을 포함한 전체 messages 기준 (Qwen 토크나이저). 절감률은 문항별 비율의 평균이 아니라 전체 합의 비율
- 정확도 유지율 = rule 평균 정확도 / none 평균 정확도 (문항별 비율의 평균 아님). none 이 0 인 문항도 포함
- rule 은 LLM 을 쓰지 않으므로 순 입력 토큰 절감률 = 입력 토큰 절감률
- NOT FOUND: none 은 c0148, rule 은 c0039

## rule 에서 정확도가 none 보다 떨어진 문항

| qid | type | none → rule | 원인 |
|---|---|---|---|
| c0029 | procedure | 1.00 → 0.50 | 답변이 코드 없이 단계만 요약해 StaticPool·테이블 생성과 overrides clear() 를 빠뜨림. 핵심 개체는 모두 남아 있어(보존율 1.0) 문맥 손실보다 답변 생성 쪽 변동 |
| c0039 | multi | 0.67 → 0.00 | rule 답변이 NOT FOUND. 핵심 개체·근거 줄은 남아 있음 (none 답변도 JWT 쪽을 400 으로 잘못 답한, 모델이 어려워하는 문항) |
| c0145 | procedure | 1.00 → 0.00 | rule 답변에 `with TestClient(app) as client` 와 블록 진입·종료 시 lifespan 시작·정리 주석이 있는데 judge 가 두 fact 모두 불충족. judge 오판(FN) 의심, 사람 확인 필요 |

반대로 c0148(multi)은 none 이 NOT FOUND(0)였고 rule 은 정답(1.0)이었다.

## 재현성 (none 두 번)

같은 설정(temperature 0, seed 42)으로 none 을 한 번 더 돌려(`20261013-140130`) 문항별로 비교했다.

| 비교 | 다른 문항 수 (/35) | 문항 |
|---|---|---|
| 답변 문자열 | 8 | c0003, c0006, c0015, c0029, c0038, c0039, c0040, c0145 |
| key_fact 판정 | 1 | c0039 |
| 문항 정확도 | 1 | c0039 (0.67 → 0.00) |
| 평균 정확도 | | 0.962 → 0.943 |

- temperature 0, seed 고정인데도 긴 답변(procedure 5, multi 3)은 중간부터 표현이 달라졌다 (예: "route function" → "route handler").
  Ollama CPU 실행의 부동소수점 비결정성으로 보인다. 짧은 답(fact·code)은 35문항 중 모두 같았다
- 정확도가 바뀐 문항은 c0039 하나. 두 번째 답변도 JWT 쪽을 400 으로 잘못 답했는데, 단순 버전 400 은 맞게 말했음에도
  judge 가 그 fact 까지 불충족으로 판정했다 (judge FN 의심)
- 따라서 none 과 rule 의 차이 0.033 (0.962 vs 0.929) 은 none 을 반복했을 때의 차이 0.019 와 같은 크기다.
  문항 하나(1/35 = 0.029)가 바뀌면 생기는 차이이므로, rule 의 정확도 하락을 압축 효과로 단정하기 어렵다.
  반복 실행 평균(REPEATS) 이나 문항 수를 늘린 비교가 필요하다

## 실행 환경

- git commit: `4fe2f65` (판정 설정 확정 커밋, summary.json 의 git_head)
- 평가셋: `data/evalsets/claude-v1/qa_dev.json` sha256 `2ee1f1a7e1abf8a384336763efc8d251a86f8079988692a7e2f0e6fe70c2966e`
  (git 에 저장된 LF 기준. Windows 작업본은 CRLF 변환으로 `1b7b4801…` 이 나온다)
- Ollama 0.40.3
- qwen2.5:7b `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
- bge-m3 `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`
- answer 프롬프트 v1 `d12495bd1412`, fact_judge_v2 `7e441ad04bab`
- 실행 머신: Windows 11 Pro 10.0.26200, AMD Ryzen 7 8845HS, RAM 20GB, GPU AMD Radeon 780M (내장).
  Ollama 는 GPU 를 쓰지 않고 CPU 로 실행 (`/api/ps` size_vram 0)
- 지연 시간은 비교하지 않는다: CPU 실행이라 느리고, c0038 rule 한 건은 TTFT 가 5750초로 실행 중 멈춤(절전 등)이 섞였다
