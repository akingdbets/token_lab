# 키 필요한 확인 작업 (멀티턴 1·2·3단계)

먼저 "실행 전 점검 목록" 과 "파일럿 순서" 를 본다. 그 아래 절들은 단계별 세부 내용이다.

## 실행 전 점검 목록 (이 순서대로)

1. 패키지 설치. llmlingua 가 없으면 `per_message(llmlingua2)` 등 llmlingua 계열 압축기는 시작 시점에 에러로 멈춘다 (원문으로 대체하지 않음).

```powershell
pip install llmlingua==0.2.2 tiktoken
```

2. `.env` 의 토크나이저 확인. replay.py 는 시작할 때 TOKENIZER 가 답변 모델과 맞는지 확인하고, gpt-6-luna 인데 `tiktoken:o200k_base` 가 아니거나 tiktoken 이 없으면 멈춘다 (근사로 돌릴 때만 `--allow-approx-tokenizer`, summary 에 표시됨).

```powershell
Select-String -Path .env -Pattern "^TOKENIZER="
```

   `TOKENIZER=tiktoken:o200k_base` 가 나와야 한다.

3. 캐시·추론 토큰 필드 이름 확정 (아래 1절). 결과로 `src/llm.py` 의 `USAGE_FIELD_CANDIDATES` 주석을 고친다.

```powershell
python src/llm.py --cache-probe
```

4. 그다음 아래 "파일럿 순서" 의 (1)~(4) 를 차례로 돈다. 답변 지시문은 v2 (기본값) 다.

## 파일럿 순서 (2026-11-22 갱신)

모든 단계에서 공통 인자는 같다 (`--model gpt-6-luna --reasoning-effort server_default --max-completion-tokens 4096 --samples 3`).
응답 캐시를 같은 곳(`results/cache/responses.sqlite`)에 쓰므로 뒤 단계의 none·기준 궤적은 앞 단계 응답을 재사용한다 (같은 요청이면 0원).
예상 비용은 이 노트북의 `--estimate-only` 값이다 (Qwen 토크나이저 근사, 답변 300 + 추론 1,000, 요약 300 + 추론 1,000 토큰 가정, 요약 조건 none 은 추론 0).

| 단계 | 내용 | 예상 실제 지출 |
|---|---|---|
| (1) | `--cache-probe` (필드 이름 확정) | < $0.01 |
| (2) | 기준 궤적 + none / window(2) / window_budget / query_select / per_message(rule) / per_message(llmlingua2), 예산 2000·4000·8000 | 답변 $0.58~0.83 + 채점 $0.28 ≈ **$0.9~1.1** (llmlingua2 몫 약 $0.06~0.09 + 채점 $0.03 포함, 추정치) |
| (3) | 요약형 2종 × 요약 추론 2조건 (server_default, none), 예산 2000·4000·8000 | 답변 $0.67~0.95 + 요약 $0.20 + 채점 $0.33 ≈ **$1.2~1.5** |
| (4) | `--sequential-chains` 로 none, frozen_summary(4000) 각 시나리오 1개 (mt01_security) 캐시 검증 | 답변 $0.016~0.02 + 요약 $0.002 ≈ **$0.03** (채점 없음) |

답변 금액 범위는 프롬프트 캐시 적중 0% (상한) ~ 접두부 캐시 반영 값이다.

### (1) 캐시 필드 확정

```powershell
python src/llm.py --cache-probe
```

### (2) 기준 궤적 + 상태 없는 압축기

```powershell
python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 --model gpt-6-luna --compressors "none,window(2),window_budget,query_select,per_message(rule),per_message(llmlingua2)" --history-budget 2000,4000,8000 --samples 3 --reasoning-effort server_default --max-completion-tokens 4096 --concurrency 5
```

