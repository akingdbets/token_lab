# Telegraph English 프롬프트 출처

- `compression_v5.txt`: Telegraph English 저자들이 공개한 압축 프롬프트(문법 명세 포함)를 **고치지 않고** 그대로 복사했다.
  - 논문: Arbuzov, Shvets, Bei 외, "Telegraph English: Semantic Prompt Compression via Structured Symbolic Rewriting", arXiv:2605.04426
  - 저장소: https://github.com/sibmike/telegrapher (`code/prompts/compression_v5.txt`), 커밋 `7aadc093eeebe63953722b79df1a57c57f569288`
  - 라이선스: CC BY-SA 4.0 (저장소 `LICENSE-docs`, 프롬프트 파일 대상). 이 파일을 바꿔 배포하면 같은 라이선스를 따른다
  - 저장소 README 는 이 파일을 "canonical Telegraph English grammar" 로 소개한다 (430행, 기호 약 40개, 12항목 품질 점검)
- `technical_rules_v1.md`: 이 프로젝트에서 쓴 **추가 규칙**이다 (저자 것 아님). 기술 문서용으로 코드 블록·식별자·숫자를 보존한다.
  변환 시 system 메시지 = `technical_rules_v1.md` + 빈 줄 + `compression_v5.txt` 이고, 변환할 본문은 user 메시지로 보낸다
  (저자 참고 구현 `code/telegrapher/compression/sync.py` 와 같은 메시지 구조).
