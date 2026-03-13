"""Drift runner — calls LLM, scores drift, stores results."""
import json
import os
import sys
import re
from datetime import datetime
from typing import List, Optional

import anthropic

# Add parent dir so we can import the existing core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Low-level LLM call ────────────────────────────────────────────────────────

def call_llm(prompt: str, model: str = "claude-3-haiku-20240307") -> str:
    """Call the LLM and return the response text."""
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text if msg.content else ""
    except anthropic.AuthenticationError:
        raise ValueError("LLM_AUTH_ERROR: API key invalid or missing. Please contact support.")
    except anthropic.RateLimitError:
        raise ValueError("LLM_RATE_LIMIT: Rate limit exceeded. Please try again shortly.")
    except Exception as e:
        raise ValueError(f"LLM_ERROR: {str(e)[:100]}")


# ── Validator helpers ─────────────────────────────────────────────────────────

def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text.strip())
        return True
    except Exception:
        return False


def _word_count(text: str) -> int:
    return len(text.split())


def _run_validators(response: str, validators: List[str]) -> dict:
    """Return {validator_name: bool} for each validator."""
    results = {}
    for v in validators:
        if v == "valid_json":
            results[v] = _is_valid_json(response)
        elif v == "single_word":
            results[v] = _word_count(response.strip()) == 1
        elif v.startswith("word_in:"):
            allowed = [w.strip() for w in v.split(":", 1)[1].split(",")]
            results[v] = response.strip().lower() in [w.lower() for w in allowed]
        elif v == "starts_code_block":
            results[v] = "```" in response
        elif v == "no_refusal":
            refusal_words = ["sorry", "cannot", "can't", "refuse", "inappropriate"]
            results[v] = not any(w in response.lower() for w in refusal_words)
        elif v == "one_sentence":
            sentences = re.split(r'[.!?]+', response.strip())
            non_empty = [s for s in sentences if s.strip()]
            results[v] = len(non_empty) <= 2
        else:
            results[v] = True  # unknown validator: pass
    return results


# ── Drift scoring ──────────────────────────────────────────────────────────────

def _jaccard_similarity(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 1.0


def score_drift(baseline: str, current: str, validators: List[str]) -> dict:
    """
    Return drift score dict:
      drift_score: float 0.0–1.0
      alert_level: none | low | medium | high | critical
      regressions: list of validator names that passed before but fail now
      components: dict of partial scores
    """
    # Exact match
    if baseline.strip() == current.strip():
        return {
            "drift_score": 0.0,
            "alert_level": "none",
            "regressions": [],
            "components": {}
        }

    # Semantic similarity (Jaccard)
    sim = _jaccard_similarity(baseline, current)
    semantic_drift = 1.0 - sim

    # Length drift (normalised)
    base_len = len(baseline.split())
    curr_len = len(current.split())
    if base_len > 0:
        length_drift = min(abs(curr_len - base_len) / base_len, 1.0)
    else:
        length_drift = 0.0 if curr_len == 0 else 1.0

    # Validator regression
    baseline_validators = _run_validators(baseline, validators)
    current_validators = _run_validators(current, validators)
    regressions = [
        v for v in validators
        if baseline_validators.get(v, False) and not current_validators.get(v, False)
    ]
    regression_penalty = min(len(regressions) * 0.25, 0.5)

    # Composite score
    drift_score = round(
        0.50 * semantic_drift + 0.20 * length_drift + 0.30 * regression_penalty,
        3
    )
    drift_score = min(drift_score, 1.0)

    # Alert level
    if drift_score >= 0.6:
        alert_level = "high"
    elif drift_score >= 0.4:
        alert_level = "medium"
    elif drift_score >= 0.2:
        alert_level = "low"
    else:
        alert_level = "none"

    return {
        "drift_score": drift_score,
        "alert_level": alert_level,
        "regressions": regressions,
        "components": {
            "semantic_drift": round(semantic_drift, 3),
            "length_drift": round(length_drift, 3),
            "regression_penalty": round(regression_penalty, 3),
        }
    }


# ── High-level API used by routes ─────────────────────────────────────────────

def run_baseline_for_prompt(prompt_text: str, model: str, validators: List[str]) -> dict:
    """Call LLM and return baseline response + validator results."""
    response = call_llm(prompt_text, model)
    return {
        "response": response,
        "model": model,
        "validators": _run_validators(response, validators),
        "captured_at": datetime.utcnow().isoformat() + "Z",
    }


def run_check_for_prompt(
    prompt_text: str,
    model: str,
    validators: List[str],
    baseline_response: str,
    prompt_id: str,
    prompt_name: str,
) -> dict:
    """Run a drift check for a single prompt and return result dict."""
    current_response = call_llm(prompt_text, model)
    drift = score_drift(baseline_response, current_response, validators)
    return {
        "prompt_id": prompt_id,
        "prompt_name": prompt_name,
        "model": model,
        "baseline": baseline_response,
        "current": current_response,
        "drift_score": drift["drift_score"],
        "alert_level": drift["alert_level"],
        "regressions": drift["regressions"],
        "components": drift["components"],
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }
