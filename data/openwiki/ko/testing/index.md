# 파일

- [비동기 테스트와 데이터베이스 테스트](async-tests-and-database.md) - pytest.mark.anyio와 httpx.AsyncClient(ASGITransport)로 async def 테스트에서 FastAPI 앱을 호출하는 방법, AsyncClient가 lifespan을 실행하지 않는 문제와 asgi-lifespan, 다른 이벤트 루프 오류 대처, 그리고 세션 의존성을 dependency_overrides로 교체해 테스트용 데이터베이스(SQLModel/SQLite)로 테스트하는 방법을 설명한다.
- [테스트: TestClient, 의존성 오버라이드, 이벤트, WebSocket](testing-basics.md)
