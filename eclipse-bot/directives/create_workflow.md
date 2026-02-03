# 워크플로우 생성 지침

> AI 에이전트가 새 워크플로우를 개발할 때 참고하는 문서입니다.

이 지침은 Eclipse Bot의 워크플로우/도구 시스템을 기반으로 합니다. 모든 기능(도구 및 워크플로우)은 `src.core.registry.BaseWorkflow`를 상속하여 구현합니다.

## 실행 환경

- **프로젝트 경로**: `/data4/docker-compose/eclipse-bot`
- **도구 위치**: `./src/tools/` (원자적 기능)
- **워크플로우 위치**: `./src/workflows/` (복합 시나리오)

## 생성 절차

### 1단계: BaseWorkflow 상속 및 클래스 정의

```python
from typing import Any
from src.core.registry import BaseWorkflow

class MyNewTool(BaseWorkflow):
    """도구에 대한 설명을 작성합니다."""
    
    # 1. 고유 이름과 설명 정의
    name = "my_new_tool"
    description = "이 도구가 무엇을 하는지 구체적으로 기술합니다."
    
    # 2. 파라미터 스키마 정의 (JSON Schema)
    parameters = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "파라미터 설명"
            },
            "option": {
                "type": "boolean", 
                "description": "옵션 설명"
            }
        },
        "required": ["param1"]
    }
    
    # 3. (선택) 이 워크플로우 내에서 사용할 수 있는 하위 도구 제한
    # allowed_tools = ["read_file", "p4_sync"] 
    # None이면 모든 도구 사용 가능
    
    # 4. 실행 로직 구현
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        param1 = input_data.get("param1")
        
        try:
            # 비즈니스 로직 수행
            result = f"Processed {param1}"
            
            return {
                "result": result,
                "status": "success"
            }
        except Exception as e:
            return {"error": str(e)}
```

### 2단계: 레지스트리 등록

`src/tools/__init__.py` 또는 `src/workflows/__init__.py`에 등록 코드를 추가해야 합니다.

```python
# src/tools/__init__.py 예시

from .my_tool import MyNewTool

def register_all_tools():
    from src.core.registry import registry
    
    # ... 기존 도구들 ...
    registry.register(MyNewTool())
```

### 3단계: P4 연동 시

`src.core.PerforceClient`를 사용합니다.

```python
from src.core import PerforceClient

async def execute(self, input_data: dict) -> dict:
    p4 = PerforceClient()
    # 비동기 실행을 위해 loop.run_in_executor 또는 to_thread 사용 권장
    output = await asyncio.to_thread(p4._run, "files", "//...")
```

## 체크리스트

신규 도구/워크플로우 생성 시:

- [ ] `BaseWorkflow` 상속 확인
- [ ] `name`, `description` 명확하게 작성 (LLM이 이를 보고 호출함)
- [ ] `parameters` 스키마 정확히 정의
- [ ] `execute` 메서드 구현 및 예외 처리
- [ ] `__init__.py`에 등록 루틴 추가
- [ ] 로컬 테스트 (봇 재시작 후 로그 확인)
