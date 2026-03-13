"""
DriftWatch Demo — see real LLM drift detection output (no API key needed).

Uses real drift data collected from Claude-3-Haiku runs (2026-03-12).

Usage:
    python3 examples/demo_mode.py
    
Record for demo GIF:
    asciinema rec demo.cast
    python3 examples/demo_mode.py
    # Ctrl+D to stop recording
    # Upload to asciinema.org or convert: agg demo.cast demo.gif
"""

import time
import sys

def slow_print(text, delay=0.03):
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def pause(ms=500):
    time.sleep(ms / 1000)

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
ORANGE = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
DIM = "\033[2m"

REAL_RESULTS = [
    {
        "id": "inst-01",
        "name": "Instruction following (capitalization)",
        "prompt": 'Return a single word describing this sentiment: "I love this product"',
        "baseline": '"Neutral."',
        "current": '"Neutral"',
        "drift_score": 0.575,
        "category": "instruction",
        "validators": [
            {"name": "exact_match", "passed": False, "detail": "trailing period dropped"},
            {"name": "length_stable", "passed": True, "detail": "length delta: -1 char"},
        ],
        "alert": "Drift score 0.575 exceeds threshold 0.3 — exact-match parsers will BREAK"
    },
    {
        "id": "json-01",
        "name": "JSON extraction (format compliance)",
        "prompt": 'Extract name and score from: "Alice scored 95 points". Return JSON.',
        "baseline": '{"name": "Alice", "score": 95}',
        "current": '{\n  "name": "Alice",\n  "score": 95\n}',
        "drift_score": 0.316,
        "category": "json",
        "validators": [
            {"name": "json_valid", "passed": True, "detail": "valid JSON"},
            {"name": "has_keys:name,score", "passed": True, "detail": "all keys present"},
            {"name": "format_stable", "passed": False, "detail": "whitespace/newline added"},
        ],
        "alert": "Format variance detected — inline JSON became pretty-printed"
    },
    {
        "id": "inst-02",
        "name": "Concise output (verbosity)",
        "prompt": "Summarise this in one sentence: 'The cat sat on the mat and slept.'",
        "baseline": "A cat slept on a mat.",
        "current": "The cat rested comfortably on the mat while sleeping.",
        "drift_score": 0.173,
        "category": "instruction",
        "validators": [
            {"name": "length_stable", "passed": False, "detail": "+5 words (21 → 26% longer)"},
            {"name": "exact_match", "passed": False, "detail": "output changed"},
        ],
        "alert": None
    },
    {
        "id": "json-02",
        "name": "JSON classification (stable)",
        "prompt": 'Classify this review as JSON: {"text": "Great!", "label": "positive/negative/neutral"}',
        "baseline": '{"text": "Great!", "label": "positive"}',
        "current": '{"text": "Great!", "label": "positive"}',
        "drift_score": 0.000,
        "category": "json",
        "validators": [
            {"name": "json_valid", "passed": True, "detail": "valid JSON"},
            {"name": "exact_match", "passed": True, "detail": "identical output"},
        ],
        "alert": None
    },
    {
        "id": "json-03",
        "name": "Code generation (stable)",
        "prompt": "Write a Python function that adds two numbers. Return ONLY the function.",
        "baseline": "def add(a, b):\n    return a + b",
        "current": "def add(a, b):\n    return a + b",
        "drift_score": 0.000,
        "category": "code",
        "validators": [
            {"name": "starts_with:def", "passed": True, "detail": "function format correct"},
            {"name": "no_preamble", "passed": True, "detail": "no preamble detected"},
        ],
        "alert": None
    },
]

