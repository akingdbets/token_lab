# C1 정답 사본 검증 — 실행 전 고정 사항 (해석 기준)

C1 가설 문구 (잠정, 결과 뒤 최종 문구를 맞춘다):
> 문서에서만 답하라는 지시(answer_v1) 아래에서 gpt-6-luna 는 정답 사본이 없으면 대부분 답하지 않았고,
> 압축에 강해 보이는 것은 압축 뒤에도 남는 정답 사본 덕분이다.

사본이 남는 경로는 두 가지로 본다.
- ① 제자리 생존: LLMLingua-2 처럼 단어 단위로 지우면 근거 문장의 다른 단어는 지워져도 정답 단어가 제자리에 남는다
- ② 문서 중복: drop_evidence 처럼 줄 단위로 지우면 근거 줄의 정답은 사라지고, 문서 다른 곳의 사본으로 답한다

이 문서는 **API 를 쓰는 run 보다 먼저** 커밋한다. 아래 기준을 결과를 보고 바꾸면, 바꾼 이유와 함께 따로 적는다.

## 조건 (`src/compressors/copies.py`)

| 조건 | 문맥에서 지우는 것 | 보는 것 |
|---|---|---|
| none | 없음 | 기준 |
| drop_evidence | 근거 인용문 줄 | ② 문서 중복 |
| drop_all_copies | 근거 단위 + 정답 사본 단위 전부 (코드 블록은 통째로) | 사본이 없으면 못 맞히는가 (필요조건) |
| keep_code_copy | drop_all_copies 에서 근거가 아닌 코드 사본 하나만 남김 | 코드 사본 하나로 충분한가 |
| keep_prose_copy | 같은 방식으로 코드 밖 사본 하나만 남김 | 산문 사본 하나로 충분한가 |
| keep_answer_in_place | drop_all_copies 에서 정답이 든 근거 단위 하나를 정답 구절로 바꿔 제자리에 남김 | ① 제자리 생존만으로 충분한가 |
| matched_random_drop (_s2, _s3) | 근거·사본이 아닌 단위에서 drop_all_copies 와 같은 토큰 수 | "문맥이 줄어서" 반론 차단 |
| empty | 문서 전체 | 바닥값 (기존 0/35) |

## 문항

