# DriftWatch — LLM Behavioural Drift Detection

> **Your LLM just changed. Did you notice?**

Continuous regression testing for LLM APIs. Detect when GPT-4o, Claude, or Gemini silently change behaviour and break your product — before your users do.

[![Drift Check](https://github.com/GenesisClawbot/llm-drift/actions/workflows/drift-check.yml/badge.svg)](https://github.com/GenesisClawbot/llm-drift/actions/workflows/drift-check.yml)

**Deploy the backend in one click:**

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/driftwatch)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/GenesisClawbot/llm-drift)

---

## The Problem

LLMs update silently. When they do, your prompts may no longer work as expected:

- Your JSON parser breaks because the model added a preamble
- Your classifier starts returning different answers
- Your code generator stopped following format instructions

> *"We caught GPT-4o drifting this week... OpenAI changed GPT-4o in a way that significantly changed our prompt outputs. Zero advance notice."*
> — r/LLMDevs, February 2025

**DriftWatch finds out within 5 minutes. Not 3 days later from support tickets.**

---

## Quick Start (< 5 minutes)

```bash
# 1. Clone and install
git clone https://github.com/GenesisClawbot/llm-drift.git
cd llm-drift
pip install -r requirements.txt

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY for GPT-4o

# 3. Establish baseline (run when model behaves correctly)
python3 core/drift_detector.py --run baseline

# 4. Check for drift any time
python3 core/drift_detector.py --run check

# 5. Run demo (baseline + check in one shot)
python3 core/drift_detector.py --run demo
```

### Example Output

```
🔍 Running drift check — claude-3-haiku-20240307
   Baseline from: 2026-03-12T18:51

  [🔴 MEDIUM] Single word response: drift=0.575
    ⚠️ Regression: word_in:positive,negative,neutral
    Baseline: "neutral" → Current: "Neutral" (capitalization drift!)

  [🟠 MEDIUM] JSON extraction — strict schema: drift=0.316
    Different whitespace formatting — format compliance changed

  [✅ NONE] JSON array extraction: drift=0.000 (stable)

──────────────────────────────────────────────────
📊 DRIFT CHECK COMPLETE
   Total prompts:  5
   Avg drift:      0.213
   Max drift:      0.575
   🚨 Alerts:      0
──────────────────────────────────────────────────
```

---

## Automated Hourly Monitoring (GitHub Actions)

The repo includes a pre-built GitHub Actions workflow that runs drift checks every hour:

1. **Fork or clone** this repo to your GitHub account
2. Go to **Settings → Secrets → Actions**
3. Add `ANTHROPIC_API_KEY` (or your LLM provider key)
4. The workflow at `.github/workflows/drift-check.yml` runs automatically

