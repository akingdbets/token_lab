# 키 필요한 확인 작업 (멀티턴 기반 1단계)

API 키가 없는 노트북에서 구현과 오프라인 테스트까지만 했다. 아래는 키가 있는 노트북에서 돌릴 확인 작업이다.
끝나면 결과를 이 문서에 적고, `src/llm.py` 의 `USAGE_FIELD_CANDIDATES` 주석을 확인된 이름으로 고친다.

## 0. 준비

프로젝트 최상위 `.env` (git 제외) 에 답변·채점 접속 정보를 넣는다.

```
ANSWER_BACKEND=openai
ANSWER_BASE_URL=https://api.openai.com
ANSWER_API_KEY=...
ANSWER_MODEL=gpt-6.1-sol
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

| 항목 | gpt-6.1-sol (chat completions) | deepseek-flash |
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
