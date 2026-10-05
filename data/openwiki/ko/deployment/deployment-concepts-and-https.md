---
type: concept
title: 배포 개념, HTTPS, 버전 관리
description: FastAPI 앱 배포 시 고려할 개념—HTTPS와 TLS 종료 프록시(Traefik, Caddy, Nginx 등), Let's Encrypt와 SNI, 시작 시 자동 실행, 장애 후 재시작, 워커 복제와 프로세스별 메모리, 시작 전 단계(DB 마이그레이션), 자원 사용률—과 fastapi 버전 고정 전략을 정리한다.
tags: [deployment, https, tls, workers, replication, versioning]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-c4942803a280a2e51c833734
    resource: repo://docs/en/docs/deployment/concepts.md
  - id: openwiki-source-4ed3f158b6c4f6079e2aec29
    resource: repo://docs/en/docs/deployment/https.md
  - id: openwiki-source-59423393aef62df38afc5cc7
    resource: repo://docs/en/docs/deployment/versions.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 배포 개념, HTTPS, 버전 관리

**배포**란 애플리케이션을 사용자가 이용할 수 있게 만드는 과정이다. 웹 API라면 보통 원격 머신에 올리고, 성능·안정성이 좋은 서버 프로그램으로 실행해 사용자가 끊김 없이 접근하게 하는 것을 말한다. 코드를 계속 바꾸고 개발 서버를 껐다 켜는 **개발** 단계와 대비된다.

