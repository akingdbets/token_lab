# Token-budget-aware evidence preservation

강한 LLMLingua-2 압축에서 필요한 값·관계·조건이 손실되는 문제를 분석하고, 질문 관련 원문을 선택 보존하는 실험이다. **이 소규모 자동 생성·자동 채점 평가셋에서, 동일 전체 입력 예산에서 관찰된 개선**을 보고한다. 일반적인 기술 QA 성능이나 배포 효과를 확정하지 않는다.

- [결과·ablation·통계·한계](RESULTS.md)
- [Oracle 진단 방법](ORACLE.md)
- [압축 손실 검수 도구](DAMAGE_REVIEW.md)
- [기존 PR과의 범위·통합 검토](TEAM_SCOPE.md)
- `data/metrics.csv`: dev210 + 독립186 = 396시행의 작은 수치 테이블. 답변 원문·요청 ID·로컬 경로·원시 로그 없음.
- `data/oracle_metrics.csv`: Oracle90시행의 수치 테이블.
- `data/statistics.json`: 아래 오프라인 분석으로 재생성 가능.
- `data/independent_qa.json`, `data/audit_decisions.json`, `data/sources.json`: 자동 검수 통과31문항, 후보32개 판정, 공개 출처·해시.
- `corpus/`: 실제 평가에 사용한 고정 추출본8개. 인코딩 오류를 사후 수정하지 않았다. 라이선스는 `corpus/LICENSE.txt` 참조.
- `data/provenance.json`: 측정 당시 base commit, 코드/프롬프트 해시, freeze 시점, 모델 설정. 당시 연구 코드는 미커밋 상태였으므로 base commit만으로 구현을 특정하지 않으며 개별 코드 해시를 함께 사용한다.

## API 없는 검토·재현

Python3.12, `requirements.txt` 환경에서 저장소 루트 기준:

```sh
python scripts/test_evidence_offline.py
python scripts/analyze_evidence_results.py --output /tmp/tokenlab_statistics.json
```

테스트 실행기는 HTTP와 소켓 연결을 차단한다. 모델 호출은 mock으로 대체한다. 현재 **191개 실행: 185개 통과, private 원시 산출물 의존6개 생략**이다. 공개 지표의 통계·인용문·코드 해시는 별도 테스트하며 생략하지 않는다. 모델 가중치나 실제 API 실험을 실행하지 않는다.

`numpy`만으로 공개 통계를 재계산할 수 있다. API 실행기/전체 테스트 환경은 나머지 requirements를 사용한다. paired bootstrap은 문항 순서를 `question_order`로 고정한다. 기존 원시 run 없이도 주 결과, 직접 ablation 대조, 문서 군집 CI, Oracle 회복 분모를 재현한다.

## 전체 실험을 다시 실행할 때

이 PR을 게시하는 과정에서는 새 LLM 실험을 실행하지 않았다. 다음은 별도 비용이 발생하는 미래 재현 절차다.

```sh
# 1. 로컬 압축 준비, dev 새 평가, 알고리즘 고정
python scripts/final_experiment.py prepare --split dev
python scripts/final_experiment.py run --split dev       # 유료 API
python scripts/final_experiment.py freeze

# 2. 고정 후 독립 출처 수집·문항 생성/자동 감사·데이터셋 고정
python scripts/final_experiment.py dataset               # 유료 API
python scripts/final_experiment.py prepare --split independent
python scripts/final_experiment.py run --split independent # 유료 API

# 3. 저장 자료로 재집계
python scripts/final_experiment.py summarize --split dev
python scripts/final_experiment.py summarize --split independent
python scripts/final_experiment_report.py report
```

기존 결과를 지우지 말고 별도 checkout/output을 사용한다. plan/dataset/freeze는 덮어쓰기를 거부한다. 기본 설정 파일은 `docs/analysis/final-experiment/config.json`이다. 로컬 LLMLingua-2 가중치 revision `5f0c827`을 미리 준비해야 하며 실험기는 HF offline 모드를 사용한다. 답변/채점 키는 각자의 환경변수나 로컬 `.env`에만 둔다. 모델·endpoint·seed는 측정 조건으로 고정되어 있으며 키 값은 공개하지 않는다.

정확한 역사적 출력은 별도 보관된 원시 산출물이 필요하다. 새로운 생성/채점은 같은 seed여도 달라질 수 있다. 공개 통계의 비트 단위 재현과 새 API 평가를 구분한다. 역사적 full artifacts로 공개 테이블을 새 경로에 다시 내보내려면:

```sh
python scripts/export_evidence_publication.py --source-root "$TOKENLAB_ARTIFACT_ROOT" --output /tmp/tokenlab_publication
```

이 exporter는 source를 읽기만 하고 명시한 필드만 내보낸다. `data/manifest.json`은 exporter 입력 사본들의 해시이며 후속 계산 파일 `statistics.json`과 설명 문서는 별도다. QA의 로컬 출력 경로를 제거했으므로 공개 JSON의 바이트 해시와 원래 private dataset 해시는 다르다. 질문·정답·사실·인용 내용은 바꾸지 않았다.

원시 run, contexts 대량 출력, 답변 캐시, ZIP, `.env`, 키, `.venv`, 일반 캐시 및 Git 내부 파일은 커밋하지 않는다. scoped `.gitignore`는 연구 출력 디렉터리를 제외하고 설정 파일만 허용한다.
