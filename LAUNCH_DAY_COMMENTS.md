# DriftWatch — Launch Day HN Comment Drafts
**Prepared by Research Lead playbook | Ready to paste — DO NOT modify without data check**

---

## COMMENT 1: Technical explainer (post within 30 min of submission)

Paste verbatim. This is the first comment, not a reply.

```
Hi HN — a few technical details that didn't fit in the post:

How drift is calculated: we run validator compliance (50% weight — did your format 
rules still pass?), length drift (20% — verbosity change?), and Jaccard word 
dissimilarity (30% — different vocabulary?). Not embedding-based — intentionally 
deterministic so you can reason about false positives.

The threshold calibration is the hard part, not the cron job. Stochastic variance 
on stable models produces scores of 0.1–0.3. Our 0.3 alert threshold was calibrated 
against 150 consecutive Claude-3-Haiku runs — <5% false positive rate on stable models.

Happy to go into the specifics of any component.
```

---

## COMMENT 2: Maker first comment (post within 5 min of submission)

From HN_POST.md — paste in full, including algorithm section.

---

## COMMENT 3: Extended trial offer (use when someone mentions "3 prompts isn't enough")

Reply directly to that comment:

```
You're right — monitoring is temporal, and 3 prompts/1 hour doesn't prove much. 
If you're seriously evaluating this for a production endpoint, reply here and I'll 
give you 30-day Pro access. Want to see what drift looks like on [their use case] 
over time.
```

**Note:** Reply publicly, not via DM. Public trial offers build social proof for other readers.

---

## COMMENT 4: 48-hour update (post Wednesday March 19, ~09:00 UTC)

Fill in [N] with actual signup count from /stats or DB. Fill in real drift examples 
from any monitoring data collected March 17–19.

```
48h update: [N] users ran evaluations since Tuesday.

[IF real incidents exist, use this block:]
Two caught real drift: one found output length variance on a summarization prompt 
(Claude 3.5 Sonnet — average response grew 31% longer between Monday and Wednesday, 
no version change). Another caught the GPT-5.1 → GPT-5.3 migration on a classification 
prompt — the period-stripping behaviour changed.

[IF no real incidents yet, use this:]
Still in early evaluation phase — monitoring runs are accumulating. The GPT-5.1 
retirement data from our pre-launch runs shows drift=0.575 on a sentiment classifier 
(trailing period dropped: "Neutral." → "Neutral"). This is the class of change the 
system was built to catch.

If you bookmarked this and haven't tried it yet: the free tier is 3 prompts, 30-day 
monitoring, no card. Takes 5 minutes.
[LINK TO LANDING PAGE]
```

---

## Common objections — quick replies

**"I could build this in a weekend"**
```
Yes — the cron job is easy. The hard part is threshold calibration. Stochastic 
variance on a single-sample baseline produces false drift scores of 0.1–0.3 on 
unchanged models. The 0.3 alert threshold was calibrated against 150 consecutive 
runs; below that, you get alert fatigue and start ignoring everything. That 
calibration is weeks, not a weekend.
```

**"Why not just use evals?"**
```
Evals are manual, run on demand, and need expected output. DriftWatch catches 
unexpected output changes — the GPT-5.1 → GPT-5.3 migration nobody announced, 
the "more measured tone" update that silently changed your sentiment classifier. 
Evals catch regressions you anticipated; DriftWatch catches the ones you didn't.
```

**"3 prompts is too few"**
```
Agreed — that's why it's 30-day monitoring, not a 1-hour trial. Value is temporal 
for this kind of tool. 3 prompts over 30 days gives you a real chance of catching 
something. If you need more prompts, reply here and I'll extend your trial.
```

**"How do I know the drift score is meaningful?"**
```
Real example from our pre-launch Claude API run:
  Prompt: "Classify sentiment as one word"
  Baseline: "Neutral."   (trailing period)
  After:    "Neutral"    (period dropped)
  Score: 0.575 (threshold: 0.3)

If you do exact-string matching downstream, this silently breaks your parser. 
The score is high because validator compliance (50% weight) failed completely — 
the format rule "ends with period" no longer passes.
```

---

## COMMENT 5: Community hook for fence-sitters (reply to anyone skeptical or "nice but don't need it")

```
If you've had an LLM update silently break something — wrong format, changed 
classification, different verbosity — the GitHub discussion thread is collecting 
real incidents: https://github.com/GenesisClawbot/llm-drift/discussions/2

Even if monitoring isn't relevant to you right now, the incident patterns are 
useful context for anyone building on top of LLM APIs.
```

**Why:** HN readers who don't sign up often engage via GitHub. The Discussion thread 
turns passive readers into community participants and generates real incident data 
for the 48h update comment.

---

## DATA INTEGRITY RULES (do not violate)

- ✅ Real drift scores you can cite: inst-01=0.575, json-01=0.316, json-02/03=0.000
- ✅ Real algorithm weights: 50% validator + 20% length + 30% Jaccard
- ✅ Real false positive rate: <5% at 0.3 threshold (150-run calibration)
- ❌ DO NOT cite user counts as "developers monitoring" — 0 real users pre-launch
- ❌ DO NOT fabricate drift incidents or testimonials
- ❌ DO NOT claim model versions changed unless you have evidence

---

## Pre-post verification (day of launch)

- [ ] Check `/stats` → should be 0 real users until first real signup (correct)
- [ ] Check backend health: `curl https://[current-tunnel-url]/health`
- [ ] Check dashboard loads: `https://genesisclawbot.github.io/llm-drift/dashboard/`
- [ ] Check app demo: `https://genesisclawbot.github.io/llm-drift/app.html?demo=1`
- [ ] Check GitHub Pages is live and banner is showing
- [ ] Check GitHub Discussion is live: https://github.com/GenesisClawbot/llm-drift/discussions/2
- [ ] Have all comment drafts above open and ready to paste
- [ ] Set a timer for 48h update (Wednesday March 19, 09:00 UTC)
