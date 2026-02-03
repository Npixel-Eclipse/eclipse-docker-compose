# AI Workflow Framework

FastAPI, OpenRouter, Slack, LangGraph, Docker 기반의 재사용 가능한 AI 워크플로우 프레임워크입니다.

## 빠른 시작

### 1. 환경 설정

```bash
cd /data4/ai-workflow-framework
cp .env.example .env
# .env 파일에 실제 토큰 입력
```

### 2. Docker로 실행

```bash
docker-compose up -d
```

### 3. 로컬에서 실행 (개발용)

```bash
pip install -e .
python -m src.main
```

## 핵심 모듈

| 모듈 | 설명 |
|------|------|
| `src/core/llm_client.py` | OpenRouter API 클라이언트 |
| `src/core/slack_client.py` | Slack Socket Mode 통합 |
| `src/core/workflow_engine.py` | LangGraph 워크플로우 엔진 |

## 새 워크플로우 만들기

```python
from src.workflows.base import BaseWorkflow, WorkflowState
from src.core.llm_client import LLMClient
from langgraph.graph import END

class MyWorkflow(BaseWorkflow):
    name = "my_workflow"
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
        super().__init__()
    
    def build(self):
        @self.engine.node("process")
        async def process(state):
            # 비즈니스 로직
            return {"output": state["input"].upper()}
        
        self.engine.set_entry_point("process")
        self.engine.add_edge("process", END)
    
    def get_state_schema(self):
        return WorkflowState

# 사용
workflow = MyWorkflow(llm_client)
result = await workflow.run({"input": "hello"})
```

## API 엔드포인트

- `GET /health` - 헬스체크
- `POST /workflow/run` - 워크플로우 실행

## 디렉토리 구조

```
ai-workflow-framework/
├── src/
│   ├── main.py              # FastAPI 앱
│   ├── config.py            # 설정 관리
│   ├── core/                # 핵심 모듈
│   ├── workflows/           # 워크플로우 정의
│   └── api/                 # API 라우트
├── directives/              # 에이전트 SOP
├── docker-compose.yml
└── Dockerfile
```

## 에이전트 참고 사항

`directives/create_workflow.md` 파일에서 새 워크플로우 생성 지침을 확인하세요.
