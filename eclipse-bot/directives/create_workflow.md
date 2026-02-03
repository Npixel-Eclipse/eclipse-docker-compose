# 워크플로우 생성 지침

> AI 에이전트가 새 워크플로우를 개발할 때 참고하는 SOP입니다.

## 개요

이 프레임워크는 LangGraph 기반 워크플로우 엔진을 제공합니다. 새 워크플로우는 `BaseWorkflow`를 상속하여 구현합니다.

## 실행 환경

- **프레임워크 경로**: `/data4/ai-workflow-framework`
- **워크플로우 위치**: `/data4/ai-workflow-framework/src/workflows/`
- **환경 변수**: `/data4/ai-workflow-framework/.env`

## 워크플로우 생성 절차

### 1단계: 상태 스키마 정의

```python
from typing import TypedDict, Optional

class MyState(TypedDict, total=False):
    # 입력
    user_input: str
    
    # 처리 중간 결과
    processed_data: dict
    
    # 출력
    result: str
    error: Optional[str]
```

**체크포인트:**
- [ ] 모든 필드에 타입 힌트 적용
- [ ] Optional 필드는 `total=False` 사용

### 2단계: BaseWorkflow 상속

```python
from src.workflows.base import BaseWorkflow
from langgraph.graph import END

class MyWorkflow(BaseWorkflow):
    name = "my_workflow"
    
    def __init__(self, llm_client=None):
        self.llm = llm_client  # 필요한 의존성 주입
        super().__init__()  # 반드시 마지막에 호출
    
    def build(self):
        # 노드 정의
        pass
    
    def get_state_schema(self):
        return MyState
```

### 3단계: 노드 구현

```python
def build(self):
    @self.engine.node("step_1")
    async def step_1(state: MyState) -> MyState:
        # 상태의 일부만 반환하면 됨 (병합됨)
        return {"processed_data": {"key": "value"}}
    
    @self.engine.node("step_2")
    async def step_2(state: MyState) -> MyState:
        data = state["processed_data"]
        return {"result": str(data)}
```

### 4단계: 그래프 연결

```python
def build(self):
    # ... 노드 정의 ...
    
    # 시작점 설정
    self.engine.set_entry_point("step_1")
    
    # 엣지 연결
    self.engine.add_edge("step_1", "step_2")
    self.engine.add_edge("step_2", END)
```

### 5단계: 조건부 분기 (선택)

```python
def route_decision(state: MyState) -> str:
    if state.get("error"):
        return "error_handler"
    return "next_step"

self.engine.add_conditional_edge(
    "current_node",
    route_decision,
    {
        "error_handler": "error_handler",
        "next_step": "next_step",
    }
)
```

## LLM 사용

```python
from src.core.llm_client import LLMClient, Message

# 채팅
response = await self.llm.chat([
    Message(role="system", content="..."),
    Message(role="user", content="..."),
])
print(response.content)

# 스트리밍
async for chunk in self.llm.chat_stream(messages):
    print(chunk, end="")
```

## Slack 통합

```python
from src.main import get_slack_integration

slack = get_slack_integration()

# 메시지 전송
await slack.send_message(
    channel="C12345678",
    text="Hello!",
    thread_ts="1234567890.123456",  # 스레드 답장용
)
```

## 테스트

```python
# 로컬 테스트
workflow = MyWorkflow(llm_client)
result = await workflow.run({"user_input": "test"})

assert result.success
assert "result" in result.final_state
```

## 체크리스트

신규 워크플로우 생성 시:

- [ ] TypedDict 상태 스키마 정의
- [ ] BaseWorkflow 상속
- [ ] build() 메서드에서 노드와 엣지 정의
- [ ] get_state_schema() 반환 타입 확인
- [ ] 에러 핸들링 노드 추가
- [ ] 로컬 테스트 수행
- [ ] 이 directive 업데이트 (학습한 내용이 있으면)
