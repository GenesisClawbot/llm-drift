#!/usr/bin/env python3
"""
LLM Drift Detector — Core Engine
Runs test prompts against LLM APIs, compares to baseline, calculates drift scores.

Usage:
  python drift_detector.py --run baseline     # Establish baseline
  python drift_detector.py --run check        # Check for drift
  python drift_detector.py --run demo         # Run demo with simulated drift
"""

import os
import sys
import json
import re
import time
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Try to import anthropic, graceful fallback
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

BASELINE_FILE = DATA_DIR / "baseline.json"
RESULTS_FILE  = DATA_DIR / "results.json"
HISTORY_FILE  = DATA_DIR / "history.json"


# ── Validators ────────────────────────────────────────────────────────────────

def validate(response: str, validators: list[str]) -> dict:
    """Run all validators against a response. Returns pass/fail per validator."""
    results = {}
    text = response.strip()

    for v in validators:
        if v == "is_valid_json":
            try:
                json.loads(text)
                results[v] = True
            except json.JSONDecodeError:
                results[v] = False

        elif v == "is_json_array":
            try:
                parsed = json.loads(text)
                results[v] = isinstance(parsed, list)
            except:
                results[v] = False

        elif v.startswith("has_keys:"):
            keys = v.split(":")[1].split(",")
            try:
                parsed = json.loads(text)
                results[v] = all(k in str(parsed) for k in keys)
            except:
                results[v] = False

        elif v == "single_word":
            results[v] = len(text.split()) == 1

        elif v.startswith("word_in:"):
            options = v.split(":")[1].split(",")
            results[v] = text.strip().lower() in [o.lower() for o in options]

        elif v.startswith("max_words:"):
            limit = int(v.split(":")[1])
            results[v] = len(text.split()) <= limit

        elif v.startswith("max_sentences:"):
            limit = int(v.split(":")[1])
            results[v] = len(re.split(r'[.!?]+', text)) <= limit + 1

        elif v.startswith("response_length_min:"):
            limit = int(v.split(":")[1])
            results[v] = len(text) >= limit

        elif v.startswith("response_length_max:") or v.startswith("short_response:"):
            limit = int(v.split(":")[1])
            results[v] = len(text) <= limit

        elif v == "is_number":
            try:
                float(text.strip())
                results[v] = True
            except:
                results[v] = False

        elif v.startswith("number_in_range:"):
            parts = v.split(":")[1].split(",")
            lo, hi = float(parts[0]), float(parts[1])
            try:
                n = float(text.strip())
                results[v] = lo <= n <= hi
            except:
                results[v] = False

        elif v.startswith("contains:"):
            needle = v.split(":", 1)[1]
            results[v] = needle.lower() in text.lower()

        elif v == "no_refusal":
            refusal_signals = ["i can't", "i cannot", "i'm unable", "i won't",
                               "i apologize", "i'm sorry but", "not able to"]
            results[v] = not any(s in text.lower() for s in refusal_signals)

        elif v == "starts_with_number":
            results[v] = bool(re.match(r'^\s*\d', text))

        elif v == "contains_three_items":
            results[v] = len(re.findall(r'^\s*\d\.', text, re.MULTILINE)) >= 3

        elif v == "no_english_explanation":
            english_signals = ["here is", "here's", "the translation", "in french",
                               "certainly", "of course", "translation:"]
            results[v] = not any(s in text.lower() for s in english_signals)

        elif v == "no_prose_before_code":
            first_line = text.split('\n')[0].strip()
            results[v] = first_line.startswith(('def ', 'class ', 'import ', 'from ',
                                                 'SELECT', 'WITH ', '#', '```'))

        elif v.startswith("matches_pattern:"):
            pattern = v.split(":", 1)[1]
            results[v] = bool(re.match(pattern, text))

        else:
            results[v] = None  # Unknown validator

    return results


# ── Scoring ───────────────────────────────────────────────────────────────────

