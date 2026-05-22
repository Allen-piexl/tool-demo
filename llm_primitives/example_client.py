from __future__ import annotations

import requests

examples = [
    ("http://localhost:8001/invoke", "What is AAPL stock price?"),
    ("http://localhost:8002/invoke", "latest news about climate change"),
    ("http://localhost:8003/invoke", "Search Amazon wireless earbuds"),
]

for url, query in examples:
    print("=", query)
    res = requests.post(url, json={"query": query}, timeout=180)
    print(res.status_code)
    print(res.json())
    print()
