# TokenLab Dashboard 데이터 기반

이 디렉터리는 실험 결과를 PostgreSQL에 읽어 들이고 Grafana 대시보드를 자동 등록합니다. 기존 실험 코드와 결과 파일을 변경하지 않습니다.

## 구조

```text
dashboard/
├── docker-compose.yml                    PostgreSQL, importer, Grafana
├── .env.example                          환경변수 예시
├── importer/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/import_results.py             결과 검증 및 DB 수입
│   └── tests/test_import_results.py      합성 입력과 검증 테스트
├── sql/001_schema.sql                    초기 DB 스키마
└── grafana/
    ├── dashboards/tokenlab-mvp.json      버전 관리하는 MVP 대시보드
    └── provisioning/
        ├── dashboards/tokenlab.yml       대시보드 자동 등록
        └── datasources/tokenlab.yml      PostgreSQL 자동 등록
```

## 시작과 종료

Docker Desktop이 실행 중이어야 합니다. `dashboard/`에서 실행합니다.

```bash
cp .env.example .env
# .env의 두 비밀번호를 로컬에서 변경
docker compose config --quiet
docker compose up --build -d
docker compose ps --all
docker compose logs importer
```

`.env`는 `dashboard/.gitignore`에 포함됩니다. 실제 비밀번호를 `.env.example`이나 Git 추적 파일에 넣지 마세요. PostgreSQL 포트는 호스트에 공개하지 않습니다. `results/`와 `data/evalsets/`는 importer에 읽기 전용으로 마운트합니다. Apple Silicon에서는 각 이미지의 ARM64 변형이 사용됩니다.

Grafana 주소는 <http://127.0.0.1:3001/>입니다. 관리자 계정은 `.env`의 `GRAFANA_ADMIN_USER`와 `GRAFANA_ADMIN_PASSWORD`를 사용합니다. 데이터 소스 `TokenLab PostgreSQL`과 [TokenLab Experiment Dashboard](http://127.0.0.1:3001/d/tokenlab-experiment-mvp/tokenlab-experiment-dashboard)가 자동 등록됩니다. JSON 파일을 수정하면 Grafana가 주기적으로 다시 읽습니다. Grafana 컨테이너를 재시작해도 대시보드가 유지됩니다. UI에서 변경한 내용은 파일 기반 설정으로 덮어써질 수 있으므로 JSON 파일을 수정하세요.

```bash
docker compose down
```

`down`은 컨테이너와 네트워크를 종료하지만 PostgreSQL과 Grafana의 named volume은 유지합니다.

## MVP 대시보드

- `Run ID`는 사람이 읽기 쉬운 Run ID·namespace·DB 번호를 보여주고, 실제 쿼리에는 `run_pk`를 사용합니다. `Compressor`는 선택한 Run의 압축기만 표시합니다. 비교 차트는 Compressor 선택과 관계없이 해당 Run의 모든 압축기를 표시합니다.
- Run Metadata와 Data Availability는 설정값과 결측 사유를 표시합니다. Dataset 버전이나 Judge Mode가 불명확하면 `Unknown`으로 표시합니다.
- 여섯 Stat은 최신 input/net input 절감률, semantic similarity, entity retention, answer accuracy, accuracy retention을 보여줍니다. 최신 지표를 레거시 context 지표로 대체하지 않습니다.
- 두 Bar Chart는 동일 Run의 압축기별 최신 input 절감률과 답변 정확도를 비교합니다. XY Chart는 두 지표가 모두 있는 압축기만 점으로 표시합니다.
- Question Results는 선택한 Run·Compressor의 질문별 결과를 표시하고, 최신 input 절감률과 레거시 context 절감률을 별도 열로 둡니다. `NOT FOUND`는 원본 Trial JSON에 해당 필드가 있을 때만 표시합니다.

현재 저장된 3개 Run은 모두 레거시여서 최신 input 절감률 Stat은 `N/A`, 해당 Bar Chart와 XY Chart는 `No data`가 정상입니다. 반면 실제 0점인 Accuracy는 `0%`로 표시됩니다. Semantic Similarity가 계산되지 않은 Run에서는 `N/A`이며, 계산된 Run에서는 저장된 원값을 표시합니다. 음수 절감률과 100% 초과 Accuracy Retention을 잘라내지 않습니다. Dashboard는 시간 필터를 사용하지 않으며 서로 다른 Run을 한 그래프에 섞지 않습니다.

대시보드가 보이지 않으면 `docker compose logs grafana`에서 provisioning 오류를 확인하고, `docker compose config --quiet`로 마운트를 점검하세요. Grafana API의 `/api/dashboards/uid/tokenlab-experiment-mvp`에서 등록 상태를 확인할 수 있습니다. 새 Run을 추가했다면 먼저 importer를 재실행하고 브라우저에서 대시보드를 새로고침하세요.

## 재수입과 DB 확인

새 Run을 `results/runs/<run_id>/`에 추가한 뒤 다음을 실행합니다.

```bash
docker compose run --rm importer
```

