# 파일

- [폼 데이터와 파일 업로드](forms-and-files.md) - python-multipart 설치 후 Form()으로 폼 필드 받기, Pydantic 폼 모델과 extra="forbid", File()로 bytes 받기와 UploadFile(filename, content_type, file, async read/write/seek/close), 선택적·다중 파일 업로드, 폼과 파일을 함께 받는 방법, JSON Body와 섞을 수 없는 이유를 설명한다.
- [헤더와 쿠키 파라미터](headers-and-cookies.md) - Header()로 요청 헤더를 받는 방법과 밑줄→하이픈 자동 변환(convert_underscores), 중복 헤더를 list로 받기, Cookie()로 쿠키 받기, Pydantic 모델로 헤더·쿠키 파라미터 묶기(FastAPI 0.115.0+)와 extra="forbid"로 추가 헤더·쿠키 거부, 문서 UI에서 쿠키를 보낼 수 없는 이유를 설명한다.
- [중첩 모델과 추가 데이터 타입](nested-models-and-data-types.md) - 요청 본문에서 list[str]·set[str] 같은 타입 파라미터 필드, 하위 모델 중첩, HttpUrl 같은 특수 타입, 모델 리스트·깊은 중첩, list/dict 본문(dict[int, float])을 쓰는 방법과 UUID·datetime·date·time·timedelta·frozenset·bytes·Decimal 등 추가 데이터 타입의 표현, val_json_bytes/ser_json_bytes로 JSON 안의 base64 bytes를 처리하는 방법을 설명한다.
- [경로 파라미터와 숫자 검증](path-parameters.md) - Python 포맷 문자열 문법으로 경로 파라미터를 선언하고 타입(int 등)으로 변환·검증하는 방법, 경로 작업 선언 순서, str+Enum으로 허용 값 제한, {file_path:path}로 경로를 포함하는 파라미터, Path()로 메타데이터와 gt/ge/lt/le 숫자 검증, 파라미터 순서와 * 트릭, FastAPI가 파라미터 종류를 판별하는 규칙을 설명한다.
- [쿼리 파라미터, 문자열 검증, 쿼리 파라미터 모델](query-parameters.md) - 경로에 없는 함수 파라미터가 쿼리 파라미터가 되는 규칙, 기본값·선택·필수 파라미터와 bool 변환, Annotated + Query()로 min_length/max_length/pattern 검증과 title/description/alias/deprecated/include_in_schema 메타데이터, 리스트(다중 값) 쿼리, AfterValidator 사용자 검증, Pydantic 모델로 쿼리 파라미터 묶기와 extra="forbid"를 설명한다.
- [요청 본문: Pydantic 모델, 여러 본문 파라미터, Field](request-body.md)
- [Request 객체 직접 사용과 커스텀 Request/APIRoute](using-request-directly.md) - 경로 작업 파라미터를 Request 타입으로 선언해 Starlette Request(클라이언트 IP, 원시 본문 등)에 직접 접근하는 방법과 검증·문서화가 생략된다는 점, Request 서브클래스(GzipRequest)와 APIRoute.get_route_handler() 재정의로 요청 본문 변환·예외 처리·응답 시간 측정을 하는 방법, app.router.route_class와 APIRouter(route_class=...)로 적용 범위를 정하는 방법을 설명한다.
