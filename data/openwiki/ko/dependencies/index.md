# 파일

- [고급 의존성: 파라미터화된 의존성](advanced-dependencies.md)
- [데코레이터 의존성과 전역 의존성](decorator-and-global-dependencies.md) - 반환값이 필요 없는 의존성을 경로 작업 데코레이터의 dependencies=[Depends(...)]로 실행하는 방법, APIRouter·include_router·FastAPI(dependencies=...)로 경로 작업 그룹과 앱 전체에 의존성을 적용하는 방법, 실행 순서를 설명한다.
- [yield를 사용하는 의존성](dependencies-with-yield.md) - return 대신 yield를 쓰는 의존성으로 DB 세션 같은 리소스를 만들고 정리하는 방법, try/except/finally와 예외 재발생 규칙, 하위 의존성 종료 순서, Depends(scope="function"|"request")로 종료 시점 제어, 컨텍스트 매니저 사용을 설명한다.
- [의존성 주입 기초: Depends, 클래스, 하위 의존성](dependency-injection-basics.md)