동일한 파일을 다시 읽으면 `SKIPPED`가 출력됩니다. 같은 `SOURCE_NAMESPACE`와 Run ID에 다른 파일 해시가 이미 저장된 경우 `FAILED`로 기록하고 종료 코드 1을 반환합니다. 이때 DB의 기존 Run은 유지됩니다. 다른 머신의 Run을 합칠 때는 `.env`의 `SOURCE_NAMESPACE`를 머신/출처별 고유 값으로 설정하세요.

DB 레코드 수 확인:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT schema_version, count(*) FROM runs GROUP BY schema_version;"'
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM trials;"'
```

## DB 초기화

다음 명령은 **이 Compose 프로젝트의 PostgreSQL/Grafana named volume과 수입 데이터를 삭제**합니다. 기존 `results/` 파일은 삭제하지 않습니다. 실행 전 DB 데이터가 필요 없는지 확인하세요.

```bash
docker compose down -v
docker compose up --build -d
```

SQL 초기화 파일은 PostgreSQL volume이 처음 만들어질 때만 실행됩니다. 기존 volume에 스키마를 변경하려면 별도 마이그레이션이 필요합니다.

## 데이터 처리

- `runs`: 출처 namespace + Run ID, 파일 해시, 스키마 종류, LLM/Judge 설정, Dataset 식별 상태, 원본 Summary JSONB.
- `run_compressor_metrics`: Run + Compressor별 Summary 지표, Compressor 설정 및 원본 metrics JSONB.
- `trials`: 질문 + Compressor별 결과, 답변과 판정, 원본 Trial JSONB. 현재 repeat/turn index는 0이며 확장용 컬럼이 있습니다.

각 Run은 한 트랜잭션으로 수입합니다. Summary/Trial의 Run ID, Compressor 집합, 행 수, 중복 Trial, JSON 형식을 확인합니다. 오류가 나면 해당 Run의 DB 작업을 롤백하고 다른 Run의 수입은 계속합니다. 하나라도 실패하면 전체 importer의 종료 코드는 1입니다.

Dataset은 현재 `data/evalsets/*/qa_dataset.json`과 각 Trial의 문항 ID, split, type, 질문, 정답, 근거 페이지가 모두 일치하는 후보가 정확히 하나일 때 `content_match`로 기록합니다. 이 매칭은 과거 실행 시점의 평가셋 파일 해시를 증명하지 않습니다. 후보가 없거나 여러 개면 Dataset 이름/해시는 SQL `NULL`입니다. 독립적인 문항 집합 비교를 위해 `cohort_sha256`도 보존합니다.

Legacy Run은 `ctx_tokens_raw/ctx_tokens`, `reduction_pct`, `net_reduction_pct`를 가집니다. Current Run은 `input_tokens_raw/input_tokens`, `input_reduction_pct`, `net_input_reduction_pct`를 추가합니다. DB는 이 네 절감률을 별도 컬럼에 저장하며 누락 필드는 SQL `NULL`입니다. `0.0`은 실제 측정값으로 보존합니다. `answer_accuracy`와 `entity_retention`은 0~1 원값이고 `*_pct`는 이미 퍼센트 단위입니다.

## 테스트

표준 라이브러리 기반 검증 테스트:

```bash
docker compose run --rm --entrypoint python importer -m unittest discover -s /app/tests -v
```

DB 통합 테스트는 **별도의 테스트 DB**를 사용합니다. Fixture는 임시 디렉터리에서 생성되며 `results/`나 운영 DB에 들어가지 않습니다.

```bash
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" tokenlab_importer_test'
docker compose run --rm --entrypoint python \
  -e TEST_PGDATABASE=tokenlab_importer_test \
  -e TEST_SCHEMA_PATH=/app/sql/001_schema.sql \
  importer -m unittest discover -s /app/tests -v
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" tokenlab_importer_test'
```

테스트는 현행 스키마 fixture, 잘못된 JSON, 중복 Trial, Run ID/Compressor 불일치, 재수입 no-op, 해시 충돌, SQL `NULL`과 0, 트랜잭션 롤백을 확인합니다. `dropdb`는 위에서 직접 만든 테스트 DB만 제거합니다.

## 문제 해결

- Grafana에 접속되지 않으면 `docker compose ps --all`과 `docker compose logs grafana`를 확인하세요. 호스트 포트 3001을 다른 앱이 쓰는지도 확인합니다.
- Importer가 DB 연결에 실패하면 `docker compose ps --all`에서 `db`가 healthy인지 확인하세요.
- `FAILED ... invalid JSON`은 해당 원본 Run 파일의 문법 오류입니다. Importer는 원본을 수정하지 않습니다.
- `existing run ID has different file hashes`는 같은 namespace/Run ID에 내용이 다른 파일이 이미 수입됐다는 뜻입니다. 출처가 다른 실행이면 `SOURCE_NAMESPACE`를 분리하고, 같은 실행을 재수정한 것이라면 원본 및 DB 정리 방침을 먼저 결정하세요.
- Grafana 데이터 소스가 보이지 않으면 `docker compose logs grafana`에서 provisioning 오류를 확인하세요. `.env`의 DB 접속 정보를 바꾼 뒤에는 `docker compose up -d --force-recreate grafana`로 컨테이너 환경을 갱신합니다. Grafana 관리자 암호는 첫 초기화 후 volume에 저장되므로 `.env`만 바꿔도 기존 암호가 자동 변경되지는 않습니다.