- `per_message(llmlingua2)` 는 llmlingua 가 있어야 한다 (점검 목록 1). 없으면 시작 시점에 멈춘다. 이 노트북에는 llmlingua 가 없어 아래 추정 표에 per_message(llmlingua2) 가 없다. 실행 전에 같은 명령에 `--estimate-only` 를 붙여 llmlingua2 의 입력 절감·sim 비용을 먼저 확인한다.

- 끝나면 `summary.json` 의 `reference_health`, `answer_health` (finish_length·empty_response·reasoning_ran) 를 보고 `--max-completion-tokens` 를 정한다. 바꾸면 기준 궤적이 새로 만들어진다.

### (3) 요약형 2종 × 요약 추론 2조건

```powershell
python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 --model gpt-6-luna --compressors "none,rolling_summary,frozen_summary" --history-budget 2000,4000,8000 --samples 3 --reasoning-effort server_default --max-completion-tokens 4096 --summary-model gpt-6-luna --summary-reasoning-effort server_default,none --summary-max-tokens 4096 --concurrency 5
```

- 압축기 이름은 `rolling_summary(4000)[sre=none]` 처럼 펼쳐진다. none 은 (2) 와 같은 요청이라 응답 캐시에서 읽는다.
- `summary_failure` (요약 실패율) 가 0 이 아니면 `--summary-max-tokens` 를 올린다. 실패 체인은 `--resume <run_id>` 로 다시 시도된다.

### (4) 캐시 검증 (순차 체인, 응답 캐시 끔)

```powershell
python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 --model gpt-6-luna --compressors none --history-budget 4000 --samples 1 --reasoning-effort server_default --max-completion-tokens 4096 --summary-model gpt-6-luna --summary-reasoning-effort server_default --summary-max-tokens 4096 --sequential-chains "none,frozen_summary(4000)" --chain-scenarios mt01_security --chain-samples 0
```

- 턴 순서대로 한 번에 하나씩, 응답 캐시 없이 보낸다 (답변 채점 없음). `sequential_summary.json` 에 턴별 `sim_cached_tokens` (prefix_shared_tokens 기반) 와 서버 `cached_tokens` 가 나란히 있다.
- 두 값이 크게 다르면 비용 주 지표(시뮬레이션 캐시 비용)의 가정을 다시 본다. 서버 캐시는 보존 시간·라우팅 영향을 받으므로 한 체인 결과로 일반화하지 않는다.
- 기준 궤적은 (2) 에서 만든 것을 그대로 쓴다 (같은 설정 해시).

### 비용 지표 (중요)

- replay 는 턴을 병렬·순서 무관하게 보내므로, 실행 중 서버가 보고한 `cached_tokens` 는 실제 대화의 캐시 동작이 아니다.
- 두 비용 열의 해석: **sim** 은 대화 간격이 캐시 보존 시간(30분) 안이라는 가정(직전 턴 접두부가 캐시에 남아 있음), **nocache (캐시 0%)** 는 캐시가 만료된 경우의 경계값이다. 실제 비용은 대화 간격 분포에 따라 두 값 사이에 놓인다 (`summary.notes` 에도 적힘).
- 그래서 `summary.json` / `budget_table` 의 비용 절감률 주 지표는 **`cost_reduction_pct_sim`** (같은 압축기로 실제 대화했을 때 직전 턴 요청과 겹치는 접두부 = `prefix_shared_tokens` 를 캐시 읽기로 본 시뮬레이션 비용) 이고, `_sim_write` 는 미스 부분을 캐시 쓰기 단가로 계산한 변형이다. `_nocache` 는 상한, `_measured` (실측 cached_tokens) 는 참고용이다.
- overflow 턴(직전 턴 원문만으로 예산 초과)을 뺀 집계는 `excluding_overflow` 와 budget_table 의 `*_excluding_overflow` 에 있다.

### 예상 비용 상세 (시뮬레이션 캐시 기준, 2026-11-22)

**압축기 비교: 실험상 비용 (호출당) = 답변 + 요약, none 대비 절감률.** sim = 직전 턴 접두부 캐시 (주 지표), 캐시 0% = 상한.
none: 캐시 0% $0.0980, sim $0.0640, 직전 턴 접두부 공유율 76.0%.

