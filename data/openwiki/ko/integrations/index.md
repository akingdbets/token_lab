# 파일

- [백그라운드 작업](background-tasks.md) - BackgroundTasks 파라미터와 add_task()로 응답을 보낸 뒤 실행할 작업(이메일 알림, 파일 처리 등)을 등록하는 방법, 의존성 여러 단계에서 같은 BackgroundTasks 객체 공유, Response를 직접 반환할 때의 동작, Starlette BackgroundTask와의 차이, Celery 같은 대안을 설명한다.
- [GraphQL과 OpenTelemetry 연동](graphql-and-opentelemetry.md) - Strawberry의 GraphQLRouter 등 ASGI 호환 GraphQL 라이브러리를 FastAPI에 붙이는 방법과, FastAPI 내장 OpenTelemetry 지원(HTTP 트레이스·메트릭·로그, WebSocket 트레이스)을 OTLP 환경 변수와 FastAPI(telemetry={...}) 설정(tracer_provider, operation_spans, exclude, auto_configure 등)으로 구성하는 방법을 설명한다.
- [SQL 데이터베이스(SQLModel)](sql-databases.md) - SQLModel(SQLAlchemy + Pydantic)로 FastAPI 앱에 SQL 데이터베이스를 연결하는 방법—테이블 모델과 create_engine(check_same_thread), create_all로 테이블 생성, yield 세션 의존성(SessionDep), CRUD 경로 작업, HeroBase/Hero/HeroPublic/HeroCreate/HeroUpdate 다중 모델 패턴, model_dump(exclude_unset=True)와 sqlmodel_update로 PATCH 구현—을 설명한다.
- [정적 파일, 템플릿, 프론트엔드](static-files-templates-frontend.md) - StaticFiles를 app.mount()로 마운트해 정적 파일을 제공하는 방법, Jinja2Templates와 TemplateResponse(request, name, context)·url_for로 HTML을 렌더링하는 방법, app.frontend()/router.frontend()로 Vite·Astro 등의 정적 프론트엔드 빌드를 낮은 우선순위 라우트로 제공하는 방법(fallback="auto"/"index.html"/"404.html"/None, check_dir, 의존성·미들웨어 적용)을 설명한다.
- [WebSocket](websockets.md)
