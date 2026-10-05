# 파일

- [배포 개념, HTTPS, 버전 관리](deployment-concepts-and-https.md) - FastAPI 앱 배포 시 고려할 개념—HTTPS와 TLS 종료 프록시(Traefik, Caddy, Nginx 등), Let's Encrypt와 SNI, 시작 시 자동 실행, 장애 후 재시작, 워커 복제와 프로세스별 메모리, 시작 전 단계(DB 마이그레이션), 자원 사용률—과 fastapi 버전 고정 전략을 정리한다.
- [Docker와 클라우드 배포](docker-and-cloud.md) - FastAPI 앱의 Docker 이미지를 처음부터 만드는 방법(Dockerfile, 레이어 캐시, exec 형식 CMD, --proxy-headers, 단일 파일 앱), 컨테이너 환경에서의 HTTPS·재시작·복제·메모리·시작 전 단계 전략, deprecated된 기본 이미지, fastapi deploy로 FastAPI Cloud에 배포하는 방법과 기타 클라우드를 정리한다.
- [수동 배포와 서버 워커](manual-deployment-and-workers.md) - fastapi run 명령으로 운영 서버를 실행하는 방법, ASGI 서버(Uvicorn, Hypercorn, Daphne, Granian) 선택, uvicorn[standard] 설치와 uvicorn main:app 직접 실행, 운영에서 --reload를 쓰지 말아야 하는 이유, --workers로 다중 워커 프로세스를 띄우는 방법을 설명한다.
