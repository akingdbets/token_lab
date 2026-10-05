# 파일

- [HTTP Basic, API 키, 기타 보안 스킴](http-basic-and-api-keys.md) - fastapi.security의 HTTPBasic/HTTPBasicCredentials로 HTTP Basic 인증을 하고 secrets.compare_digest로 타이밍 공격을 막는 방법, APIKeyHeader·APIKeyQuery·APIKeyCookie, HTTPBearer/HTTPAuthorizationCredentials, HTTPDigest, OpenIdConnect 스텁, auto_error=False로 선택적 인증, 401 응답과 WWW-Authenticate 헤더, OpenAPI 보안 스킴 문서화를 설명한다.
- [JWT 토큰과 비밀번호 해싱](oauth2-jwt.md) - OAuth2 비밀번호 흐름에 PyJWT로 서명된 JWT 액세스 토큰(HS256, exp 만료, sub 주체)을 발급·검증하고, pwdlib(Argon2, PasswordHash.recommended())로 비밀번호를 해싱·검증하며, 존재하지 않는 사용자에도 DUMMY_HASH로 검증해 타이밍 공격을 막는 완전한 예제를 설명한다.
- [보안 기초: OAuth2 비밀번호 흐름과 현재 사용자](oauth2-password-flow.md)
- [OAuth2 스코프](oauth2-scopes.md) - OAuth2PasswordBearer(scopes={...})로 사용 가능한 스코프를 선언하고, 토큰에 스코프를 담고, Security(dependency, scopes=[...])로 경로 작업·의존성별 필요 스코프를 선언하며, SecurityScopes로 의존성 트리 전체에 누적된 스코프를 검사하는 방법, 캐시 동작, 서드파티 연동용 다른 OAuth2 흐름을 설명한다.