| 압축기 | 입력 절감 | overflow | 접두부 공유 | 요약 비용 | 절감 (캐시 0%) | **절감 (sim)** | 절감 (sim_write) | 요약 호출 | 재압축 |
|---|---|---|---|---|---|---|---|---|---|
| window(2) | 54.8% | 0.0% | 20.5% | – | 25.4% | −8.5% | −11.6% | – | – |
| window_budget(2000) | 65.0% | 18.5% | 24.6% | – | 30.1% | −3.6% | −5.8% | – | – |
| window_budget(4000) | 38.0% | 0.0% | 44.7% | – | 17.6% | −8.3% | −11.0% | – | – |
| window_budget(8000) | 6.2% | 0.0% | 68.9% | – | 2.9% | −4.4% | −5.6% | – | – |
| query_select(2000) | 55.9% | 18.5% | 12.8% | – | 25.9% | −10.9% | −14.6% | – | – |
| query_select(4000) | 39.8% | 0.0% | 11.8% | – | 18.4% | −22.3% | −28.4% | – | – |
| query_select(8000) | 31.8% | 0.0% | 11.7% | – | 14.7% | −28.0% | −35.4% | – | – |
| per_message(rule) | 14.8% | – | 59.3% | – | 6.9% | −4.4% | −5.8% | – | – |
| per_message(llmlingua2) | (키 있는 노트북에서 `--estimate-only`) | | | | | | | | |
| rolling_summary(2000)[sre=server_default] | 64.1% | 18.5% | 26.2% | $0.0379 | −9.1% | −63.9% | −64.5% | 45 | – |
| rolling_summary(2000)[sre=none] | 64.1% | 18.5% | 26.2% | $0.0154 | 13.9% | −28.7% | −30.4% | 45 | – |
| rolling_summary(4000)[sre=server_default] | 47.1% | 0.0% | 53.5% | $0.0184 | 3.0% | −29.6% | −29.8% | 18 | – |
| rolling_summary(4000)[sre=none] | 47.1% | 0.0% | 53.5% | $0.0094 | 12.2% | −15.5% | −16.2% | 18 | – |
| rolling_summary(8000)[sre=server_default] | 16.1% | 0.0% | 69.0% | $0.0082 | −0.9% | −12.8% | −12.8% | 6 | – |
| rolling_summary(8000)[sre=none] | 16.1% | 0.0% | 69.0% | $0.0052 | 2.2% | −8.1% | −8.2% | 6 | – |
| frozen_summary(2000)[sre=server_default] | 61.6% | 18.5% | 31.8% | $0.0504 | −22.9% | −82.9% | −82.9% | 63 | 18 |
| frozen_summary(2000)[sre=none] | 61.6% | 18.5% | 31.8% | $0.0189 | 9.3% | −33.7% | −35.0% | 63 | 18 |
| frozen_summary(4000)[sre=server_default] | 45.5% | 0.0% | 56.3% | $0.0181 | 2.6% | −28.9% | −29.1% | 18 | 0 |
| frozen_summary(4000)[sre=none] | 45.5% | 0.0% | 56.3% | $0.0091 | 11.8% | −14.9% | −15.5% | 18 | 0 |
| frozen_summary(8000)[sre=server_default] | 16.1% | 0.0% | 69.0% | $0.0082 | −0.9% | −12.8% | −12.8% | 6 | 0 |
| frozen_summary(8000)[sre=none] | 16.1% | 0.0% | 69.0% | $0.0052 | 2.2% | −8.1% | −8.2% | 6 | 0 |

