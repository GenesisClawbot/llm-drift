# DriftWatch Roadmap

## v1.0.0 — ✅ Shipped (March 2026)

**Core platform**
- [x] Drift detection engine with composite scoring (format + semantic + instruction-following)
- [x] 20 curated test prompts across 7 categories
- [x] SaaS backend (FastAPI + SQLite + APScheduler)
- [x] User accounts + API key provisioning
- [x] Stripe subscriptions (£99/mo Starter, £249/mo Pro)
- [x] Interactive drift dashboard
- [x] Slack + email alerting
- [x] Free tier (3 prompts, no credit card)

---

## v1.1.0 — Deployment & Integrations (April 2026)

**Deployment**
- [ ] Railway one-click deploy template
- [ ] Render.com deploy button
- [ ] Docker Compose self-host guide

**Integrations**
- [ ] PagerDuty webhook on drift threshold breach
- [ ] OpsGenie integration
- [ ] GitHub Actions native action (`uses: genesisclawbot/driftwatch-action@v1`)

**Monitoring targets**
- [ ] Azure OpenAI endpoint support
- [ ] Anthropic Claude API direct integration
- [ ] Google Gemini API support
- [ ] Local Ollama endpoint monitoring

---

## v1.2.0 — Analytics & Comparison (May 2026)

**Multi-model comparison**
- [ ] Head-to-head drift comparison: GPT-4o vs Claude vs Gemini
- [ ] Model drift leaderboard (which provider changes behavior most)
- [ ] Regression timeline: exact date of observed behavioral shift

**Analytics**
- [ ] Historical drift trend graphs (30/90 day views)
- [ ] Drift correlation with OpenAI/Anthropic changelog dates
- [ ] Export drift history as CSV/JSON

---

## v1.3.0 — Team & Scale (June 2026)

**Collaboration**
- [ ] Team workspaces (shared prompt suites)
- [ ] Prompt library sharing between organizations
- [ ] Role-based access (viewer / editor / admin)

**Scale**
- [ ] 500+ prompt test suite (expanded coverage)
- [ ] Sub-minute alert latency option (5-minute checks)
- [ ] PostgreSQL backend for production deployments

---

## Community Wishlist (voting welcome)

Open a [Discussion](https://github.com/GenesisClawbot/llm-drift/discussions) to vote on features:

- Fine-tuned model drift detection (custom GGUF/HuggingFace endpoints)
- Automated PR comments on drift threshold breach
- VS Code extension for real-time drift scoring in editor
- LLM provider status page integration (correlate drift with incidents)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) to add test prompts, fix bugs, or build integrations. PRs welcome!
