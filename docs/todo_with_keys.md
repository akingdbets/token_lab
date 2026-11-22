# 키 필요한 확인 작업 (멀티턴 1·2단계)

API 키가 없는 노트북에서 구현과 오프라인 테스트까지만 했다. 아래는 키가 있는 노트북에서 돌릴 확인 작업이다.
끝나면 결과를 이 문서에 적고, `src/llm.py` 의 `USAGE_FIELD_CANDIDATES` 주석을 확인된 이름으로 고친다.

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

- `per_message(llmlingua2)` 는 `llmlingua` 와 모델 가중치가 있어야 한다 (`pip install -r requirements.txt`). 없으면 원문을 그대로 돌려주므로(`fallback_error`) 결과의 `compression_info.info.single_status` 를 꼭 본다. 이 노트북의 추정에서는 그래서 뺐다.
- 추정·`history_tokens_*`·`input_tokens_est` 는 `TOKENIZER` 기준이다. luna 와 맞추려면 `tiktoken` 을 설치하고 `TOKENIZER=tiktoken:o200k_base` 로 둔다 (이 노트북은 tiktoken 이 없어 Qwen 토크나이저로 근사했다). 과금 토큰은 서버 usage 기준이라 영향이 없다.

### `--max-completion-tokens` 권장값: 4096 (answer_health 보고 조정)

- 근거: luna 기본 설정(추론 서버 기본값)은 출력 한도 2048 에서 closed-book 빈 답변 4건이 나왔다 (추론 토큰이 한도를 다 씀, `docs/results/closed_book_luna.md`). 4096 으로 돈 `luna-default-20261103` (test 139문항 × 5조건) 은 잘림·빈 답변 0 이었다 (`docs/results/test_v1_default.md`).
- 멀티턴은 입력이 길어(턴이 갈수록 기록 누적) 추론이 더 길어질 수 있다. **파일럿 뒤 `summary.json` 의 `answer_health` (finish_length, empty_response) 와 `reference_health` 를 보고 조정한다.** 0 이 아니면 8192 로 올려 다시 돈다 (설정이 바뀌므로 기준 궤적도 새로 만들어진다).
- `answer_health.reasoning_ran` 이 0 이면 서버 기본값에서 추론이 돌지 않은 것이다 (제공사가 기본값을 바꿨을 수 있음). 그대로 두지 말고 확인한다.

### 예상 비용 (이 노트북의 `--estimate-only`, 2026-11-22)

가정: 시나리오 3개 / 27턴, sample 3, 답변 300 + 추론 1,000 토큰, judge 호출당 입력 261 / 출력 101 토큰 (test_v1_default 실측 평균), per_fact 채점, 토크나이저 Qwen (근사).

| 압축기 | 요청 (실제) | 입력 토큰 | 입력 절감 | 기록 절감 | 캐시 0% | 접두부 캐시 | 채점 |
|---|---|---|---|---|---|---|---|
| none | 81 (54) | 450,921 | 0.0% | 0.0% | $0.065 | $0.038 | $0.028 |
| window(2) | 81 (81) | 202,200 | 55.2% | 63.4% | $0.073 | $0.059 | $0.028 |
| per_message(rule) | 81 (81) | 383,688 | 14.9% | 17.3% | $0.091 | $0.059 | $0.028 |

- 기준 궤적 27 요청: $0.033 (캐시 0%) / $0.021 (접두부 캐시)
- 합계 (실제 지출, 기준 궤적 포함, llmlingua2 제외): 답변 **$0.26 (캐시 0% 상한) / $0.18 (접두부 캐시)**, 채점 **$0.08**
- per_message(llmlingua2) 를 넣으면 답변이 대략 압축기 하나 몫 ($0.06~0.09) 더 든다.
- none 의 "실제" 요청이 54 인 것은 reference sample 이 기준 궤적과 같은 요청이라 응답 캐시에 적중하기 때문이다.

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