- none: 캐시 0% $0.0980, sim $0.0640, sim_write $0.0658, 직전 턴 접두부 공유율 76.0%.
- per_message(rule) 의 접두부 공유율(59.3%)이 높은 이유: 과거 문서를 매번 같은 규칙으로 압축해 앞쪽 턴이 글자 그대로 유지된다. 다만 직전 턴 메시지는 그 턴에는 원문(현재 턴), 다음 턴에는 압축본(과거)이라 그 지점에서 접두부가 끊긴다.
- **요약 추론 조건별 요약 비용**: server_default $0.141 (156회, 추론 1,000 가정), none $0.063 (156회, 추론 0).
- **frozen_summary 재압축**: 2000 에서 체인당 2.0회 (턴 3~6), 4000·8000 에서 0회. 2000 은 rolling 과 비슷해진다.
- **시뮬레이션 캐시 기준으로는 어떤 압축기도 none 보다 싸지 않다.** none 은 기록이 앞에서부터 그대로 자라 직전 턴 접두부 공유율이 76% 이고, 캐시 읽기 단가가 입력의 1/10 이다. 압축기는 입력을 줄여도 접두부가 깨져 캐시 할인을 잃는다. 출력(답변 + 추론 1,300 토큰)이 비용의 대부분이라 입력 절감 효과가 작다. 실제 추론 토큰과 (4) 의 캐시 검증 결과가 이 결론의 핵심 가정이다.
- overflow 18.5% (2000): 직전 턴 원문만으로 예산을 넘는 턴이다. `excluding_overflow` 집계로 따로 본다.

## 0. 준비

프로젝트 최상위 `.env` (git 제외) 에 답변·채점 접속 정보를 넣는다.

```
ANSWER_BACKEND=openai
ANSWER_BASE_URL=https://api.openai.com
ANSWER_API_KEY=...
ANSWER_MODEL=gpt-6-luna            # 멀티턴 답변기 (논문과 같은 모델). 1단계 probe 는 gpt-6.1-sol 로도 한 번 돌린다
JUDGE_BACKEND=openai
JUDGE_BASE_URL=https://api.deepseek.com
JUDGE_API_KEY=...
JUDGE_MODEL=deepseek-flash
TOKENIZER=tiktoken:<답변 모델의 인코딩>
```

- `ANSWER_REASONING_EFFORT` 는 아직 정하지 않았다. config 기본값은 `none`(추론 OFF)이고, 논문 run 도 `none` 이었다.
  추론 ON(서버 기본값)으로 확인하려면 `.env` 에 `ANSWER_REASONING_EFFORT=` 처럼 **빈 값**을 넣는다.
  값을 적지 않으면 config 기본값 `none` 이 쓰인다. 두 설정을 모두 보려면 probe 를 두 번 돌린다.

```powershell
python -m unittest discover -s tests
```

## 1. 캐시·추론 토큰 필드 이름 확정 (`--cache-probe`)

같은 약 2,000 토큰 프롬프트를 연속 두 번 보내고, 호출마다 `cached_tokens / cache_write_tokens / reasoning_tokens` 와 `raw_usage` 원본을 출력한다. 비용은 모델당 몇 센트 이하다.

```powershell
python src/llm.py --cache-probe
```

```powershell
python src/llm.py --cache-probe answer
```

```powershell
python src/llm.py --cache-probe judge
```

확인할 것

| 항목 | gpt-6-luna / gpt-6.1-sol (chat completions) | deepseek-flash |
|---|---|---|
| 캐시 읽기 | 호출 2 의 `prompt_tokens_details.cached_tokens` > 0 인지 | 호출 2 의 `prompt_cache_hit_tokens` > 0 인지 |
| 캐시 쓰기 | **미확인**. 호출 1 의 raw_usage 에 쓰기 토큰 필드가 있는지, 이름은 무엇인지 | 과금 항목 없음 (`prompt_cache_miss_tokens` 는 미스) |
| 추론 | `completion_tokens_details.reasoning_tokens` | `completion_tokens_details.reasoning_tokens`, 추론 원문 `reasoning_content` |

