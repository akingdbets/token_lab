# 파일

- [요청 처리 흐름(사용자 관점의 내부 구조)](request-lifecycle.md) - FastAPI 앱이 ASGI 요청을 받아 응답을 보내기까지의 내부 흐름—미들웨어 스택 구성(ServerErrorMiddleware, 사용자 미들웨어, ExceptionMiddleware, AsyncExitStackMiddleware), 라우터 매칭, request_response의 두 AsyncExitStack, get_request_handler의 본문 파싱·의존성 해석·엔드포인트 실행·응답 검증/직렬화, OpenAPI 스키마 캐시—를 사용자가 디버깅에 필요한 수준으로 설명한다.