- 본 분석: `type ∈ {fact, code}` 이고 원문에서 정답 핵심어가 잡히는 문항 (`copies_dry_run.select_items`). dev 23, test 70
- 정답 유형 (`core_match.answer_kind`, 코드로 고정): 식별자형 dev 8 / test 17, 값형 dev 15 / test 53
  - 식별자형: 한 단어에 `_ @ : { ( [ . -` 가 있거나 낙타 표기·연속 대문자 (DUMMY_HASH, asgi-lifespan, StaticPool)
  - 값형: 여러 단어, 따옴표 리터럴, 숫자·버전, URL·경로·이메일·와일드카드, 나머지 한 단어 (15, "request", http://test, blue)
  - 경계에 있는 것: `fake-super-secret-token`·`item.html`·`database.db` 는 규칙상 식별자형, `{"token": token}` 은 값형
- 제외
  - drop_all_copies 가 지운 토큰이 원문의 **상한 __%** 를 넘는 문항 (dry-run 뒤 확정. 30% 면 dev c0001·c0002·c0017 제외, 50% 면 제외 없음)
  - 조건별 사본 검증 실패(verified=False)나 정의 안 됨(defined=False)인 문항은 그 조건에서만 뺀다 (test c0013: 정답 "4" 가 번호 목록 "4." 과 겹침)
- 조건별 문항 목록: `python src/copies_dry_run.py --split <dev|test> --cap <상한>` → `results/copies_dry_run/<split>.json` 의 `eligible`

## keep_answer_in_place 해석 (세 갈래)

none, drop_all_copies 와 같은 문항에서 정확도를 비교한다. 정답 유형별로 따로 본다.
"none 에 가깝다" = none 과의 차이가 15%p 이내, "drop_all_copies 에 가깝다" = drop_all_copies 와의 차이가 15%p 이내.

1. **두 유형 모두 none 에 가깝다** → 정답 단어 하나만 제자리에 남아도 충분하다. LLMLingua-2 가 압축에 강한 이유는 ① 제자리 생존으로 설명된다
2. **두 유형 모두 drop_all_copies 에 가깝다** → 고립된 정답 단어로는 부족하다. r30 에서 근거 문장의 다른 단어가 지워지고도 맞힌 24건은 남은 주변 단어나 다른 단서 덕분이다. ① 만으로는 설명되지 않는다
3. **식별자형은 none 에 가깝고 값형은 그렇지 않다** (또는 반대) → 충분한지는 정답 유형에 달렸다. 식별자는 이름 자체가 질문과 이어지지만 숫자·리터럴은 주변 문맥이 있어야 무엇의 값인지 안다

두 유형이 위 어디에도 들지 않으면(사이 값) 그대로 보고하고 갈래를 정하지 않는다.
예측 (기록용): 3 (식별자형은 충분, 값형은 부족).
근거: PR #39 에서 r30 이 c0020 의 값형 정답 `request` 를 일곱 위치 모두 지워 NOT FOUND 가 됐고, 정답이 설명 문장에만 남은 trial 이
가장 약했다 (정확도 0.83, NOT FOUND 0.17). 식별자형은 LLMLingua-2 보호 규칙(식별자·코드 블록 강제 보존)으로 남는 경우가 많다.

## 그 밖의 판정 기준

- 중복성 (필요조건): drop_evidence 에서는 맞히고 drop_all_copies 에서는 NOT FOUND 인 문항이 많고, matched_random_drop 정확도가 none 에 가까우면 지지
- 충분조건: keep_code_copy / keep_prose_copy 가 none 에 가까우면 사본 하나로 충분
- keep_prose_copy 를 test 에 넣는 조건: dev 에서 keep_code_copy 와 정확도 차 20%p 이상이고 keep_prose_copy 의 n ≥ 8. 아니면 test 에서 빼고 한계로 적는다
- keep_code_copy 는 dev n 이 4 (상한 30%) 라 dev 결과로는 판단하지 않는다
- 기권(NOT FOUND, `is_not_found`)과 오답은 따로 센다
- 비교는 같은 문항끼리 짝지어 한다 (McNemar 또는 부호검정). dev 는 조건마다 3회 (matched_random_drop 은 run 마다 시드 하나: 1회차 기본, 2회차 _s2, 3회차 _s3. 시드 변동과 run 변동이 섞인다)
- dev 는 파일럿, 확인은 test. test 조건: none, drop_evidence, drop_all_copies, keep_code_copy, keep_answer_in_place, matched_random_drop (keep_prose_copy 는 위 규칙)

## 보조 분석 (API 없음)

- `src/redundancy.py` ([redundancy_analysis.md](redundancy_analysis.md), PR #39): 저장된 run 의 중복도 1 vs 2+ 정확도, trial 상태(a/b/c, A/B/C)
  - drop_evidence (`20261019-231040`, 저장소 밖 run 이라 탐색 결과): 중복도 1 은 0.282, 2+ 는 0.818 (p = 0.004)
  - LLMLingua-2 (#35 3회 반복): 중복도로 구분되지 않음 (모두 p > 0.29). 다만 정확도가 0.92~1.00 이라 천장 근처에서 검정력이 낮다
  - 근거 자리에 정답 단어만 남은 trial 24건 정확도 0.875 → keep_answer_in_place 로 충분성을 직접 잰다
- 중복도는 `copies_dry_run.py` 출력에도 같은 정의(`redundancy.core_positions`)로 넣었다. 개입 실험 결과를 같은 축으로 나눠 볼 수 있다
- **중복도 1 문항은 drop_evidence 와 drop_all_copies 가 거의 같은 조작이다** (근거 밖 사본이 없다). dev 23문항 중 11개, test 70문항 중 40개.
  두 조건의 대비(중복성 검증)는 중복도 2+ 문항(dev 12, test 30)에서 본다. 중복도 1 문항에는 keep_code_copy·keep_prose_copy 가 정의되지 않는다

## 아직 정할 것

- 상한 수치 (30% / 50%)
- dev none: #35 run 재사용(69회 절약)과 같은 배치 재실행 중 무엇으로 할지
- permissive 답변 지시문(answer_v2): dev 1회, 예측은 closed-book 66% 근처 (넓게)