- 캐시 쓰기 후보(`prompt_tokens_details.cache_write_tokens`, `prompt_tokens_details.cache_creation_tokens`)는 Responses API 문서의 `input_tokens_details.cache_write_tokens` 를 보고 만든 **추측**이다. 실제 이름이 다르면 `USAGE_FIELD_CANDIDATES` 를 고친다.
- 쓰기 필드가 아예 없으면 gpt-6.1-sol 비용은 `cost_source="no_cache_write_info"` 가 된다(쓰기 토큰을 일반 입력 단가로 계산해 실제보다 낮을 수 있음). 그대로 둘지 정해야 한다.
- 호출 2 에 캐시 읽기가 0 이면 캐시 반영 지연일 수 있다. 몇 초 뒤 한 번 더 돌려 본다.

## 2. 연결 확인 (새 필드 출력)

```powershell
python src/llm.py
```

```powershell
python src/llm.py judge
```

스트리밍 경로에서도 `raw_usage` 가 채워지는지 본다 (OpenAI 는 `stream_options.include_usage` 의 마지막 청크).

## 3. 싱글턴 짧은 실행 (형식 회귀 확인)

```powershell
python src/experiment.py --limit 3 --compressors none,rule
```

확인할 것

- 이전 run 과 같은 형식으로 `results/runs/<run_id>/trials.jsonl`, `summary.json`, `contexts/` 가 생긴다.
- `trials.jsonl` 에 새 필드 `answer_cached_tokens`, `answer_cache_write_tokens`, `answer_reasoning_tokens`, `answer_raw_usage` 가 있다.
- `summary.json` 조건별 `usage` 에 `answer_cached_tokens` 등 합계, 새 `answer_health`(reasoning_ran / finish_length / empty_response) 가 있다.
- 기존 필드와 지표 값의 의미는 그대로다 (새 키만 늘었다).

## 결과 기록

| 날짜 | 명령 | 결과 요약 |
|---|---|---|
| | | |

# 멀티턴 2단계 (replay)

## 4. 파일럿 replay 실행

`--reasoning-effort`, `--max-completion-tokens` 는 필수다 (config 기본값을 쓰지 않는다). temperature 는 기본값이 `server_default` (보내지 않음) 다.

먼저 비용만 확인한다 (API 호출 없음).

```powershell
python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 --model gpt-6-luna --compressors "none,window(2),per_message(rule),per_message(llmlingua2)" --samples 3 --reasoning-effort server_default --max-completion-tokens 4096 --judge-model deepseek-flash --estimate-only
```

실행한다.

```powershell
python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 --model gpt-6-luna --compressors "none,window(2),per_message(rule),per_message(llmlingua2)" --samples 3 --reasoning-effort server_default --max-completion-tokens 4096 --reference-sample 0 --concurrency 5
```

끊기면 출력 끝에 나온 run_id 로 이어서 돌린다 (끝난 trial 은 건너뛰고, 이미 받은 응답은 응답 캐시에서 읽는다).

```powershell
python src/multiturn/replay.py --scenarios data/evalsets/multiturn-v1 --model gpt-6-luna --compressors "none,window(2),per_message(rule),per_message(llmlingua2)" --samples 3 --reasoning-effort server_default --max-completion-tokens 4096 --resume <run_id>
```

- `per_message(llmlingua2)` 등 llmlingua 계열은 `llmlingua` 와 모델 가중치가 있어야 한다. 없으면 replay.py·estimate.py 모두 **시작 시점에 MissingDependencyError 로 멈춘다**. 실행 중 모델 로드·추론이 실패해 싱글턴 압축기가 원문을 돌려주면(`status=fallback_error`) CompressorFallbackError 로 멈춘다 (조용한 대체 금지). 이 노트북에는 llmlingua 가 없어 추정에서 뺐다.
- 추정·`history_tokens_*`·`input_tokens_est` 는 `TOKENIZER` 기준이다. luna 와 맞추려면 `tiktoken` 을 설치하고 `TOKENIZER=tiktoken:o200k_base` 로 둔다 (이 노트북은 tiktoken 이 없어 Qwen 토크나이저로 근사했다). 과금 토큰은 서버 usage 기준이라 영향이 없다.