배포 방식은 다양하다. 도구를 조합해 직접 서버를 운영하거나, 일부를 대신해 주는 클라우드 서비스(예: FastAPI 팀의 [FastAPI Cloud](https://fastapicloud.com))를 쓸 수 있다. 구체적인 방법은 [수동 배포와 서버 워커](./manual-deployment-and-workers.md), [Docker와 클라우드](./docker-and-cloud.md)를 본다. 이 페이지는 어떤 방법을 쓰든 고려해야 할 **개념**을 정리한다.

## 1. 보안: HTTPS

### 개발자가 알아야 할 HTTPS 핵심

- 서버는 제3자에게서 **인증서를 발급받아야** 하며, 인증서는 **만료**되므로 **갱신**해야 한다.
- 암호화는 HTTP 아래인 **TCP 수준**에서 이뤄진다. TCP는 도메인을 모르고 IP만 안다. 도메인 정보는 HTTP 데이터 안에 있다.
- 따라서 기본적으로 **IP 주소당 인증서 하나**만 가능하지만, TLS 확장 **SNI(Server Name Indication)**를 쓰면 하나의 IP에서 여러 도메인의 인증서를 제공할 수 있다. 이때 공개 IP를 리스닝하는 **단일 컴포넌트**가 모든 인증서를 가지고 있어야 한다.
- 보안 연결이 맺어진 뒤의 통신 프로토콜은 여전히 **HTTP**(내용만 암호화됨)다.

### TLS 종료 프록시

일반적으로 서버에 **하나의 프로그램**이 HTTPS를 전담한다. 암호화된 요청을 받아 복호화한 HTTP 요청을 같은 서버의 실제 앱(FastAPI)에 전달하고, 응답을 다시 암호화해 돌려준다. 이를 **TLS Termination Proxy**라 한다.

| 도구 | 인증서 갱신 |
| --- | --- |
| Traefik | 자동 |
| Caddy | 자동 |
| Nginx | Certbot 같은 외부 컴포넌트 |
| HAProxy | Certbot 같은 외부 컴포넌트 |
| Kubernetes + Ingress Controller(Nginx 등) | cert-manager 같은 외부 컴포넌트 |
| 클라우드 제공자 | 서비스의 일부로 처리 |

### Let's Encrypt

Linux Foundation 프로젝트로, 표준 암호화를 쓰는 **무료 HTTPS 인증서**를 자동으로 발급한다. 수명이 약 3개월로 짧아 오히려 보안에 유리하며, 도메인 검증과 갱신을 자동화할 수 있다.

### 요청 흐름 요약

도메인 구입 → DNS에 공개 IP 설정 → 클라이언트가 TLS 핸드셰이크 시작(SNI로 도메인 전달) → TLS 종료 프록시가 해당 인증서로 암호화 연결 수립 → 요청 복호화 후 앱에 HTTP로 전달 → 앱의 HTTP 응답을 암호화해 반환. 하나의 프록시가 여러 도메인/앱을 처리할 수 있고, 인증서 갱신도 프록시(또는 별도 프로그램)가 담당한다.

### 프록시 전달 헤더

TLS 종료 프록시 뒤의 앱 서버(예: FastAPI CLI가 실행하는 Uvicorn)는 HTTPS를 모르고 평문 HTTP로 통신한다. 프록시가 `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host` 헤더를 붙이지만 앱 서버는 기본적으로 이를 신뢰하지 않는다. FastAPI CLI의 `--forwarded-allow-ips` 옵션으로 신뢰할 IP를 지정하면(프록시에서만 요청을 받는다면 `"*"`), 앱이 자신의 공개 URL·HTTPS 여부·도메인을 알고 리다이렉트를 올바르게 처리한다. 자세한 내용은 [프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md).

## 2. 프로그램과 프로세스

- **프로그램**: 디스크의 코드/파일(예: `python`, `uvicorn`, 앱 코드)
- **프로세스**: 운영체제에서 실행 중인 프로그램 인스턴스. CPU와 메모리를 사용하며, 같은 프로그램을 여러 프로세스로 실행할 수 있다.

## 3. 시작 시 자동 실행

원격 서버에서 터미널로 직접 실행하면 연결이 끊기거나 서버가 재부팅될 때 앱이 멈춘다. 사람 개입 없이 서버 시작 시 앱(예: Uvicorn)을 자동으로 띄우는 **별도 프로그램**을 쓴다(DB 같은 다른 컴포넌트도 함께 관리하는 경우가 많다).

예: Docker, Kubernetes, Docker Compose, Docker Swarm Mode, Systemd, Supervisor, 클라우드 제공자.

## 4. 재시작

- **작은 오류**: 한 요청에서 버그가 나도 FastAPI는 그 요청에 대해 500 오류를 반환하고 다음 요청을 계속 처리한다.
- **큰 오류(크래시)**: 프로세스 자체가 죽으면 같은 앱 코드로는 아무것도 할 수 없으므로, **외부 컴포넌트**가 재시작해야 한다. 보통 시작 시 실행 도구가 재시작도 담당한다(위 목록과 동일).

## 5. 복제: 프로세스와 메모리

- CPU 코어가 여럿이고 단일 프로세스로 감당하기 어렵다면 같은 앱을 여러 프로세스(**워커**)로 실행한다.
- 하나의 IP·포트 조합은 **한 프로세스만** 리스닝할 수 있으므로, 단일 프로세스가 포트를 리스닝하고 워커들에게 통신을 전달해야 한다.
- 프로세스는 보통 **메모리를 공유하지 않는다**. 1 GB 모델을 로드하는 앱을 워커 4개로 실행하면 최소 4 GB RAM이 필요하다. 서버 RAM이 3 GB라면 문제가 생긴다.
- CPU 사용률은 시간에 따라 크게 변하지만 메모리는 대체로 안정적이다.

복제 전략:

- **Uvicorn `--workers`**: 하나의 Uvicorn 프로세스 매니저가 포트를 리스닝하고 여러 워커 프로세스를 띄운다([서버 워커](./manual-deployment-and-workers.md)).
- **Kubernetes 등 분산 컨테이너 시스템**: 클러스터 계층이 포트를 리스닝하고, 컨테이너마다 **Uvicorn 프로세스 하나**를 두어 컨테이너 수로 복제한다([Docker](./docker-and-cloud.md)).
- **클라우드 서비스**: 프로세스나 컨테이너 이미지를 지정하면 서비스가 복제를 처리한다.

## 6. 시작 전 단계

DB 마이그레이션처럼 앱 시작 전에 **한 번만** 실행해야 하는 작업은 **단일 프로세스**에서 실행해야 한다. 워커 여러 개가 병렬로 실행하면 작업이 중복되고, 마이그레이션처럼 민감한 작업은 서로 충돌할 수 있다. 여러 번 실행해도 안전하다면 처리가 쉬워지고, 구성에 따라 시작 전 단계가 아예 필요 없을 수도 있다.

예: Kubernetes의 Init Container, 사전 단계를 실행한 뒤 앱을 시작하는 bash 스크립트(그 스크립트의 시작·재시작·오류 감지 수단은 여전히 필요). 앱 내부의 초기화는 [lifespan](../app-structure/lifespan-events.md)을 쓰되, 워커마다 실행된다는 점에 유의한다.

## 7. 자원 사용률

서버의 CPU 시간과 RAM은 자원이다. 너무 적게 쓰면 돈과 전력을 낭비하고, 100%에 가깝게 쓰면 디스크 스왑(수천 배 느림)이나 크래시가 발생한다. 보통 **크래시 없이 최대한** 활용하는 것이 목표이며(예: 50~90% 수준), `htop` 같은 도구나 모니터링으로 확인한다.

## FastAPI 버전 관리

FastAPI는 많은 운영 환경에서 쓰이고 테스트 커버리지 100%를 유지하지만 여전히 빠르게 발전 중이라 버전이 `0.x.x`다. Semantic Versioning에 따라 `1.0.0` 미만에서는 호환성이 깨지는 변경이 있을 수 있다.

- **PATCH**(마지막 숫자, `0.2.3`의 `3`): 버그 수정·비파괴 변경
- **MINOR**(가운데 숫자, `0.2.3`의 `2`): 파괴적 변경과 새 기능

### 버전 고정

앱에서 잘 동작하는 최신 버전으로 고정한다.

```txt
fastapi[standard]==0.112.0
```

또는 PATCH 업데이트만 허용:

```txt
fastapi[standard]>=0.112.0,<0.113.0
```

`uv`, Poetry, Pipenv 등도 버전을 지정하는 방법을 제공한다. 사용 가능한 버전은 릴리스 노트에서 확인한다.

### 업그레이드

먼저 [테스트](../testing/testing-basics.md)를 작성한 뒤, 새 버전으로 올리고 테스트가 모두 통과하면 그 버전으로 다시 고정한다.

### Starlette와 Pydantic

- `starlette`는 고정하지 **않는다**. FastAPI 버전마다 맞는 Starlette 버전을 사용한다.
- Pydantic은 FastAPI 테스트를 자체 테스트에 포함하므로, 동작하는 범위로 고정하면 된다(예: `pydantic>=2.7.0,<3.0.0`). 이 저장소의 FastAPI는 `pydantic>=2.9.0`을 요구한다([Pydantic v1→v2](../models/pydantic-v1-to-v2.md)).

## 관련 페이지

- [수동 배포와 서버 워커](./manual-deployment-and-workers.md)
- [Docker와 클라우드 배포](./docker-and-cloud.md)
- [프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md)
