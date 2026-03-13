---
name: LLM Drift Report
about: Report a detected or suspected LLM behaviour change
title: "[DRIFT] <model> — <brief description>"
labels: drift-report
assignees: ''
---

## Drift Summary

**Model / Provider:**
(e.g. `gpt-4o-2024-08-06`, `claude-3-5-sonnet`, `gemini-1.5-pro`)

**Approximate date of change:**
(When did you first notice the change?)

**Prompt category:**
- [ ] JSON extraction
- [ ] Classification / labelling
- [ ] Code generation
- [ ] Summarisation
- [ ] Instruction following
- [ ] Other: ___

## What Changed

**Before (baseline output):**
```
paste your baseline output here
```

**After (drifted output):**
```
paste the changed output here
```

**DriftWatch score (if available):**
`drift_score: `

## Impact

**How did this affect your product?**
(e.g. JSON parser failed, classifier gave wrong label, downstream formatting broke)

**How did you discover it?**
- [ ] DriftWatch alert
- [ ] User complaint
- [ ] Manual testing
- [ ] CI test failure

## Additional Context

Any other relevant information, links to the model changelog, or related issues.