### `--max-completion-tokens` 권장값: 4096 (answer_health 보고 조정)

- 근거: luna 기본 설정(추론 서버 기본값)은 출력 한도 2048 에서 closed-book 빈 답변 4건이 나왔다 (추론 토큰이 한도를 다 씀, `docs/results/closed_book_luna.md`). 4096 으로 돈 `luna-default-20261103` (test 139문항 × 5조건) 은 잘림·빈 답변 0 이었다 (`docs/results/test_v1_default.md`).
- 멀티턴은 입력이 길어(턴이 갈수록 기록 누적) 추론이 더 길어질 수 있다. **파일럿 뒤 `summary.json` 의 `answer_health` (finish_length, empty_response) 와 `reference_health` 를 보고 조정한다.** 0 이 아니면 8192 로 올려 다시 돈다 (설정이 바뀌므로 기준 궤적도 새로 만들어진다).
- `answer_health.reasoning_ran` 이 0 이면 서버 기본값에서 추론이 돌지 않은 것이다 (제공사가 기본값을 바꿨을 수 있음). 그대로 두지 말고 확인한다.

### 예상 비용 (이 노트북의 `--estimate-only`, 2026-11-22)

가정: 시나리오 3개 / 27턴, sample 3, 답변 300 + 추론 1,000 토큰, judge 호출당 입력 261 / 출력 101 토큰 (test_v1_default 실측 평균), per_fact 채점.
**토크나이저: Qwen/Qwen2.5-7B-Instruct (근사, 기대값 tiktoken:o200k_base).** llmlingua 미설치라 `per_message(llmlingua2)` 제외.

**압축기 비교: 실험상 비용 (호출당).** 응답 캐시 적중과 무관하게 81 trial 전부를 한 번 호출한 값으로 센다 (none 의 reference sample 은 같은 요청인 기준 궤적 호출 값). 절감률은 none 대비.

| 압축기 | trial | 입력 토큰 | 입력 절감 | 기록 절감 | 캐시 0% | 절감 | 접두부 캐시 | 절감 | +쓰기 과금 | 절감 |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 81 | 450,921 | – | – | $0.0977 | – | $0.0594 | – | $0.0601 | – |
| window(2) | 81 | 202,200 | 55.2% | 63.4% | $0.0729 | 25.4% | $0.0591 | 0.6% | $0.0603 | −0.4% |
| per_message(rule) | 81 | 383,688 | 14.9% | 17.3% | $0.0910 | 6.9% | $0.0593 | 0.1% | $0.0601 | −0.1% |

- 프롬프트 캐시를 반영하면 압축기 간 비용 차이가 거의 사라진다. 출력(답변 300 + 추론 1,000 토큰, 호출당 $0.00065)이 비용의 대부분이고, none 은 기록이 앞에서부터 그대로 자라 캐시 적중이 많기 때문이다. **실제 실행에서 추론 토큰·캐시 적중을 확인해야 할 가장 중요한 가정이다.**

**예산 확인: 실제 지출** (실제로 보내는 요청만)

| 항목 | 실제 요청 | 캐시 0% | 접두부 캐시 | 채점 |
|---|---|---|---|---|
| 기준 궤적 | 27 | $0.0326 | $0.0213 | – |
| none | 54 / 81 | $0.0652 | $0.0381 | $0.0275 |
| window(2) | 81 / 81 | $0.0729 | $0.0591 | $0.0275 |
| per_message(rule) | 81 / 81 | $0.0910 | $0.0593 | $0.0275 |
| **합계** | | **$0.26** | **$0.18** | **$0.08** |

- none 의 reference sample 은 기준 궤적과 같은 요청이라 응답 캐시에 적중해 실제 지출이 0원이다 (기준 궤적 호출로 이미 한 번 낸다). 그래서 none 의 실제 요청이 54 다.
- per_message(llmlingua2) 를 넣으면 답변이 대략 압축기 하나 몫 ($0.06~0.09) 더 든다.

