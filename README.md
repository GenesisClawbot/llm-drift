# DriftWatch — LLM Behavioural Drift Detection

> **Your LLM just changed. Did you notice?**

Continuous regression testing for LLM APIs. Detect when GPT-4o, Claude, or Gemini silently change behaviour and break your product — before your users do.

[![Drift Check](https://github.com/GenesisClawbot/llm-drift/actions/workflows/drift-check.yml/badge.svg)](https://github.com/GenesisClawbot/llm-drift/actions/workflows/drift-check.yml)
[![GitHub Stars](https://img.shields.io/github/stars/GenesisClawbot/llm-drift?style=social)](https://github.com/GenesisClawbot/llm-drift)
[![GitHub Release](https://img.shields.io/github/v/release/GenesisClawbot/llm-drift)](https://github.com/GenesisClawbot/llm-drift/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Detected LLM drift? **[⭐ Star this repo](https://github.com/GenesisClawbot/llm-drift)** — helps other developers find it.

**Deploy the backend in one click:**

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/GenesisClawbot/llm-drift)
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

## See It in Action (no API key needed)

```bash
git clone https://github.com/GenesisClawbot/llm-drift.git
cd llm-drift
python3 examples/demo_mode.py
```

Shows real drift data from our production Claude runs:
- `inst-01`: **0.575 drift** — trailing period dropped, breaks exact-match parsers
- `json-01`: **0.316 drift** — inline JSON became pretty-printed
- `json-02`, `json-03`: **0.000** — stable

**Record a terminal demo** (for PRs, reviews, team sharing):
```bash
pip install asciinema
asciinema rec demo.cast
python3 examples/demo_mode.py
# Ctrl+D when done, then: agg demo.cast demo.gif
```

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
    ⚠️ Regression: exact_match failed
    Baseline: "Neutral." → Current: "Neutral" (trailing period dropped)

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

## How Drift Detection Works

The drift score is a weighted composite of three independent signals, computed per-prompt on each monitoring run:

**1. Validator compliance drift (50% weight)**
Each prompt has a set of validators — boolean checks on the response (is it valid JSON? does it return exactly one word? does it contain the expected field names?). The compliance rate of these validators is compared to the baseline. A validator that *passed in the baseline but fails now* is flagged as a **regression**, regardless of overall score.

**2. Length drift (20% weight)**
Absolute percentage change in response length vs. baseline: `|len(current) - len(baseline)| / len(baseline)`. A verbosity-constrained prompt returning a paragraph instead of a sentence scores high on this component. Capped at 1.0.

**3. Jaccard word dissimilarity (30% weight)**
Word-level Jaccard distance: `1 - |words(baseline) ∩ words(current)| / |words(baseline) ∪ words(current)|`. This catches content drift (different words used to express the same concept) and hallucination-style divergence (entirely different output). Not embedding-based — intentionally a fast, deterministic heuristic with no model cost.

**Composite score:** `overall = validator_drift × 0.5 + length_drift × 0.2 + word_distance × 0.3`

**Why not use embeddings?** Embedding-based similarity (e.g. cosine similarity via `text-embedding-3-small`) is better for semantic equivalence but adds per-check API cost and latency, and can mask format regressions that matter for production parsers (two responses with identical meaning but different punctuation have high semantic similarity but one breaks your parser). We use heuristics because format fidelity, not semantic equivalence, is what breaks production code.

**False positive calibration:** Normal stochastic variance for a single-sample baseline produces drift scores of 0.1–0.3 on structured prompts. The alert threshold of 0.3 was calibrated against 150 consecutive Claude-3-Haiku runs — alert rate on unchanged models is < 5% at this threshold.

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

## FAQ

**Q: What happens to my monitoring history when I exceed the free tier?**
Monitoring data (prompt results, drift scores, baselines) is stored in PostgreSQL on the hosted service (Render/Railway) and SQLite when running locally. On the hosted service: free tier retains 90 days of history, Starter retains 12 months, Pro retains unlimited. Baseline files are always preserved — you can re-run checks against any prior baseline. On self-hosted (Docker/Railway), data retention is only limited by your own storage.

**Q: Does this replace my existing evals / LangSmith / Helicone?**
No — it's complementary. Evals test capability. LangSmith/Helicone trace and observe requests. DriftWatch runs *proactive scheduled tests* and alerts when output behaviour changes over time. You wouldn't remove your CI tests when you add production monitoring.

**Q: Can I monitor models I've fine-tuned?**
Yes — any model accessible via the OpenAI, Anthropic, or OpenAI-compatible API endpoint. Specify your fine-tuned model name exactly as you'd call it via the API. Baseline and check runs call it identically.

**Q: Why SQLite for local development?**
SQLite is for local CLI use only (`core/drift_detector.py`). The hosted service uses PostgreSQL. If you're self-hosting the backend via Docker or Railway, the `DATABASE_URL` env var accepts any Postgres connection string.

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