def main():
    print()
    slow_print(f"{BOLD}DriftWatch — LLM Behavioural Drift Check{RESET}", delay=0.02)
    slow_print(f"{DIM}Model: claude-3-haiku-20240307 | Baseline: 2026-03-12{RESET}", delay=0.01)
    print()
    pause(300)
    
    slow_print(f"{CYAN}📸 Loading baseline...{RESET}", delay=0.02)
    pause(400)
    slow_print(f"   5 prompts loaded from baseline.json", delay=0.01)
    print()
    pause(200)
    
    slow_print(f"{CYAN}🔍 Running current model against baseline...{RESET}", delay=0.02)
    
    for i, r in enumerate(REAL_RESULTS):
        pause(600)
        print(f"   [{i+1}/{len(REAL_RESULTS)}] {r['id']}... ", end='', flush=True)
        pause(800)
        score = r['drift_score']
        if score > 0.5:
            color = RED
            icon = "🔴"
        elif score > 0.2:
            color = ORANGE
            icon = "🟠"
        else:
            color = GREEN
            icon = "✅"
        print(f"{color}{score:.3f}{RESET} {icon}")
    
    print()
    pause(300)
    
    LINE = "─" * 62
    print(f"{BOLD}{LINE}{RESET}")
    slow_print(f"{BOLD}DRIFT CHECK RESULTS  —  2026-03-12T20:31 UTC{RESET}", delay=0.01)
    print(f"{BOLD}{LINE}{RESET}")
    
    alerts = []
    for r in REAL_RESULTS:
        pause(200)
        score = r['drift_score']
        if score > 0.5:
            color = RED
            icon = "🔴"
        elif score > 0.2:
            color = ORANGE
            icon = "🟠"
        else:
            color = GREEN
            icon = "✅"
        
        print()
        print(f"{icon} {BOLD}[{r['id']}]{RESET} {r['name']}")
        print(f"   Drift score: {color}{BOLD}{score:.3f}{RESET}", end="")
        
        if score > 0.3:
            print(f"  {RED}⚠ ALERT{RESET}")
            if r['alert']:
                alerts.append((r['id'], r['alert']))
        else:
            print()
        
        # Show baseline vs current for interesting cases
        if score > 0.1:
            b = r['baseline'][:60].replace('\n', '↵')
            c = r['current'][:60].replace('\n', '↵')
            print(f"   {DIM}Baseline:{RESET} {b}")
            print(f"   {DIM}Current: {RESET} {c}")
        
        # Validator results
        for v in r['validators']:
            vicon = "  ✅" if v['passed'] else "  ❌"
            vcol = GREEN if v['passed'] else RED
            print(f"   {vicon} {v['name']}: {vcol}{v['detail']}{RESET}")
        
        pause(150)
    
    print()
    print(f"{BOLD}{LINE}{RESET}")
    
    avg = sum(r['drift_score'] for r in REAL_RESULTS) / len(REAL_RESULTS)
    max_d = max(r['drift_score'] for r in REAL_RESULTS)
    alert_count = len(alerts)
    
    print(f"  Avg drift:  {BOLD}{avg:.3f}{RESET}")
    print(f"  Max drift:  {BOLD}{RED if max_d > 0.3 else ''}{max_d:.3f}{RESET}")
    print(f"  Alerts:     {BOLD}{RED if alert_count else GREEN}{alert_count}{RESET}")
    print(f"{BOLD}{LINE}{RESET}")
    
    if alerts:
        print()
        slow_print(f"{RED}{BOLD}🚨 {alert_count} prompt(s) regressed — check your downstream parsers:{RESET}", delay=0.02)
        for aid, amsg in alerts:
            slow_print(f"   [{aid}] {amsg}", delay=0.01)
        print()
        slow_print(f"{CYAN}→ Monitor live: https://genesisclawbot.github.io/llm-drift/app.html{RESET}", delay=0.02)
        slow_print(f"{CYAN}→ GitHub (MIT): https://github.com/GenesisClawbot/llm-drift{RESET}", delay=0.02)
    else:
        print()
        slow_print(f"{GREEN}✅ No significant drift detected. Your prompts are stable.{RESET}", delay=0.02)
    
    print()

if __name__ == "__main__":
    main()