## 5. 싱글턴 다리 측정 확인

논문(test_v1, `20261102-205826`)은 gpt-6-luna + 추론 OFF(`none`)·temperature 0·출력 한도 512 다. 멀티턴은 gpt-6-luna + 추론·temperature 서버 기본값이다.
문서(`docs/results/test_v1_default.md`)상 `luna-default-20261103` 이 이미 그 다리 측정이다: 같은 평가셋(`test-v1-freeze` test 139문항), 같은 압축 문맥(test_v1 contexts 재사용), 같은 압축기(none, rule, llmlingua2_r50, llmlingua2_r30, rule>llmlingua2), 같은 채점(deepseek-flash, fact_judge_v2, per_fact), 다른 점은 추론·temperature 서버 기본값과 출력 한도 4096 뿐이다. 그래서 새로 측정하지 않는다.

키 있는 노트북에서 확인만 한다.

```powershell
python -c "import json; d=json.load(open('results/runs/luna-default-20261103/summary.json', encoding='utf-8')); print(json.dumps(d['config'].get('sampling'), indent=1))"
```

- `answer.reasoning_effort` 가 null(보내지 않음), `temperature` 가 null, `max_tokens` 4096 인지 본다. 폴더 이름이 다르면 `results/runs/` 에서 찾는다.
- 만약 다르거나 run 이 없으면 같은 조건을 다시 잰다. **experiment.py 로 하지 않는다**: experiment.py 는 출력 한도가 코드 상수 `ANSWER_MAX_TOKENS = 512` 라 추론을 켜면 답변이 잘린다 (환경변수로 바꿀 수 없음). luna-default 를 만든 `src/rerun_contexts.py` 를 쓴다. 이 스크립트는 temperature·reasoning_effort 를 보내지 않고(서버 기본값), 출력 한도 4096, test_v1 의 저장된 압축 문맥을 그대로 쓴다. 예상 답변 비용은 지난 실측 기준 약 $1.5 (5조건, test 139문항), 채점은 별도.

```powershell
$env:EVAL_DIR = "data/evalsets/claude-v1"; python src/rerun_contexts.py results/runs/20261102-205826 --model gpt-6-luna --compressors "none,rule,llmlingua2_r50"
```

  - `llmlingua2_r50` 은 `llmlingua2`(retain 0.5) 와 같은 설정이다. 논문 조건 전체를 맞추려면 `"none,rule,llmlingua2_r50,llmlingua2_r30,rule>llmlingua2"` 로 돌린다.
  - experiment.py 구조는 바꾸지 않았다. experiment.py 로 추론 서버 기본값을 재려면 `ANSWER_REASONING_EFFORT=` (빈 값) 으로 넘길 수는 있지만 출력 한도 512 때문에 다리 측정으로 쓰지 않는다.

# 멀티턴 3단계 (요약 압축기 2종 + 질문 기반 선택 + 같은 예산 비교)

실행 명령·예상 비용·비용 지표 설명은 맨 앞 "파일럿 순서" 의 (2)~(4) 로 옮겼다 (예산 2000·4000·8000, 요약 추론 2조건, 시뮬레이션 캐시 비용 기준).

- 상태형 압축기는 끝난 턴도 압축을 다시 해 상태를 재구성한다 (요약 호출은 응답 캐시 적중이라 과금 없음).
- 요약 실패 (3번 시도 뒤에도 빈 요약·`finish_reason=length`): 그 체인을 그 턴부터 `summary_failed` 로 표시하고 남은 턴을 건너뛴다. 실패 응답은 캐시에 저장하지 않으므로 `--resume` 하면 다시 시도한다.
- 키가 있으면 `turn_trials.jsonl` 의 `cost_sim` 과 `cost` (실측), `prefix_shared_tokens(_raw)` 와 `cached_tokens` 를 나란히 본다. 실측은 병렬 실행이라 참고용이다.
