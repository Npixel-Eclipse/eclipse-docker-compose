
import re

patterns = [
    r"(?:code\s*review|리뷰).*(?:cl|change)?\s*(\d+)|(?:cl|change)\s*(\d+).*(?:code\s*review|리뷰)|(\d+)\s*(?:code\s*review|리뷰|해줘)"
]

inputs = [
    "377 코드리뷰 해줘",
    "377 리뷰",
    "리뷰 377",
    "CL 377 리뷰",
    "코드리뷰 377 해줘"
]

for p in patterns:
    print(f"Pattern: {p}")
    for text in inputs:
        match = re.search(p, text, re.IGNORECASE)
        print(f"  '{text}': {'MATCH' if match else 'NO MATCH'}")
        if match:
             print(f"    Groups: {match.groups()}")
