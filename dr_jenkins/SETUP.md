# Jenkins Dashboard Setup Guide

## Quick Start with Docker Compose (Recommended)

가장 빠르고 간단한 방법입니다.

### 1. Docker Compose로 실행

```bash
cd D:\Work\Eclipse_Studio\Source\tools\dr_jenkins

# 빌드 및 실행
docker-compose up --build

# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

### 2. 접속

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:4000
- **PostgreSQL**: localhost:5432

### 3. 초기 데이터 수집

웹 브라우저에서 http://localhost:3000 접속 후:
1. "Scrape All History" 버튼 클릭 (전체 히스토리 수집 - 시간 소요)
2. 또는 "Refresh Recent" 버튼 클릭 (최근 100개만 빠르게 수집)

---

## Local Development Setup

개발을 위해 로컬에서 실행하는 방법입니다.

### Prerequisites

- Node.js 20+
- pnpm (권장) 또는 npm
- Docker (PostgreSQL용)

### 1. PostgreSQL 실행

```bash
# Docker로 PostgreSQL만 실행
docker run -d \
  --name jenkins-dashboard-postgres \
  -e POSTGRES_USER=jenkins_user \
  -e POSTGRES_PASSWORD=jenkins_password \
  -e POSTGRES_DB=jenkins_db \
  -p 5432:5432 \
  postgres:16-alpine
```

### 2. Backend 설정

```bash
cd backend

# 의존성 설치
pnpm install

# 환경 변수 설정
cp .env.example .env
# .env 파일 내용 확인/수정

# Prisma 설정
pnpm prisma generate
pnpm prisma migrate dev

# 개발 서버 실행
pnpm start:dev
```

Backend는 http://localhost:4000 에서 실행됩니다.

### 3. Frontend 설정

```bash
cd frontend

# 의존성 설치
pnpm install

# 환경 변수 설정
cp .env.local.example .env.local

# 개발 서버 실행
pnpm dev
```

Frontend는 http://localhost:3000 에서 실행됩니다.

---

## 환경 변수 설정

### Backend (.env)

```env
DATABASE_URL="postgresql://jenkins_user:jenkins_password@localhost:5432/jenkins_db"
JENKINS_URL="http://192.168.121.101:8080"
JENKINS_API_TOKEN="11f21feb9dd222c85c379eb8adefbe7c77"
JENKINS_JOB_PATH="view/Server/job/Build-Server-Docker-All"
PORT=4000
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:4000
```

---

## 주요 기능

### 1. 빌드 리스트
- 모든 Jenkins 빌드를 리스트 형식으로 표시
- 페이지네이션 지원 (페이지당 20개)
- BranchType, Status 필터링
- 빌드 번호/파라미터 검색

### 2. 통계 대시보드
- 전체 빌드 통계 (총 빌드 수, 성공률, 실패율, 평균 시간)
- 상태별 분포 (Success/Failure/Aborted) 파이 차트
- BranchType별 성공률 바 차트
- 일별 빌드 추이 (최근 30일)
- 빌드 시간 트렌드 (최근 100개)
- BranchType별 상세 테이블

### 3. 빌드 로그 뷰어
- 각 빌드 카드 클릭 시 모달 오픈
- 빌드 상세 정보 (상태, 시간, 파라미터)
- 콘솔 로그 전체 내용 표시

### 4. 자동 스크래핑
- 5분마다 최신 100개 빌드 자동 업데이트
- 수동 스크래핑 버튼 제공

---

## API 엔드포인트

### Builds

```bash
# 빌드 리스트 조회
GET /api/builds?page=1&limit=20&branchType=Main&status=SUCCESS&search=keyword

# 빌드 상세 조회
GET /api/builds/:id

# 빌드 로그 조회
GET /api/builds/:id/logs

# 빌드 통계
GET /api/builds/stats
```

### Stats

```bash
# 전체 통계
GET /api/stats/overall?branchType=Main&startDate=2024-01-01&endDate=2024-12-31

# BranchType별 통계
GET /api/stats/branch-types

# 일별 통계
GET /api/stats/daily?days=30

# 빌드 시간 트렌드
GET /api/stats/duration-trend?limit=100
```

### Scraping

```bash
# 전체 히스토리 스크래핑 (백그라운드)
POST /api/scrape/initial

# 최근 빌드 스크래핑
POST /api/scrape/recent
```

---

## 데이터베이스 관리

### Prisma Studio 실행

```bash
cd backend
pnpm prisma studio
```

http://localhost:5555 에서 데이터베이스 GUI 확인 가능

### 마이그레이션

```bash
# 새 마이그레이션 생성
pnpm prisma migrate dev --name migration_name

# 프로덕션 마이그레이션 적용
pnpm prisma migrate deploy

# 데이터베이스 리셋 (주의!)
pnpm prisma migrate reset
```

---

## 트러블슈팅

### Backend가 시작되지 않을 때

1. PostgreSQL 연결 확인
```bash
psql -h localhost -U jenkins_user -d jenkins_db
```

2. Prisma Client 재생성
```bash
cd backend
pnpm prisma generate
```

### Frontend 빌드 오류

1. Node modules 재설치
```bash
cd frontend
rm -rf node_modules .next
pnpm install
```

### Jenkins 연결 실패

1. Jenkins URL 접근 가능한지 확인
```bash
curl http://192.168.121.101:8080/view/Server/job/Build-Server-Docker-All/api/json
```

2. API Token이 유효한지 확인

### 스크래핑이 느릴 때

- 전체 히스토리 스크래핑은 빌드 개수에 따라 시간이 오래 걸립니다
- 초기 수집 후에는 자동 스케줄러가 최신 데이터만 업데이트합니다
- Backend 로그를 확인하여 진행 상황 모니터링:
```bash
docker-compose logs -f backend
```

---

## 프로덕션 배포

### Docker Compose 사용

```bash
# .env 파일 설정 후
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 재시작
docker-compose restart
```

### 개별 빌드 및 실행

```bash
# Backend
cd backend
docker build -t jenkins-dashboard-backend .
docker run -d -p 4000:4000 --env-file .env jenkins-dashboard-backend

# Frontend
cd frontend
docker build -t jenkins-dashboard-frontend .
docker run -d -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://localhost:4000 jenkins-dashboard-frontend
```

---

## 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.
