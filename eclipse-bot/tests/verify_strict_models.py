import os
import requests
import json
from src.config import get_settings

def check_models_strict():
    settings = get_settings()
    key = settings.openrouter_api_key
    if not key:
        print("Error: No OPENROUTER_API_KEY found.")
        return

    print("Querying OpenRouter API (https://openrouter.ai/api/v1/models)...")
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://eclipse-bot.internal"
    }
    
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        
        # Create a lookup dict for O(1) access
        models_map = {m["id"]: m for m in data}
        
        targets = [
            "anthropic/claude-opus-4.6",
            "moonshotai/kimi-k2.5",
            "openai/gpt-5.2-codex"
        ]
        
        print("\n" + "="*60)
        print(f"{'Target Model ID':<30} | {'Status':<10} | {'Context Length'}")
        print("="*60)
        
        for target in targets:
            if target in models_map:
                info = models_map[target]
                ctx = info.get("context_length", "N/A")
                print(f"{target:<30} | {'FOUND':<10} | {ctx}")
            else:
                print(f"{target:<30} | {'MISSING':<10} | -")
                
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"API Request Failed: {e}")

if __name__ == "__main__":
    check_models_strict()
