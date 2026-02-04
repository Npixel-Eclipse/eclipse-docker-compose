from src.config import get_settings
from src.agents.utils import get_chat_model
from src.tools.p4_tools import (
    ALL_P4_TOOLS, p4_describe, p4_annotate, p4_print, p4_grep, p4_filelog
)

def get_subagents() -> list[dict]:
    """Return list of specialist subagent definitions.
    
    Each subagent is initialized with a pre-configured Chat model.
    Sub-agents are instructed to respond in KOREAN.
    """
    settings = get_settings()
    default_model = settings.subagent_model
    default_api_key = settings.openrouter_api_key
    
    def create_spec(name: str, desc: str, prompt: str, tools: list):
        model_instance = get_chat_model(default_model, default_api_key)
        
        # Enforce Korean and dynamic review checklist
        system_prompt = f"""{prompt}
        
## 지침 (Core Instructions)
1. **반드시 한국어로 답변하세요.** 모든 리뷰 내용과 요약은 한국어여야 합니다.
2. 고정된 체크리스트만 반복하지 말고, 코드의 실제 변경 맥락을 분석하여 유연하게 리뷰하세요.
3. 'thought:' 또는 'Thinking Process' 등 모델의 내부 추론 과정을 답변 본문에 포함하지 마세요. (본문은 리포트 내용만 포함)
4. 문제가 없다면 '특이사항 없음'이라고 짧게 언급하고, 문제나 개선 방안이 있다면 구체적인 코드 예시와 함께 설명하세요.
"""
        return {
            "name": name,
            "description": desc,
            "model": model_instance,
            "system_prompt": system_prompt,
            "tools": tools,
        }

    return [
        create_spec(
            "kotlin-expert", 
            "Kotlin/Spring 기반 백엔드 코드 리뷰",
            "당신은 Kotlin 백엔드 Agent입니다. Kafka 컨슈머에서의 blocking 호출, 트랜잭션 전파 문제, Kotlin 문법 활용 오용 등을 중점적으로 체크하세요.",
            [p4_describe, p4_annotate, p4_print]
        ),
        create_spec(
            "jpa-expert",
            "JPA/DB 접근 계층 리뷰",
            "당신은 JPA 및 데이터베이스 Agent입니다. N+1 문제, 지연 로딩 설정 오류, 인덱스를 타지 않는 쿼리, 대량 데이터 처리 성능 등을 분석하세요.",
            [p4_describe, p4_annotate, p4_print]
        ),
        create_spec(
            "kafka-expert",
            "Kafka 메시징 시스템 리뷰",
            "당신은 Kafka Agent입니다. Partition Key 선정의 적절성, 재시도 및 DLQ 전략, 메시지 순서 보장 여부 등을 검토하세요.",
            [p4_describe, p4_print]
        ),
        create_spec(
            "rust-expert",
            "Rust 시스템 및 비즈니스 로직 리뷰",
            "당신은 Rust Agent입니다. unsafe 블록의 필요성, unwrap/expect 남용으로 인한 패닉 가능성, async task 내의 blocking 호출(std sync primitives 등)을 체크하세요.",
            [p4_describe, p4_annotate, p4_print]
        ),
        create_spec(
            "ecs-expert",
            "Shipyard ECS 게임 엔진 로직 리뷰",
            "당신은 Shipyard ECS Agent입니다. EntityId 관리, System 간 의존성, View/ViewMut 선택 오류로 인한 데드락이나 성능 저하를 분석하세요.",
            [p4_describe, p4_print]
        ),
        create_spec(
            "yaml-expert",
            "리소스 및 설정(YAML) 파일 리뷰",
            "당신은 리소스 설정 Agent입니다. YAML 파일 내의 ID 중복, 시스템 간 참조 무결성, 오타로 인한 런타임 에러 가능성을 검토하세요.",
            [p4_describe, p4_print]
        ),
        create_spec(
            "proto-expert",
            "gRPC/Protobuf 변경 리뷰",
            "당신은 Protocol Buffer Agent입니다. 하위 호환성 파괴 여부(Breaking Changes), 필드 번호 중복, enum 관리 전략 등을 체크하세요.",
            [p4_describe, p4_print]
        ),
        create_spec(
            "security-expert",
            "보안 취약점 및 민감 정보 노출 리뷰",
            "당신은 보안 Agent입니다. 하드코딩된 Secret(API Key, Password), 입력값 검증 미흡, 부적절한 권한 체크 등을 철저히 찾으세요.",
            ALL_P4_TOOLS
        ),
        create_spec(
            "architecture-expert",
            "시스템 설계 및 의존성 규칙 리뷰",
            "당신은 아키텍처 Agent입니다. 레이어 간 침범, 마이크로서비스 간 순환 참조, 도메인 모델 오용 등을 검토하여 시스템의 결합도를 낮추는 방향으로 제언하세요.",
            ALL_P4_TOOLS
        ),
        create_spec(
            "game-logic-expert",
            "핵심 게임 메커니즘 및 상태 머신 리뷰",
            "당신은 게임 로직 Agent입니다. 상태 머신의 전이 규칙 준수, 게임 재화/밸런스 수식의 정밀도, 엣지 케이스에서의 상태 불일치 가능성을 분석하세요.",
            [p4_describe, p4_print, p4_annotate]
        ),
    ]
