# SOURCE — OpenWiki (DuckDB, English)

| 항목 | 값 |
|---|---|
| OpenWiki | `openwiki` 0.7.0 |
| 생성 방식 | Claude Code 연동 (host agent가 페이지 작성) |
| 생성 모델 | Claude Code host agent (`.last-update.json`: `model: host-agent/claude`). 세부 모델 ID는 OpenWiki가 기록하지 않음 |
| 생성 일시 | init 2026-11-27 23:54 KST (`2026-11-27T14:54:17Z`, `status: complete`) |
| 이후 갱신 | update 2026-11-28 01:07 KST (`2026-11-27T16:07:12Z`, `command: update`, `status: complete`). `quickstart.md` Claim 4개의 근거 줄 범위만 바로잡음. 본문 변경 없음 |
| 언어 | en (`INSTRUCTIONS.md`: "Write every wiki page in English.") |
| 입력 문서 | `duckdb/duckdb-web` 커밋 `d849caa9`의 `docs/2.0` 일부 (267개 파일) |
| 입력 저장소 커밋 | `06611500a17932d6dd558ecccae7811b4d0ebdd7` (`.last-update.json`·`.page-manifest.json`의 `gitHead`). `_config.yml`로 `{{ site.* }}` 변수를 해석(`latest_duckdb_version` 2.0.1) |
| 입력 범위 | `docs/2.0` (+ `README.md`, `LICENSE`, `_config.yml`) |
| 내용 | 페이지 71개 (본문 54 + 섹션 index 17), `.claims/` 근거 파일 포함 |

원본 `openwiki/` 폴더를 숨김 파일(`.claims/`, `.page-manifest.json`, `.last-update.json`)까지 그대로 복사했다.
OpenWiki가 입력 저장소 루트에 만든 `AGENTS.md`, `.github/`는 복사하지 않았다.
이 `SOURCE.md`만 복사 후 추가한 파일이다.
