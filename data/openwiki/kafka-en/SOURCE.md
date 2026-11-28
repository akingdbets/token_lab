# SOURCE — OpenWiki (Apache Kafka, English)

| 항목 | 값 |
|---|---|
| OpenWiki | `openwiki` 0.7.0 |
| 생성 방식 | Claude Code 연동 (host agent가 페이지 작성) |
| 생성 모델 | Claude Opus 5.5 (사용자 제공). OpenWiki 기록은 `host-agent/claude`이며 세부 모델 ID는 기록하지 않음 |
| 생성 완료 | 2026-11-28 15:13:43 KST (`2026-11-28T06:13:43.544Z`, `command: init`, `status: complete`) |
| 언어 | en (`INSTRUCTIONS.md`: "Write every wiki page in English.") |
| 원본 저장소 | `apache/kafka` 커밋 `1156b2752aaa28eafc0b4c4d387e63356793268d` (`Bump version to 4.4.0`) |
| 입력 저장소 커밋 | `7144ac76dc0be7f228ea91f0735925a8cba666fd` (`Kafka 4.4.0 docs input for OpenWiki`), `.last-update.json`·`.page-manifest.json`의 `gitHead` |
| 입력 범위 | `docs/` (설정 참조용 `docs/generated/` HTML 표 포함), `config/`, `examples/`, `README.md`, `LICENSE`, `NOTICE` — 추적 파일 122개 (`openwiki/INSTRUCTIONS.md` 포함) |
| 버전 주의 | 원본 저장소 버전은 4.4.0이나 문서 인덱스는 `AK 4.3.X`이며 예제에 4.3.x 버전이 포함됨. 위키의 버전 설명을 그대로 보존함 |
| 내용 | 본문·진입 페이지 53개 (주제 페이지 52 + `quickstart.md`), index 11개, `.claims/` 근거 파일 53개 |

원본 `openwiki/`의 120개 파일을 숨김 파일(`.claims/`, `.page-manifest.json`, `.last-update.json`)까지 그대로 복사했다.
입력 저장소 루트의 `AGENTS.md`, `.github/`는 복사하지 않았다.
이 `SOURCE.md`만 복사 후 추가한 파일이다. `repo://` 출처 및 근거 줄 범위는 위 입력 저장소를 기준으로 한다.
