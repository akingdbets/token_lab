# 압축 손실 원인 검수

`compression_failure_review.py`는 API 호출 없이 기존 summary/trials/contexts와 평가셋을 조인한다. 기본 dev는 `20261104-151606`, test는 중복 없는 완료 시행 수와 모델/split을 확인해 최신 Terra test를 선택한다. 정확도 하락은 동일 qid의 none 대비 각 압축 조건을 별개 시행으로 추출한다. 기존 데이터에서는 r30 29/r50 12, 비교분모278, 성공 표본16, 조인 누락0이었다.

```sh
python scripts/compression_failure_review.py --output docs/analysis/terra-review-new
```

생성 HTML은 CSS/JavaScript/자료가 내장된 오프라인 좌우 문맥 뷰어다. 질문·정답·key_facts·원본 근거·원본/압축 전체 문맥·none/압축 답변·정확도·NOT FOUND·토큰 감소율을 연결한다. 코드/줄바꿈은 pre-wrap으로 보존한다. 정확 인용 검색과 근사 탐색 후보를 구분한다. exact quote가 없다는 이유로 삭제를 확정하지 않는다. 누락/중복 조인은 metadata에 남기고 추측으로 채우지 않는다.

사람 입력은 fact별 `evidence_deleted`, `relation_damaged`, `evidence_sufficient`, `judge_or_gold_issue`, `primary_cause`, `confidence`, `memo`. 독립 원인 항목은 복합 원인을 허용한다. primary A/B/C/D/uncertain, confidence low/medium/high이며 공백은 미입력이다. 자동 상태는 unverified로 사람 판정과 별도다.

검수 ID는 `(run,qid,compressor,fact_index)`이며 fact_index는0부터다. CSV는 기본 식별자·점수·자동 상태와 위 사람 입력 열을 가진다. 브라우저 CSV 저장은 입력이 하나라도 있는 fact행만 반영한다. localStorage는 브라우저/파일 위치에 따라 보존이 달라지므로 JSON 백업/복원을 지원한다. 정답/메모 등 신뢰하지 않는 텍스트를 포함하므로 spreadsheet에서는 텍스트로 가져온다.

`--success-per-stratum`, `--seed`로 유형×조건 성공 대조 표집을 재현한다. 성공은 정확도1이며 하락하지 않은 시행이다. 표집 분수와 전체 paired 분모를 기록하고, 실패만 선택한 원인 비중을 전체 발생률로 일반화하지 않는다. metadata는 원본 실행 설정/경로/commit과 코드·입력 해시를 기록하지만 로컬 생성물은 커밋하지 않는다. 공개 집계는 `data/damage_counts.json`에 있다.
