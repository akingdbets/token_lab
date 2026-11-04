# 질문 관련 문장 사후 복원: repair_v1

구현일: 2026-11-04. 기존 LLMLingua-2 전체 문서 압축 후 질문 관련 문장의 보존을 검사하고, 임계값 미만인 문장을 원래 위치에 복원하는 후보 방법이다. 정답, key_facts, evidence.quote는 사용하지 않는다. surface_v1의 추가 보호는 적용하지 않는다. 기존 LLMLingua의 코드·문서 경계·식별자 보호는 사용한다.

## 처리 과정

1. 원문을 줄/문장 경계로 분리한다. 코드 블록·헤더·`---`로 구분한 frontmatter는 선정 대상에서 제외한다. 백틱 안의 점과 소수·버전 내부의 점은 문장 경계로 취급하지 않는다. 일반 약어/복잡한 Markdown을 완벽하게 파싱하지는 않는다.
2. 질문과 각 문장의 단어 빈도 벡터 코사인으로 순위를 매긴다. 일부 영어 불용어를 제외하고 양수 점수의 상위 3문장을 선정한다. 이는 의미 검색이 아니라 단어 일치 기반 관련성이다.
3. 기존 LLMLingua로 전체 문서를 한 번 압축한다.
4. 원문과 압축문의 단어/기호를 SequenceMatcher로 정렬하고, 선정한 원문 문장에 대응하는 압축 구간을 얻는다. 압축 토큰 중 정렬된 비율이 90% 미만이면 복원을 건너뛴다. 반복 표현이 있으면 높은 정렬률도 정확한 대응을 보장하지 않는다.
5. 선정 문장과 그 압축 구간을 기존 LLM(role='embed')로 임베딩해 코사인 유사도를 계산한다. 빈 압축 구간은 복원 후보로 취급한다. 유사도 0.85 미만이면 원문 문장 전체로 교체한다. 중복되는 복원 구간은 건너뛴다.
6. 기존 압축문보다 추가된 토큰이 누적 256개 이내인 경우에만 복원한다. 높은 질문 관련성 순서로 처리하고 복원은 한 번만 수행한다. 정답 여부에 따른 재시도는 없다.
7. 반환된 최종 문서를 기존 experiment.py가 답변 모델에 전달한다. 압축기 자체는 답변·judge 모델을 호출하지 않는다.

3문장/0.85/256토큰은 효과가 검증되지 않은 초기값이다. Python 생성자의 top_k, threshold, max_added_tokens로 조절한다. 변경 값은 config에 기록된다. 이 버전은 보호 문자열을 추가 등록하지 않아 새 복원 문장 수에 마커 100개 한도가 적용되지 않는다. 기반 압축기 자체의 기존 보호 한도는 남는다.

## 실행

```bash
# 모델 호출 없는 구현 테스트
.venv/bin/python -m unittest discover -s tests -p test_sentence_repair.py

# 향후 실제 평가 명령 (답변/채점 API 호출 발생)
EVAL_DIR=data/evalsets/claude-v1 TOKENIZER=tiktoken:o200k_base \
  .venv/bin/python src/experiment.py --split test \
  --compressors 'none,llmlingua2_r50,llmlingua2_r30,llmlingua2_repair_v1_r50,llmlingua2_repair_v1_r30' \
  --judge-mode per_fact --answer-prompt v1 --semantic
```

임베딩 역할의 모델·서버 설정이 필요하다. 현재 설정이 과거 실험과 같은지 확인하고 새 run으로 실행한다. `--semantic`은 최종 실험 지표 계산 옵션이며, 이 옵션이 없어도 repair 압축기는 선정 구간의 임베딩을 요청한다. 기본 임베딩 역할이 원격 서버라면 해당 요청 비용도 발생할 수 있다.

## 기록과 한계

trial의 info에 base 압축 로그, config, selected_sentences(원문 위치·질문 관련성·원문·대응 압축문·유사도·조치), restored_sentences, added_tokens, base_context_tokens, final_context_tokens를 기록한다. 임베딩 오류는 skip_embedding_error로 기록하고 해당 문장은 복원하지 않는다. skipped_uncertain_alignment, skip_budget, skip_overlap도 확인해야 한다.

의미 유사도가 높은 관계 손실은 검출하지 못할 수 있다. 질문과 단어가 겹치지 않는 중요 문장도 선정에서 빠질 수 있다. 이는 정답 보존을 보증하는 검사기가 아니다. 추가 임베딩 연산 시간은 압축 소요 시간에 포함되지만 임베딩 서비스 비용은 생성 모델 토큰 카운터에 자동 합산되지 않는다.

최종 입력 절감률·정확도뿐 아니라 복원량·복원 건수·정렬/임베딩 실패·전체 처리 시간을 함께 보고한다. 현재 전후 비교 점수로부터 정확도 개선을 주장하지 않는다.

## 검증 상태

신규 9개 테스트와 기존 테스트를 포함한 전체 169개 통과. 낮은 유사도 복원, 높은 유사도 유지, 추가 토큰 상한, 완전 삭제 문장 삽입 위치, 임베딩 오류, 관련 문장 없음, 문장 경계, 정렬 실패를 검증했다. 이 테스트의 임베딩과 압축 출력은 주입한 테스트 대역이다. 실제 임베딩 모델의 유사도 분별력 및 답변 정확도 효과는 아직 검증하지 않았다.

## 원리·실험 결과와 공유 근거

전체 설명과 두 차례 실험 비교는 [RESULTS.md](RESULTS.md)에 있다. [analyze.py](analyze.py)는 로컬 results/runs의 세 원시 실행을 읽고 통계를 표준 출력으로 내보낸다. 원자료·생성된 JSON 분석 결과는 PR에 포함하지 않는다. 추가 모델 호출은 없다.
