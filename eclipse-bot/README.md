# Eclipse Bot

OpenRouter, Slack, LangGraph, Docker 기반의 지능형 워크플로우 에이전트입니다.

## 빠른 시작

### 1. 환경 설정

```bash
cd /data4/docker-compose/eclipse-bot
cp .env.example .env
# .env 파일에 실제 토큰 입력
```

### 2. Docker로 실행

```bash
docker-compose up -d --build
```

### 3. 로컬에서 실행 (개발용)

```bash
pip install -e .
python -m src.main
```

## 핵심 모듈

| 모듈 | 설명 |
|------|------|
| `src/core/llm_client.py` | LLM 인터페이스 (OpenRouter) |
| `src/core/slack_client.py` | Slack 통합 및 스트리밍 처리 |
| `src/core/perforce_client.py` | Perforce(P4) 통합 로직 |
| `src/workflows/` | 개별 워크플로우 및 에이전트 도구 |

## 새 워크플로우 만드기

```python
from src.workflows.base import BaseWorkflow
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
            return {"output": state["input"].upper()}
        
        self.engine.set_entry_point("process")
        self.engine.add_edge("process", END)
```

## 디렉토리 구조

```
eclipse-bot/
├── src/
│   ├── main.py              # 에이전트 진입점
│   ├── core/                # 핵심 로직 (Slack, LLM, P4)
│   ├── workflows/           # 워크플로우(도구) 구현체
│   └── api/                 # API 라우트
├── directives/              # 에이전트 행동 지침 (SOP)
├── prompts/                 # LLM 프롬프트 템플릿
├── docker-compose.yml
└── Dockerfile
```

## 에이전트 참고 사항

`directives/create_workflow.md` 파일에서 새 워크플로우 생성 지침을 확인하세요.
