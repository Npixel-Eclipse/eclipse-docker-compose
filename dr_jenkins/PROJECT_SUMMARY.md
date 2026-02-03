# Jenkins Build History Dashboard - Project Summary

## 프로젝트 개요

Jenkins 빌드 히스토리를 수집하고 시각화하는 풀스택 웹 애플리케이션입니다.

**대상 Jenkins Job**: http://192.168.121.101:8080/view/Server/job/Build-Server-Docker-All/

## 주요 기능

### ✅ 구현된 기능

1. **빌드 히스토리 수집**
   - 하이브리드 방식: 과거 데이터는 DB에 캐싱, 최신 데이터는 주기적 갱신
   - 전체 히스토리 초기 수집 (Job ID 1 ~ 최신)
   - 5분마다 최근 100개 빌드 자동 갱신
   - Jenkins API Token 인증 지원

2. **빌드 리스트 UI**
   - 카드 형식으로 빌드 표시
   - BranchType 필터링 (Main, Daily, Stage, Perf, Onpremperf)
   - 상태 필터링 (SUCCESS, FAILURE, ABORTED, IN_PROGRESS)
   - 검색 기능 (빌드 번호, 파라미터 값)
   - 페이지네이션 (페이지당 20개)
   - 파라미터 태그 표시

3. **통계 대시보드**
   - 전체 통계 카드 (총 빌드 수, 성공률, 실패율, 평균 빌드 시간)
   - 상태별 분포 파이 차트
   - BranchType별 성공률 바 차트
   - 일별 빌드 추이 라인 차트 (최근 30일)
   - 빌드 시간 트렌드 라인 차트 (최근 100개)
   - BranchType별 상세 통계 테이블

4. **빌드 로그 뷰어**
   - 모달 방식으로 빌드 상세 정보 표시
   - 빌드 파라미터 태그
   - 콘솔 로그 전체 내용 (터미널 스타일)
   - Jenkins URL 링크

5. **자동화**
   - Cron 스케줄러로 5분마다 자동 갱신
   - 수동 스크래핑 버튼 (전체 히스토리 / 최근 빌드)
   - 백그라운드 작업 처리

## 기술 스택

### Backend
- **Framework**: NestJS (TypeScript)
- **Database**: PostgreSQL 16
- **ORM**: Prisma
- **Scraping**: Axios + Cheerio
- **Scheduling**: @nestjs/schedule
- **API**: RESTful

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **UI Library**: shadcn/ui (Radix UI + Tailwind CSS)
- **State Management**: TanStack Query (React Query)
- **Charts**: Recharts
- **Styling**: Tailwind CSS

### DevOps
- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **Database**: PostgreSQL (Docker)

## 프로젝트 구조

```
dr_jenkins/
├── backend/                    # NestJS Backend
│   ├── src/
│   │   ├── main.ts            # Entry point
│   │   ├── app.module.ts      # Root module
│   │   ├── database/          # Prisma service
│   │   ├── jenkins/           # Jenkins scraping service
│   │   │   ├── jenkins.service.ts      # 스크래핑 로직
│   │   │   ├── jenkins.scheduler.ts    # Cron 작업
│   │   │   └── jenkins.controller.ts   # Scrape API
│   │   ├── builds/            # Builds API module
│   │   │   ├── builds.service.ts       # 빌드 조회 로직
│   │   │   └── builds.controller.ts    # Builds API
│   │   └── stats/             # Statistics API module
│   │       ├── stats.service.ts        # 통계 계산 로직
│   │       └── stats.controller.ts     # Stats API
│   ├── prisma/
│   │   └── schema.prisma      # DB schema
│   ├── Dockerfile
│   └── package.json
│
├── frontend/                   # Next.js Frontend
│   ├── app/
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Main page
│   │   ├── providers.tsx      # React Query provider
│   │   └── globals.css        # Global styles
│   ├── components/
│   │   ├── ui/                # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── dialog.tsx
│   │   │   └── tabs.tsx
│   │   ├── build-card.tsx     # 빌드 카드 컴포넌트
│   │   ├── build-list.tsx     # 빌드 리스트 (필터링 포함)
│   │   ├── build-log-modal.tsx # 로그 뷰어 모달
│   │   └── stats-dashboard.tsx # 통계 대시보드
│   ├── lib/
│   │   ├── api.ts             # API 클라이언트
│   │   └── utils.ts           # Utility functions
│   ├── Dockerfile
│   └── package.json
│
├── docker-compose.yml          # Docker Compose 설정
├── README.md                   # 프로젝트 개요
├── SETUP.md                    # 상세 설정 가이드
└── .gitignore
```

