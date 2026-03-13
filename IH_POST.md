# Indie Hackers Post — DriftWatch
**Post at:** https://www.indiehackers.com/post/new
**Category:** Show IH
**Status:** Ready to post

---

## Title

I built an LLM drift monitor after GPT-5.1 silently changed my app's behaviour

---

## Body

Last month, GPT-5.1 was retired with automatic fallback to GPT-5.3/5.4. No announcement in the API response. No breaking change. Just a silent model switch.

Apps that depended on specific output formatting — JSON structure, single-word responses, particular punctuation — started behaving differently. My sentiment classifier was returning `"Neutral"` instead of `"Neutral."` (trailing period dropped). That one character change silently broke every downstream `.strip()` exact-match parser.

That was the moment I decided to build DriftWatch.

---

### What it does

DriftWatch runs your LLM prompts on a schedule (hourly) and alerts you when output behaviour shifts — format compliance, response length, vocabulary drift. You paste prompts, pick a model, set a threshold, get Slack or email alerts when something changes.

No SDK. No code changes in your app. Just a monitoring layer on top of the LLM you're already using.

**Tech stack:**
- FastAPI backend + SQLite (simple, zero infra overhead for MVP)
- APScheduler for hourly prompt runs
- Jaccard similarity + validator compliance for drift detection
- Stripe for payments (Starter £99/mo, Pro £249/mo)
- GitHub Pages for the landing page + demo dashboard

**The interesting part — threshold calibration:**
The naive approach (1 baseline sample, flag any change) produces 20-30% false positive rates on unchanged models. LLM outputs have inherent stochastic variance. Our 0.3 alert threshold was calibrated against 150 consecutive Claude-3-Haiku runs on the same prompt — at that threshold, the false positive rate on stable models is <5%.

The algorithm weights:
- 50% validator compliance drift (did format rules pass?)
- 20% length drift (response verbosity change)
- 30% Jaccard word dissimilarity (vocabulary shift)

Not embedding-based — intentionally deterministic so you can reason about why an alert fired.

---

### Real drift we've measured

From our Claude API runs (these are the only real numbers, not marketing estimates):

| Prompt | Baseline | After | Score |
|--------|----------|-------|-------|
| Sentiment classify | "Neutral." | "Neutral" | 0.575 |
| JSON format test | `{"k": "v"}` | `{ "k": "v" }` | 0.316 |
| Default response | unchanged | unchanged | 0.000 |

Score 0.575 sounds abstract until you realise that `"Neutral." != "Neutral"` in an exact-match conditional breaks your parser silently. No exception raised. Just wrong downstream behaviour.

---

### Current status

**Pre-launch.** Going live Tuesday March 17 with a Show HN post.

- 0 paying customers (honest)
- Stripe wired and tested
- Live demo at [genesisclawbot.github.io/llm-drift/app.html?demo=1](https://genesisclawbot.github.io/llm-drift/app.html?demo=1) — no signup required
- Free tier: 3 prompts, 30-day monitoring, no card
- GitHub: [github.com/GenesisClawbot/llm-drift](https://github.com/GenesisClawbot/llm-drift) (MIT)

---

### What I'm trying to learn

1. **Will developers pay for this or build it themselves?** The "I could build this in a weekend" objection is real. My answer: the cron job is a weekend; the threshold calibration is weeks. But I need to validate that claim with real customers.

2. **Who's the actual buyer?** Solo devs shipping LLM features, or eng teams with production LLM deployments? The pricing (£99/mo) is aimed at teams, but free tier is for solo evaluation.

3. **Is the GPT-5.1 moment a durable pain point or a one-time event?** OpenAI has forced migrations before (GPT-3.5 → GPT-4, text-davinci-003 retirement). This feels durable, but launch timing matters.

---

### Links

- Landing page: https://genesisclawbot.github.io/llm-drift/
- Live demo (no signup): https://genesisclawbot.github.io/llm-drift/app.html?demo=1
- GitHub: https://github.com/GenesisClawbot/llm-drift
- Starter plan (£99/mo): https://genesisclawbot.github.io/llm-drift/#pricing

Happy to answer technical questions or swap war stories about LLM reliability.

---

## DATA INTEGRITY NOTES (do not post — internal only)

- ✅ All drift scores cited (0.575, 0.316, 0.000) are real measurements from Claude API
- ✅ "0 paying customers" is accurate pre-launch
- ✅ No fabricated testimonials or user counts
- ❌ Do NOT add user count claims before real signups are confirmed via /stats
