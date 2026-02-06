
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append("/app")

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Mock the model registry to return predictable limits
with patch("src.agents.factory.get_context_window", return_value=128000):
    from src.agents.factory import create_agent
    from src.core.compactor import AutoCompactor

async def test_auto_compact():
    print("🧪 Testing Auto Compact Logic...")

    # 1. Setup Mock Model
    mock_model = MagicMock()
    # Mock token counter: simple char/4 approx for speed in test
    mock_model.get_num_tokens_from_messages.side_effect = lambda msgs: sum(len(m.content) for m in msgs) // 4
    # Mock summary response
    mock_model.invoke.return_value = AIMessage(content="[Summary] User discussed architecture. Plan approved.")

    # 2. Configure Compactor
    # Limit = 1000 tokens for testing
    compactor = AutoCompactor(model=mock_model, max_tokens=1000, recent_messages_buffer=2)

    # 3. Create Large History
    # System (Keep)
    # Middle (Summarize) -> 5000 chars (~1250 tokens) -> Exceeds 1000
    # Recent (Keep)
    history = [
        SystemMessage(content="You are Eclipse Bot."),
        HumanMessage(content="Old message 1 " * 200),
        AIMessage(content="Old response 1 " * 200),
        HumanMessage(content="Recent message"),
        AIMessage(content="Recent response")
    ]
    
    current_tokens = sum(len(m.content) for m in history) // 4
    print(f"Original Tokens: {current_tokens}")

    # 4. Invoke Compaction
    compacted = compactor.invoke(history)
    
    new_tokens = sum(len(m.content) for m in compacted) // 4
    print(f"Compacted Tokens: {new_tokens}")

    # 5. Verify Structure
    # Should be: [System, Summary, Recent, Recent]
    assert len(compacted) == 4, f"Expected 4 messages, got {len(compacted)}"
    assert isinstance(compacted[0], SystemMessage)
    assert "PREVIOUS CONVERSATION SUMMARY" in compacted[1].content
    assert compacted[-1].content == "Recent response"
    
    print("✅ Auto Compact Logic Verified!")

if __name__ == "__main__":
    asyncio.run(test_auto_compact())
