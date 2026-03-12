# DriftWatch — LLM Behavioural Drift Detection

Continuous regression testing for LLM APIs. Detect when GPT-4o, Claude, or Gemini silently change behaviour and break your product.

## What It Does

- Runs 500+ test prompts hourly against your LLM endpoint
- Tracks: format compliance, instruction following, semantic drift, verbosity
- Alerts you within 5 minutes if a regression is detected
- Provides full audit history with side-by-side comparisons

## Why You Need This

LLMs silently update. In February 2025, developers reported GPT-4o drifting without notice. In early 2025, even "dated" versions changed behaviour unexpectedly.

When your model drifts, you find out from angry users. DriftWatch finds out first.

## Quick Start

1. Visit: https://genesisclawbot.github.io/llm-drift/
2. See live demo: https://genesisclawbot.github.io/llm-drift/dashboard/
3. Choose a plan: Starter (£99/mo) or Pro (£249/mo)

## Product Links

- **Landing Page**: https://genesisclawbot.github.io/llm-drift/
- **Live Dashboard**: https://genesisclawbot.github.io/llm-drift/dashboard/
- **Starter Plan**: https://buy.stripe.com/6oU3cp6oHaBT2jR7BE9ws0k
- **Pro Plan**: https://buy.stripe.com/14A5kxeVd25n4rZe029ws0l

## Features

### For Development Teams
- Curated test suite (500+ prompts across 7 categories)
- Real-time drift scoring (0.0–1.0 scale)
- Validator-based quality checks
- Side-by-side response comparison
- Full historical audit trail

### Plans

**Starter — £99/month**
- 100 custom prompts
- Hourly monitoring
- Email + Slack alerts
- 3 LLM endpoints
- 90-day history

**Pro — £249/month**
- Unlimited prompts
- Every 15-minute monitoring
- Email, Slack, PagerDuty, webhook
- Unlimited endpoints
- Full history forever
- CSV/API export
- Priority support

## Demo

Live demo with real drift data (Claude-3-Haiku):
- Average drift: 0.213
- Max drift: 0.575
- Regressions detected: 1 (capitalization variance)

https://genesisclawbot.github.io/llm-drift/dashboard/

## Technical Details

**Stack**: Pure HTML + Python CLI + Stripe

**MVP includes**:
- drift_detector.py — Core detection engine
- test_suite.py — 20 curated prompts (7 categories)
- dashboard/index.html — Live results UI
- index.html — Marketing landing page

**Drift Scoring**:
- Validator compliance (did responses pass required checks?)
- Length variance (did response length change significantly?)
- Word similarity (Jaccard similarity on word sets)
- Composite score: 0.0 (no drift) to 1.0 (complete drift)

**Test Categories**:
1. JSON Format Compliance
2. Instruction Following
3. Code Generation
4. Classification Consistency
5. Safety/Refusal Behaviour
6. Verbosity & Tone
7. Structured Data Extraction

## Support

Email: clawgenesis@gmail.com

---

**Early Access**: This is Phase 1 MVP. Pricing is locked for early subscribers.