Results are committed to `data/results.json` after every run. View them in the [dashboard](https://genesisclawbot.github.io/llm-drift/dashboard/).

---

## What Gets Tracked

| Category | Tests | What It Catches |
|----------|-------|-----------------|
| JSON Format Compliance | 3 | Model adds preamble, changes whitespace, breaks parsers |
| Instruction Following | 5 | Returns paragraph instead of one word, ignores format rules |
| Code Generation | 3 | Adds explanation prose, changes function signatures |
| Classification | 3 | Different category labels for same input |
| Safety/Refusal | 2 | Starts refusing things it previously answered |
| Verbosity/Tone | 3 | Response length changes, "Great question!" preamble drift |
| Data Extraction | 2 | Date format changes, monetary amount parsing breaks |

**20 tests included.** Starter plan: 100 custom tests. Pro: unlimited.

---

## Drift Score Explained

Each prompt gets a **drift score from 0.0 to 1.0**:

| Score | Level | Meaning |
|-------|-------|---------|
| 0.0–0.09 | None ✅ | Stable — responses are consistent |
| 0.1–0.29 | Low 🟡 | Minor variance, probably fine |
| 0.3–0.59 | Medium 🟠 | Noticeable change, investigate |
| 0.6–0.79 | High 🔴 | Significant drift, likely breaking change |
| 0.8–1.0 | Critical 🚨 | Severe regression, action required |

**Regression** = validator that was passing now fails (e.g. JSON was valid, now it's not). Always flagged regardless of overall score.

---

## Links

| | |
|--|--|
| 🌐 **Landing Page** | https://genesisclawbot.github.io/llm-drift/ |
| 📊 **Live Dashboard** | https://genesisclawbot.github.io/llm-drift/dashboard/ |
| 💳 **Starter Plan £99/mo** | https://buy.stripe.com/6oU3cp6oHaBT2jR7BE9ws0k |
| 💳 **Pro Plan £249/mo** | https://buy.stripe.com/14A5kxeVd25n4rZe029ws0l |
| ✉️ **Support** | clawgenesis@gmail.com |

---

## Plans

| | Starter | Pro |
|--|---------|-----|
| **Price** | £99/month | £249/month |
| **Test prompts** | 100 | Unlimited |
| **Check cadence** | Hourly | Every 15 min |
| **Alerts** | Email + Slack | Email, Slack, PagerDuty, Webhook |
| **LLM endpoints** | 3 | Unlimited |
| **History** | 90 days | Forever |
| **Export** | — | CSV + API |
| **Support** | Standard | Priority |

[**Start free trial →**](https://buy.stripe.com/6oU3cp6oHaBT2jR7BE9ws0k)

---

## File Structure

```
llm-drift/
├── index.html              # Marketing landing page
├── dashboard/
│   └── index.html          # Interactive drift dashboard
├── onboard.html            # Post-payment onboarding guide
├── core/
│   ├── drift_detector.py   # Core detection engine + CLI
│   └── test_suite.py       # 20 curated test prompts
├── data/
│   ├── baseline.json       # Baseline responses (git-tracked)
│   ├── results.json        # Latest check results
│   └── history.json        # Historical drift scores
├── .github/
│   └── workflows/
│       └── drift-check.yml # GitHub Actions hourly automation
└── requirements.txt        # anthropic>=0.20.0
```

---

## Resources

### Blog Posts
- [Gemini 1.5 Pro Behavior Changed — Production Drift Data](https://genesisclawbot.github.io/llm-drift/blog/gemini-behavior-drift.html)
- [GPT-4o-2024-08-06 Isn't Frozen: What Version Pinning Actually Guarantees](https://genesisclawbot.github.io/llm-drift/blog/gpt-4o-pinned-still-changed.html)
- [GPT-5.2 Changed on Feb 10 — Did Your Prompts Break?](https://genesisclawbot.github.io/llm-drift/blog/gpt-52-behavior-change.html)
- [Why LLM Version Pinning Doesn't Protect You](https://genesisclawbot.github.io/llm-drift/blog/llm-version-pinning.html)

### Comparisons
- [DriftWatch vs LangSmith](https://genesisclawbot.github.io/llm-drift/compare/langsmith.html) — tracing vs drift detection
- [DriftWatch vs Langfuse](https://genesisclawbot.github.io/llm-drift/compare/langfuse.html) — open-source observability vs proactive alerting
- [DriftWatch vs Helicone](https://genesisclawbot.github.io/llm-drift/compare/helicone.html) — proxy logging vs scheduled monitoring
- [DriftWatch vs PromptFoo](https://genesisclawbot.github.io/llm-drift/compare/promptfoo.html) — pre-deploy evals vs production drift monitoring

### Related dev.to Articles
- [PromptFoo Passes. Production Still Breaks.](https://dev.to/clawgenesis/promptfoo-passes-production-still-breaks-heres-the-gap-24em)
- [Claude 3.5 Sonnet Changed. My System Prompt Stopped Working.](https://dev.to/clawgenesis/claude-35-sonnet-changed-my-system-prompt-stopped-working-heres-what-i-learned-nk)
- [Gemini 1.5 Pro Also Drifts.](https://dev.to/clawgenesis/gemini-15-pro-also-drifts-heres-what-changed-in-our-production-prompts-3fid)
- [Your LLM CI/CD Tests Aren't Enough](https://dev.to/clawgenesis/your-llm-cicd-tests-arent-enough-heres-the-gap-2o19)

---

## License

MIT — use freely, star if useful, subscribe if it saves you from a 3am outage.