## 데이터베이스 스키마

```prisma
model Build {
  id         Int         @id                   // Build ID
  status     String                            // SUCCESS, FAILURE, ABORTED, IN_PROGRESS
  duration   Int?                              // Build duration (ms)
  timestamp  DateTime                          // Build timestamp
  url        String                            // Jenkins build URL
  parameters Parameter[]                       // Build parameters
  logs       String?     @db.Text             // Console logs
  createdAt  DateTime    @default(now())
  updatedAt  DateTime    @updatedAt
}

model Parameter {
  id      Int    @id @default(autoincrement())
  buildId Int
  name    String                              // Parameter name (e.g., BranchType)
  value   String                              // Parameter value (e.g., Main)
  build   Build  @relation(...)
}
```

## API 엔드포인트

### Builds API
- `GET /api/builds` - 빌드 리스트 조회 (필터링, 페이지네이션)
- `GET /api/builds/:id` - 빌드 상세 조회
- `GET /api/builds/:id/logs` - 빌드 로그 조회
- `GET /api/builds/stats` - 기본 통계

### Stats API
- `GET /api/stats/overall` - 전체 통계
- `GET /api/stats/branch-types` - BranchType별 통계
- `GET /api/stats/daily` - 일별 통계
- `GET /api/stats/duration-trend` - 빌드 시간 트렌드

### Scrape API
- `POST /api/scrape/initial` - 전체 히스토리 스크래핑 (백그라운드)
- `POST /api/scrape/recent` - 최근 100개 스크래핑

## 실행 방법

### Quick Start (Docker Compose)

```bash
cd dr_jenkins
docker-compose up --build
```

접속: http://localhost:3000

### Local Development

```bash
# PostgreSQL 실행
docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_USER=jenkins_user \
  -e POSTGRES_PASSWORD=jenkins_password \
  -e POSTGRES_DB=jenkins_db postgres:16-alpine

# Backend
cd backend
pnpm install
pnpm prisma migrate dev
pnpm start:dev

# Frontend (새 터미널)
cd frontend
pnpm install
pnpm dev
```

## 환경 변수

### Backend
```env
DATABASE_URL=postgresql://jenkins_user:jenkins_password@localhost:5432/jenkins_db
JENKINS_URL=http://192.168.121.101:8080
JENKINS_API_TOKEN=11f21feb9dd222c85c379eb8adefbe7c77
JENKINS_JOB_PATH=view/Server/job/Build-Server-Docker-All
PORT=4000
```

### Frontend
```env
NEXT_PUBLIC_API_URL=http://localhost:4000
```

## 스크래핑 전략

1. **초기 수집**: 첫 실행 시 Job ID 1부터 최신까지 모든 빌드 수집
   - 백그라운드 작업으로 처리
   - 10개마다 진행률 로그 출력
   - 빌드당 100ms 딜레이 (Jenkins 부하 방지)

2. **주기적 갱신**: 5분마다 최근 100개 빌드 업데이트
   - NestJS Cron 스케줄러 사용
   - 새로운 빌드 자동 감지 및 추가
   - 진행 중인 빌드 상태 업데이트

3. **수동 스크래핑**: UI에서 버튼 클릭으로 수동 트리거
   - "Scrape All History": 전체 히스토리 재수집
   - "Refresh Recent": 최근 100개만 즉시 갱신

## 성능 최적화

- **DB 인덱싱**: Build.status, Build.timestamp, Parameter.name, Parameter.value
- **Pagination**: 페이지당 20개로 제한
- **React Query Caching**: 1분 캐시 TTL
- **Lazy Loading**: 빌드 로그는 모달 오픈 시에만 로드
- **Hybrid Data Fetching**: 과거 데이터는 DB, 최신 데이터는 주기적 갱신

## 향후 개선 사항 (Optional)

- [ ] WebSocket 실시간 업데이트
- [ ] 빌드 비교 기능
- [ ] CSV/JSON 내보내기
- [ ] 알림 설정 (빌드 실패 시)
- [ ] 더 많은 차트 (주간/월간 트렌드)
- [ ] 사용자 인증 (선택적)
- [ ] 다크 모드
- [ ] 빌드 재실행 기능

## 라이선스

MIT

---

**개발 완료일**: 2025-11-10
**개발자**: Claude Code
**문의**: 이슈 트래커 참조
