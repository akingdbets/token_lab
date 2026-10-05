# 파일

- [OpenAPI 콜백과 웹훅](callbacks-and-webhooks.md) - 경로 작업 데코레이터의 callbacks=router.routes로 내 API가 호출할 외부 API(콜백)의 형태를 OpenAPI 표현식({$callback_url}, {$request.body.id})과 함께 문서화하는 방법, app.webhooks(APIRouter)로 내 앱이 보낼 웹훅 이벤트를 문서화하는 방법을 설명한다.
- [OpenAPI 확장과 문서 UI 커스터마이징](customizing-openapi-and-docs-ui.md) - app.openapi()와 openapi_schema 캐시 동작, fastapi.openapi.utils.get_openapi로 스키마를 생성·수정해 app.openapi를 교체하는 방법(x-logo 등), Pydantic v2의 입력/출력 스키마 분리와 separate_input_output_schemas=False, swagger_ui_parameters로 Swagger UI 설정, get_swagger_ui_html/get_redoc_html로 사용자 지정 CDN·자체 호스팅 문서 자산을 쓰는 방법을 설명한다.
- [클라이언트 SDK 생성](generate-clients.md) - FastAPI가 생성하는 OpenAPI 3.1 스키마로 Hey API(@hey-api/openapi-ts), OpenAPI Generator 등을 이용해 TypeScript 등 클라이언트 SDK를 생성하는 방법, 태그로 서비스 분리, generate_unique_id_function으로 operationId·메서드 이름을 개선하고 생성 전 openapi.json을 전처리하는 방법을 설명한다.
