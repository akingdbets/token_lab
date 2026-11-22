# Oracle 근거 복원 진단

배포용 압축기와 별개의 정답 정보 활용 진단이다. 기존 Terra test 압축 실패41개에서 원문을 대조해 정보 삭제A5/관계·조건 손상B5의 고정 manifest를 먼저 만들었다. 의심스러운 Judge/gold D 사례는 우선 제외했다. A/B는 Codex의 원문 대조 예비 분류이며 독립 사람 라벨이 아니다.

선정 기준과 이유는 `docs/analysis/oracle-pilot/selection_config.json`. qid는 A: c0046/c0052/c0086/c0101/c0134, B: c0049/c0073/c0096/c0155/c0162, 모두 r30이다. 목적 표집10문항이지 모집단 원인 비중이 아니다.

- Baseline: 기존 r30 압축 문맥.
- Placebo: 질문과 무관한 원본 worker/메모리 문서의 연속 prefix를 추가.
- Oracle: 원본 none 문맥과 실제 기술 문서에 모두 존재하는 구절을 그대로 추가. gold 답변을 새로 써 넣지 않는다.
- 두 삽입 조건은 같은 문맥 끝 위치/두 줄 delimiter이고 전체 입력 토큰 수를 맞췄다. 실제 API 입력 차이는18쌍0, 9쌍−1, 3쌍+1토큰이었다.
- 같은 Terra/prompt와 Judge 설정, seed42/temperature0으로 조건당3회, 총90시행. 동일 seed 반복은 독립 n=90이 아니다. 첫 API 호출 전 대상·구절·예상 호출/토큰·해시를 고정했다.

|조건|평균 핵심 사실 정확도|완전 정답|
|---|---:|---:|
|Baseline|15.83%|2/30|
|Placebo|12.50%|0/30|
|Oracle|100.00%|30/30|

재실행 baseline이 historical none보다 낮은28쌍을 회복 분모로 삼으면 Oracle28/28, Placebo0/28이다. baseline이 이미 정답인2쌍은 Oracle 개선으로 세지 않았다. c0096의 동일 답변/근접 의미 답변에 점수가 달랐고 c0162의 첫 사실도 불안정했다. 실제 답변 텍스트와 per-fact 판정은 별도 원시 산출물에 보존했다. 이 숫자를 원인별 발생률이나 배포 성능으로 쓰지 않는다.

## 재현

```sh
# API 없는 공개 수치 재집계
python scripts/analyze_evidence_results.py --output /tmp/tokenlab_statistics.json

# 별도 보관한 원본 run/실패 분석 자료가 있을 때만 새 진단 준비
python scripts/oracle_pilot.py prepare
# 대상/실제 원문 구절/dry-run을 검토한 후에만 실행
python scripts/oracle_pilot.py run      # 유료 API
python scripts/oracle_pilot.py report   # 저장 로그 재집계
```

prepare는 기존 plan을 덮어쓰지 않고 원본을 읽기만 한다. script는 raw outputs를 `docs/analysis/oracle-pilot/` 아래 생성하며 config만 Git으로 관리한다. `prepare`와 토큰 일치 단위 테스트는 새 답변 API를 호출하지 않는다. 기본 입력은 `results/runs/20261104-165320` 및 앞선 실패 검수 자료이며 원본 자료가 없는 공개 checkout에서는 해당 raw-artifact 통합 테스트를 명시적으로 생략한다.