def compute_drift_score(baseline_resp: str, current_resp: str,
                        baseline_vals: dict, current_vals: dict) -> dict:
    """Compute a composite drift score (0.0 = identical, 1.0 = completely different)."""
    
    scores = {}

    # 1. Validator compliance score
    if baseline_vals and current_vals:
        baseline_pass = sum(1 for v in baseline_vals.values() if v) / max(len(baseline_vals), 1)
        current_pass  = sum(1 for v in current_vals.values()  if v) / max(len(current_vals),  1)
        val_drift = abs(baseline_pass - current_pass)
        scores["validator_drift"] = round(val_drift, 3)
        
        # Check for any validator that PASSED in baseline but FAILS now
        regressions = []
        for key, was_pass in baseline_vals.items():
            if was_pass and key in current_vals and not current_vals[key]:
                regressions.append(key)
        scores["regressions"] = regressions
    else:
        scores["validator_drift"] = 0.0
        scores["regressions"] = []

    # 2. Length drift
    bl_len = len(baseline_resp.strip())
    cu_len = len(current_resp.strip())
    if bl_len > 0:
        len_ratio = abs(bl_len - cu_len) / bl_len
        scores["length_drift"] = round(min(len_ratio, 1.0), 3)
    else:
        scores["length_drift"] = 0.0

    # 3. Exact match
    scores["exact_match"] = baseline_resp.strip() == current_resp.strip()

    # 4. Word overlap (Jaccard similarity on words)
    bl_words = set(baseline_resp.lower().split())
    cu_words = set(current_resp.lower().split())
    if bl_words | cu_words:
        overlap = len(bl_words & cu_words) / len(bl_words | cu_words)
        scores["word_similarity"] = round(overlap, 3)
    else:
        scores["word_similarity"] = 1.0

    # 5. Overall drift score (0 = no drift, 1 = max drift)
    val_weight = 0.5
    len_weight = 0.2
    word_weight = 0.3
    
    overall = (
        scores["validator_drift"] * val_weight +
        scores["length_drift"]   * len_weight +
        (1 - scores["word_similarity"]) * word_weight
    )
    scores["overall_drift"] = round(overall, 3)
    
    # 6. Alert level
    if scores["regressions"]:
        scores["alert_level"] = "critical"   # Was passing, now failing
    elif overall >= 0.6:
        scores["alert_level"] = "high"
    elif overall >= 0.3:
        scores["alert_level"] = "medium"
    elif overall >= 0.1:
        scores["alert_level"] = "low"
    else:
        scores["alert_level"] = "none"

    return scores


# ── LLM Caller ───────────────────────────────────────────────────────────────

def call_llm(prompt: str, model: str = "claude-3-haiku-20240307", max_tokens: int = 512) -> dict:
    """Call the LLM and return response + metadata."""
    if not HAS_ANTHROPIC:
        return {"error": "anthropic package not installed", "response": "", "latency_ms": 0}
    
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set", "response": "", "latency_ms": 0}

    client = anthropic.Anthropic(api_key=api_key)
    
    start = time.time()
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        latency = round((time.time() - start) * 1000)
        response = msg.content[0].text if msg.content else ""
        return {
            "response": response,
            "latency_ms": latency,
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
            "model": msg.model,
            "stop_reason": msg.stop_reason,
        }
    except Exception as e:
        return {"error": str(e), "response": "", "latency_ms": 0}


# ── Main Runs ─────────────────────────────────────────────────────────────────

def run_baseline(model: str, prompts: list) -> dict:
    """Establish baseline by running all prompts and storing responses."""
    from test_suite import TEST_PROMPTS
    target_prompts = prompts or TEST_PROMPTS
    
    print(f"\n🔧 Running baseline with model: {model}")
    print(f"   Prompts: {len(target_prompts)}")
    
    baseline = {
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompts": {}
    }
    
    for i, p in enumerate(target_prompts):
        print(f"  [{i+1}/{len(target_prompts)}] {p['id']}: {p['name'][:45]}...", end=" ")
        result = call_llm(p["prompt"], model=model)
        
        if "error" in result and result["error"]:
            print(f"ERROR: {result['error']}")
            continue
        
        val_results = validate(result["response"], p.get("validators", []))
        pass_count = sum(1 for v in val_results.values() if v)
        total = len(val_results)
        print(f"✓ ({pass_count}/{total} validators pass, {result['latency_ms']}ms)")
        
        baseline["prompts"][p["id"]] = {
            "prompt_id": p["id"],
            "category": p["category"],
            "name": p["name"],
            "response": result["response"],
            "validators": val_results,
            "latency_ms": result["latency_ms"],
            "tokens": result.get("output_tokens", 0),
        }
        time.sleep(0.5)  # Rate limit
    
    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)
    
    print(f"\n✅ Baseline saved to {BASELINE_FILE}")
    return baseline


