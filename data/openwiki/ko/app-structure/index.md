# 파일

- [큰 애플리케이션: APIRouter로 여러 파일 구성](bigger-applications.md)
- [수명 주기 이벤트(lifespan)](lifespan-events.md) - FastAPI(lifespan=...)에 비동기 컨텍스트 매니저를 넘겨 앱 시작 전·종료 후 로직(ML 모델 로드, 커넥션 풀 등)을 실행하는 방법과, 더 이상 권장되지 않는 on_event("startup"/"shutdown") 이벤트, 라우터 lifespan 병합, 서브 앱과의 관계를 설명한다.
- [메타데이터와 문서 URL, 조건부 OpenAPI](metadata-and-docs-urls.md) - FastAPI() 생성자의 title·summary·description·version·terms_of_service·contact·license_info, openapi_tags로 태그 설명과 순서 지정, openapi_url·docs_url·redoc_url 변경 및 비활성화, pydantic-settings로 환경에 따라 OpenAPI를 끄는 방법을 다룬다.
- [경로 작업 설정(기본·고급)](path-operation-configuration.md) - 경로 작업 데코레이터 파라미터 status_code, tags(Enum 포함), summary, description, docstring(Markdown·\f 절단), response_description, deprecated와 고급 설정 operation_id, generate_unique_id_function, include_in_schema, openapi_extra(확장 필드, 직접 정의한 requestBody)를 예제와 함께 설명한다.
- [설정과 환경 변수(pydantic-settings)](settings.md) - pydantic-settings의 BaseSettings로 환경 변수를 타입 검증된 설정 객체로 읽고, 별도 모듈·의존성(Depends + @lru_cache)으로 제공하며, .env 파일(SettingsConfigDict(env_file=".env"))을 읽고, 테스트에서 dependency_overrides로 설정을 교체하는 방법을 설명한다.
- [서브 애플리케이션, 프록시 뒤 실행, WSGI 마운트](sub-applications-proxy-and-wsgi.md) - app.mount()로 독립된 FastAPI 서브 앱(자체 OpenAPI·문서)을 붙이는 방법, Traefik/Nginx 같은 프록시 뒤에서 --forwarded-allow-ips와 root_path(--root-path, FastAPI(root_path=...))를 쓰는 방법, OpenAPI servers와 root_path_in_servers, a2wsgi의 WSGIMiddleware로 Flask·Django를 마운트하는 방법을 설명한다.
