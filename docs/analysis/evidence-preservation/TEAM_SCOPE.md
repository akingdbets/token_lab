# PR 범위와 통합 검토

최신 main `13ef62ca8041c7c69aee260fc87aff0643a44fff`에서 별도 `feature/token-budget-evidence-preservation` 브랜치를 만들었다. 원래 연구 작업 트리/미커밋 파일/원시 실험 로그는 그대로 보존했다. 측정은 더 이른 base commit 및 미커밋 연구 코드에서 수행됐으며 정확한 구현은 `data/provenance.json`의 코드 해시로 식별한다. 이 PR 준비 중 새 LLM API 실험을 하지 않았다.

검토 시 #50/#57/#58은 모두 open이었다.

|PR|영역|이 PR과의 관계|
|---|---|---|
|[#50](https://github.com/akingdbets/token_lab/pull/50)|쪼개진 점/하이픈의 단어 라벨 기반 사후 표기 복원|`llmlingua2.py`와 해당 테스트를 가져오거나 변경하지 않는다. 우리 것은 압축 전 선택 보호+동일 예산이고 `_punct` 이름과 다르다.|
|[#57](https://github.com/akingdbets/token_lab/pull/57)|질문 관련 문장의 임베딩 유사도 기반 사후 repair, 추가 입력 상한|목적은 관련되지만 별도 구현·이름·경로다. 우리 것은 임베딩 호출 없이 BM25로 압축 전 보호하고 기존 r30 예산 안에서 재배분한다. repair.py/팀원 결과·검수 문서를 포함하지 않는다.|
|[#58](https://github.com/akingdbets/token_lab/pull/58)|기존 test 설정별 이력·의미 손실 문서|그 파일은 수정하지 않는다. 우리 문서는 docs/analysis/evidence-preservation 아래의 별도 dev/독립 평가다.|

공통 변경 파일은 `src/compressors/__init__.py`뿐이다. 기존 dictionary 항목을 덮어쓰지 않고 새 class의 등록을 뒤에 추가한다. #50/#57의 registry 각각과 base를 둔 3-way text merge를 별도 임시 파일에서 시험했으며 충돌0이었다. 기존 압축기 구현이나 기본값은 수정하지 않는다. 향후 두 PR이 동시에 변경되거나 main이 진전되면 재확인이 필요하다.

원래 작업 트리에 있던 `src/punctuation_guard_pilot.py`, `src/punctuation_guard_answer.py`, `src/compression_damage_scan.py`, ZIP 및 기존 PR/병합 파일은 선별 범위에서 제외했다. 출처가 다른 탐색 코드와 팀원 작업을 이 커밋에 섞지 않는다. 전체 생성 HTML/대량 contexts/캐시/원시 API 로그/개인 로컬 경로도 제외했다. 연구 관련 공개 코드·소규모 수치와 출처만 포함한다.

검토에는 최신 main 기존 테스트를 포함해 오프라인191개를 실행했고185개 통과/6개 private-artifact 의존 테스트 생략이었다. 공개 결과/해시/토큰 비교/신뢰구간 테스트는 실행했다. HTTP/소켓 차단 하에서 성공해 추가 API 호출이 없음을 확인했다.