def run_check(model: str, prompts: list) -> dict:
    """Run prompts and compare to baseline. Generate drift report."""
    from test_suite import TEST_PROMPTS
    target_prompts = prompts or TEST_PROMPTS
    
    if not BASELINE_FILE.exists():
        print("❌ No baseline found. Run with --run baseline first.")
        sys.exit(1)
    
    with open(BASELINE_FILE) as f:
        baseline = json.load(f)
    
    print(f"\n🔍 Running drift check with model: {model}")
    print(f"   Baseline from: {baseline['timestamp'][:16]}")
    
    check = {
        "model": model,
        "baseline_model": baseline["model"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline_timestamp": baseline["timestamp"],
        "results": {},
        "summary": {}
    }
    
    alerts = []
    
    for i, p in enumerate(target_prompts):
        print(f"  [{i+1}/{len(target_prompts)}] {p['id']}: {p['name'][:40]}...", end=" ")
        result = call_llm(p["prompt"], model=model)
        
        if "error" in result and result["error"]:
            print(f"ERROR: {result['error']}")
            continue
        
        val_results = validate(result["response"], p.get("validators", []))
        baseline_entry = baseline["prompts"].get(p["id"], {})
        baseline_resp = baseline_entry.get("response", "")
        baseline_vals = baseline_entry.get("validators", {})
        
        drift = compute_drift_score(baseline_resp, result["response"],
                                    baseline_vals, val_results)
        
        level_icons = {"none": "✅", "low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🚨"}
        icon = level_icons.get(drift["alert_level"], "?")
        print(f"{icon} drift={drift['overall_drift']:.2f} ({drift['alert_level']})")
        
        if drift["alert_level"] in ("high", "critical"):
            alerts.append({
                "prompt_id": p["id"],
                "name": p["name"],
                "alert_level": drift["alert_level"],
                "regressions": drift["regressions"],
                "drift_score": drift["overall_drift"],
            })
        
        check["results"][p["id"]] = {
            "prompt_id": p["id"],
            "category": p["category"],
            "name": p["name"],
            "current_response": result["response"],
            "baseline_response": baseline_resp,
            "validators": val_results,
            "drift": drift,
            "latency_ms": result["latency_ms"],
        }
        time.sleep(0.5)

    # Summary
    if check["results"]:
        all_drifts = [r["drift"]["overall_drift"] for r in check["results"].values()]
        check["summary"] = {
            "total_prompts": len(check["results"]),
            "alerts": len(alerts),
            "alert_details": alerts,
            "avg_drift": round(sum(all_drifts) / len(all_drifts), 3),
            "max_drift": round(max(all_drifts), 3),
            "prompts_passing_all_validators": sum(
                1 for r in check["results"].values()
                if all(v for v in r["validators"].values() if v is not None)
            ),
        }
    
    # Save
    with open(RESULTS_FILE, "w") as f:
        json.dump(check, f, indent=2)
    
    # Append to history
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    history.append({
        "timestamp": check["timestamp"],
        "avg_drift": check["summary"].get("avg_drift", 0),
        "max_drift": check["summary"].get("max_drift", 0),
        "alerts": len(alerts),
        "model": model,
    })
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-200:], f, indent=2)  # Keep last 200 runs
    
    # Print summary
    s = check["summary"]
    print(f"\n{'─'*50}")
    print(f"📊 DRIFT CHECK COMPLETE")
    print(f"   Total prompts: {s.get('total_prompts', 0)}")
    print(f"   Avg drift:     {s.get('avg_drift', 0):.3f}")
    print(f"   Max drift:     {s.get('max_drift', 0):.3f}")
    print(f"   🚨 Alerts:     {s.get('alerts', 0)}")
    if alerts:
        print(f"\n   ALERT DETAILS:")
        for a in alerts:
            print(f"   - [{a['alert_level'].upper()}] {a['name']} (score: {a['drift_score']:.2f})")
            if a["regressions"]:
                print(f"     Regressions: {', '.join(a['regressions'])}")
    print(f"{'─'*50}")
    
    return check


def run_demo(model: str = "claude-3-haiku-20240307"):
    """Run a demo — generate baseline then simulate drift detection with live data."""
    from test_suite import TEST_PROMPTS
    
    print("\n" + "="*60)
    print("🤖 LLM DRIFT DETECTION — LIVE DEMO")
    print("="*60)
    print(f"Model: {model}")
    print(f"Prompts: {len(TEST_PROMPTS[:5])} (abbreviated for demo)")
    
    demo_prompts = TEST_PROMPTS[:5]  # First 5 for speed
    
    print("\n📌 PHASE 1: Establishing baseline...")
    baseline = run_baseline(model, demo_prompts)
    
    print("\n📌 PHASE 2: Running drift check (same model, should be near-zero)...")
    time.sleep(1)
    check = run_check(model, demo_prompts)
    
    print("\n📌 DEMO RESULT:")
    print(f"  Real drift detected: {check['summary'].get('avg_drift', 0):.3f}")
    print("\n  In production, this runs every hour automatically.")
    print("  When drift spikes, you get an immediate alert.")
    print("\n✅ Demo complete. Results saved to data/results.json")
    
    return check


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Drift Detector")
    parser.add_argument("--run", choices=["baseline", "check", "demo"], required=True)
    parser.add_argument("--model", default="claude-3-haiku-20240307",
                        help="Model to test (default: claude-3-haiku-20240307)")
    args = parser.parse_args()
    
    if not HAS_ANTHROPIC:
        print("Installing anthropic package...")
        os.system("pip install anthropic -q")
        import anthropic
        HAS_ANTHROPIC = True
    
    sys.path.insert(0, str(Path(__file__).parent))
    
    if args.run == "baseline":
        from test_suite import TEST_PROMPTS
        run_baseline(args.model, TEST_PROMPTS)
    elif args.run == "check":
        from test_suite import TEST_PROMPTS
        run_check(args.model, TEST_PROMPTS)
    elif args.run == "demo":
        run_demo(args.model)
