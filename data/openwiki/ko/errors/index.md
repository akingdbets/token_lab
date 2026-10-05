# 파일

- [오류 처리와 예외 핸들러](handling-errors.md) - HTTPException으로 4xx 오류 반환(detail에 JSON 값, headers 추가), @app.exception_handler로 사용자 정의 예외 처리, RequestValidationError·StarletteHTTPException 기본 핸들러 재정의, exc.body 활용, fastapi.exception_handlers의 기본 핸들러 재사용, 보안 클래스의 401/403 상태 코드 변경(make_not_authenticated_error)을 설명한다.
