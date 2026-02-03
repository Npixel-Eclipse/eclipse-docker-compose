# Jenkins Build History Dashboard

Jenkins 빌드 히스토리를 수집하고 시각화하는 웹 대시보드입니다.

## 기능

- **빌드 히스토리 리스트**: 모든 빌드를 한눈에 확인
- **BranchType 필터링**: Main, Daily, Stage, Perf, Onpremperf 별로 필터링
- **파라미터 태그 표시**: 각 빌드에 입력된 파라미터를 태그로 표시
- **통계 대시보드**: 성공률, 평균 빌드 시간, 트렌드 차트
- **빌드 로그 뷰어**: 각 빌드의 콘솔 로그 확인
- **검색 기능**: 빌드 번호, 파라미터로 검색
- **하이브리드 데이터 수집**: 과거 데이터는 DB에서, 최신 데이터는 실시간 갱신

## 기술 스택

### Frontend
- Next.js 14 (App Router)
- TypeScript
- shadcn/ui
- TanStack Query
- Recharts

### Backend
- NestJS
- Prisma ORM
- PostgreSQL
- Cheerio (Web Scraping)

## 시작하기

### 필요 환경
- Node.js 20+
- Docker & Docker Compose
- pnpm (권장)

### 로컬 개발

1. **의존성 설치**
```bash
# Backend
cd backend
pnpm install

# Frontend
cd frontend
pnpm install
```

2. **환경 변수 설정**
```bash
# backend/.env
DATABASE_URL="postgresql://jenkins_user:jenkins_password@localhost:5432/jenkins_db"
JENKINS_URL="http://192.168.121.101:8080"
JENKINS_API_TOKEN="11f21feb9dd222c85c379eb8adefbe7c77"
JENKINS_JOB_PATH="view/Server/job/Build-Server-Docker-All"
PORT=4000

# frontend/.env.local
NEXT_PUBLIC_API_URL="http://localhost:4000"
```

3. **데이터베이스 마이그레이션**
```bash
cd backend
pnpm prisma migrate dev
```

4. **개발 서버 실행**
```bash
# Terminal 1: Backend
cd backend
pnpm start:dev

# Terminal 2: Frontend
cd frontend
pnpm dev
```

### Docker Compose로 실행

```bash
# 빌드 및 실행
docker-compose up --build

# 백그라운드 실행
docker-compose up -d

# 중지
docker-compose down

# 데이터 볼륨까지 삭제
docker-compose down -v
```

접속: http://localhost:3000

## API 엔드포인트

- `GET /api/builds` - 빌드 리스트 (페이지네이션, 필터링)
  - Query params: `page`, `limit`, `branchType`, `status`, `search`
- `GET /api/builds/:id` - 빌드 상세 정보
- `GET /api/builds/:id/logs` - 빌드 콘솔 로그
- `GET /api/stats` - 통계 데이터
  - Query params: `branchType`, `startDate`, `endDate`
- `POST /api/scrape/initial` - 전체 히스토리 초기 수집
- `POST /api/scrape/recent` - 최신 빌드 수집

## 프로젝트 구조

```
dr_jenkins/
├── backend/
│   ├── src/
│   │   ├── jenkins/          # Jenkins 스크래핑 모듈
│   │   ├── builds/           # 빌드 API 모듈
│   │   ├── stats/            # 통계 API 모듈
│   │   ├── database/         # DB 설정
│   │   └── scheduler/        # Cron 작업
│   ├── prisma/
│   │   └── schema.prisma
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # 메인 대시보드
│   │   ├── stats/            # 통계 페이지
│   │   └── api/              # API Routes
│   ├── components/
│   │   ├── ui/               # shadcn/ui
│   │   ├── build-list.tsx
│   │   ├── build-card.tsx
│   │   ├── build-log-modal.tsx
│   │   └── stats-charts.tsx
│   └── Dockerfile
└── docker-compose.yml
```

## 데이터베이스 스키마

```prisma
model Build {
  id           Int         @id
  status       String      // SUCCESS, FAILURE, ABORTED
  duration     Int         // milliseconds
  timestamp    DateTime
  url          String
  parameters   Parameter[]
  logs         String?     @db.Text
  createdAt    DateTime    @default(now())
  updatedAt    DateTime    @updatedAt
}

model Parameter {
  id       Int    @id @default(autoincrement())
  buildId  Int
  name     String
  value    String
  build    Build  @relation(fields: [buildId], references: [id])
}
```

## 스크래핑 전략

1. **초기 수집**: 첫 실행 시 Job ID 1부터 최신까지 모든 빌드 수집 (백그라운드)
2. **주기적 업데이트**: 5분마다 최근 100개 빌드 업데이트
3. **실시간 조회**: 최신 10개는 API 직접 호출로 최신 상태 유지

## 라이선스

MIT
