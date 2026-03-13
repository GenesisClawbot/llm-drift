"""
DriftWatch Quickstart — detect LLM behavioral drift in 5 minutes.

Requirements:
    pip install anthropic scikit-learn numpy

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/quickstart.py
"""

import os
import json
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.drift_detector import DriftDetector
except ImportError:
    print("Error: run from the repo root: python examples/quickstart.py")
    sys.exit(1)

# ── 1. Define your critical prompts ──────────────────────────────────────────
PROMPTS = [
    {
        "id": "json-extract",
        "name": "JSON extraction",
        "prompt": 'Extract the name and age from this text and return as JSON: "Alice is 30 years old"',
        "validators": ["json_valid"],
        "category": "json"
    },
    {
        "id": "single-word",
        "name": "Single word classifier",
        "prompt": "Return a single word: what is 2+2? Answer with only the number.",
        "validators": ["exact_match", "length_stable"],
        "category": "instruction"
    },
    {
        "id": "sentiment",
        "name": "Sentiment classification",
        "prompt": "Classify the sentiment of 'This product is terrible' as exactly one word: positive, negative, or neutral.",
        "validators": ["exact_match"],
        "category": "classification"
    }
]

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    detector = DriftDetector(api_key=api_key, provider="anthropic")

    # ── 2. Establish baseline (run once when model behaves correctly) ──────────
    baseline_path = Path("examples/my-baseline.json")
    if not baseline_path.exists():
        print("📸 Running baseline (saving to examples/my-baseline.json)...")
        baseline = detector.run_baseline(PROMPTS)
        baseline_path.write_text(json.dumps(baseline, indent=2))
        print(f"   Baseline saved: {len(baseline['results'])} prompts")
        print("\n✅ Baseline established. Run again to check for drift.\n")
        return

    # ── 3. Check for drift ────────────────────────────────────────────────────
    print("🔍 Checking for drift against baseline...")
    baseline = json.loads(baseline_path.read_text())
    results = detector.run_check(PROMPTS, baseline)

    # ── 4. Print results ──────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"DRIFT CHECK RESULTS  —  {results['timestamp'][:16]}")
    print(f"{'─'*60}")

    for r in results['results']:
        score = r.get('drift_score', 0)
        icon = "🔴" if score > 0.5 else ("🟠" if score > 0.2 else "✅")
        print(f"\n{icon} [{r['id']}] {r['name']}")
        print(f"   Drift score: {score:.3f}")
        if r.get('baseline_output') and r.get('current_output'):
            b = r['baseline_output'][:80].replace('\n', ' ')
            c = r['current_output'][:80].replace('\n', ' ')
            print(f"   Baseline: {b}")
            print(f"   Current:  {c}")
        if r.get('alerts'):
            for alert in r['alerts']:
                print(f"   ⚠ {alert}")

    avg = results.get('summary', {}).get('avg_drift', 0)
    max_d = results.get('summary', {}).get('max_drift', 0)
    alerts = results.get('summary', {}).get('alert_count', 0)
    print(f"\n{'─'*60}")
    print(f"Avg drift: {avg:.3f}  |  Max drift: {max_d:.3f}  |  Alerts: {alerts}")
    print(f"{'─'*60}\n")

    if alerts > 0:
        print("🚨 Drift detected! Your model may have updated silently.")
        print("   → Check https://genesisclawbot.github.io/llm-drift/ for hosted monitoring")
    else:
        print("✅ No significant drift detected.")

if __name__ == "__main__":
    main()
