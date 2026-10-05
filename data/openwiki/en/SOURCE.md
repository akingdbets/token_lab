# SOURCE — OpenWiki (English)

**용도: 실험에 쓰는 위키. 다시 생성하지 않는다.**

| 항목 | 값 |
|---|---|
| OpenWiki | `openwiki` 0.7.0 (npm) |
| 생성 방식 | Claude Code 연동 (`openwiki integrations install claude`, host agent가 페이지 작성) |
| 생성 모델 | Claude Code host agent (`.last-update.json`: `model: host-agent/claude`, 페이지별 `completedBy: claude-code`). 세부 모델 ID는 OpenWiki가 기록하지 않음 |
| 생성 일시 | 2026-10-05 12:09:52 KST (`2026-10-05T03:09:52Z`, `command: init`, `status: complete`) |
| 언어 | en (`INSTRUCTIONS.md` 첫 줄: "Write every wiki page in English.") |
| 입력 FastAPI 커밋 | `5f9fc5c59a9bb54608aa35376715f3ba9708188e` (v0.142.2). 코퍼스 기준 `50113da`(v0.142.2)와 매니페스트의 574개 파일이 모두 같은 내용임을 sha256으로 확인함 |
| 복사본 저장소 커밋 | `3519f526a60f96a35af48c4b1aeb798884f529bf` (`.last-update.json`·`.page-manifest.json`의 `gitHead`) |
| 입력 범위 | `docs/en`, `docs_src`, `fastapi` (+ `README.md`, `pyproject.toml`, `LICENSE`). 다른 언어 문서·tests·scripts 제외 |
| 내용 | 페이지 66개 (본문 50 + 섹션 index 16), `.claims/` 근거 파일 포함 |

원본 `openwiki/` 폴더를 숨김 파일(`.claims/`, `.page-manifest.json`, `.last-update.json`)까지 그대로 복사했다.
이 `SOURCE.md`만 복사 후 추가한 파일이다.
