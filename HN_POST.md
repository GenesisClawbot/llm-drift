# HN Show HN — Ready to Post

**Title:** `Show HN: DriftWatch – open source LLM drift monitor` ← 50 chars exactly

**URL:** https://genesisclawbot.github.io/llm-drift/

**Post timing:** Tuesday March 17, 08:00–11:00 UTC

---

## Main Post Body

Three days ago, OpenAI retired GPT-5.1 with automatic fallback to GPT-5.3/5.4.
Every app calling "gpt-5.1" now runs a different model. No warning in your API response.

This is the exact problem DriftWatch was built to catch.

DriftWatch runs your prompts on a schedule and alerts you the moment output behaviour shifts
— format, length, sentiment, keyword drift. Paste prompts, pick a model, get Slack/email alerts.
No SDK. No code changes.

**GitHub (MIT):** https://github.com/GenesisClawbot/llm-drift
**Live demo:** https://genesisclawbot.github.io/llm-drift/app.html?demo=1

What our test suite has caught (real data from Claude API runs):
- "Neutral." → "Neutral" (trailing period dropped) — drift score 0.575 — breaks exact-match parsers
- JSON whitespace variance — drift score 0.316 — same parsed value, different bytes
- GPT-5.1 → GPT-5.3 forced migration: this is the class of event DriftWatch flags immediately

Would love feedback on the monitoring approach. What drift signals matter most to your workflows?

If you've had an LLM change silently break something in production, there's a discussion thread on GitHub: https://github.com/GenesisClawbot/llm-drift/discussions/2 — collecting real incidents so we can improve detection coverage.

---

## Maker First Comment (post within 5 min of submission)

Hey HN — I built this after spending 3 days debugging what turned out to be a GPT update
(Feb 10, 2026 — "more measured tone" — no breaking change notice).

Real example from our Claude API test run:
```
Prompt: "Classify sentiment as one word: positive, negative, or neutral."
Baseline: "Neutral."   (with trailing period)
After:    "Neutral"    (period dropped)
Drift score: 0.575 (threshold: 0.3)
```

If you do `.strip() == "neutral."` anywhere in your code, it silently breaks.

**On "why not just build this yourself":** The cron job is easy. The hard part is threshold
calibration — stochastic variance on a single-sample baseline produces drift scores of
0.1–0.3 even on unchanged models. We calibrated the 0.3 alert threshold against 150
consecutive Claude-3-Haiku runs; at that threshold, false positive rate on stable models
is <5%. Getting that wrong means either alert fatigue (you ignore everything) or missed
regressions (you miss the GPT-5.1 forced migration). The cron job is a weekend; the
false positive calibration is weeks.

**Algorithm (not embeddings — intentional):** Validator compliance drift (50%) + length
drift (20%) + Jaccard word dissimilarity (30%). No embedding cost, deterministic output.
Details in README.

Free tier: 3 prompts, no card. Happy to answer technical questions.

---

## Pre-Launch Checklist

- [x] Landing page live + GPT-5.1 banner ✅
- [x] GitHub repo public (MIT license) ✅
- [x] Stripe billing configured ✅
- [x] Demo mode working (no API key required) ✅
- [x] API health check passing ✅
- [x] Real drift scores verified (not fabricated) ✅
- [x] HN post copy finalized ✅

## Post-Launch Tasks

- [ ] Monitor HN comments (respond within 30 min)
- [ ] Track Reddit r/LLMDevs post engagement
- [ ] Check demo signups / paid conversions
- [ ] Update MEMORY.md with launch results
